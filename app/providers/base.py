"""
providers/base.py — Base Provider Abstract Class
===================================================
Every medical API connector inherits from BaseProvider.  This ensures
a uniform interface so the orchestrator can call any provider the same
way:

    provider = TavilyProvider(settings)
    items = await provider.fetch("semaglutide gastric emptying")

Each provider returns a list of RawEvidenceItem — a flat data class that
carries the raw text, title, source URL, and publisher name.  The
orchestrator then feeds these items into the SemanticChunker → ChromaDB
pipeline.

Design principles:
  - All I/O is async (httpx.AsyncClient) for concurrent API calls.
  - Every provider has a shared timeout so one slow API doesn't block
    the entire pipeline.
  - Errors are caught and logged; a failing provider returns an empty
    list instead of crashing the whole request.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field

import httpx
from cachetools import TTLCache

from app.shared.core.config import settings

# Global cache for all providers: key=(provider_name, query, max_results), value=list[RawEvidenceItem]
# Initialize with maxsize=1000 and TTL from settings
_provider_cache: TTLCache | None = None

def get_provider_cache() -> TTLCache:
    global _provider_cache
    if _provider_cache is None:
        _provider_cache = TTLCache(maxsize=1000, ttl=settings.provider_cache_ttl)
    return _provider_cache

logger = logging.getLogger(__name__)


@dataclass
class RawEvidenceItem:
    """
    A single piece of raw evidence fetched from any medical API.

    Fields:
        text:      The main textual content (abstract, label section, summary).
        title:     Title of the article / guideline / document.
        publisher: Human-readable source name (e.g., "PubMed", "openFDA", "ADA").
        url:       Direct link to the original source.
        metadata:  Optional extra info (PMID, citation count, etc.).
    """

    text: str
    title: str
    publisher: str
    url: str
    metadata: dict[str, str | int | float] = field(default_factory=dict)


class BaseProvider(abc.ABC):
    """
    Abstract base class for all medical evidence providers.

    Subclasses must implement:
        name      — Human-readable provider name (e.g., "PubMed").
        fetch()   — Async method that queries the API and returns evidence items.

    Provides:
        _client   — A shared httpx.AsyncClient with the configured timeout.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name of this provider (e.g., 'PubMed')."""
        ...

    @abc.abstractmethod
    async def fetch(self, query: str, max_results: int = 5) -> list[RawEvidenceItem]:
        """
        Query the external API and return raw evidence items.

        Args:
            query:       The medical claim or search query.
            max_results: Maximum number of results to return.

        Returns:
            A list of RawEvidenceItem objects (may be empty on error).
        """
        ...

    async def safe_fetch(self, query: str, max_results: int = 5) -> list[RawEvidenceItem]:
        """
        Wrapper around fetch() that catches all exceptions and implements caching.
        """
        import time
        t0 = time.time()
        cache = get_provider_cache()
        cache_key = (self.name, query.lower(), max_results)
        
        if cache_key in cache:
            logger.info(f"[Provider: {self.name}] Retrieved from cache (0.00s)")
            return cache[cache_key]

        try:
            items = await self.fetch(query, max_results)
            elapsed = time.time() - t0
            logger.info(f"[Provider: {self.name}] Fetched {len(items)} items in {elapsed:.2f}s")
            if items:
                cache[cache_key] = items
            return items
        except httpx.TimeoutException:
            logger.warning(f"[Provider: {self.name}] Request timed out after {settings.provider_timeout}s")
            return []
        except httpx.HTTPStatusError as exc:
            logger.warning(f"[Provider: {self.name}] API Error (HTTP {exc.response.status_code})")
            return []
        except Exception as exc:
            logger.error(f"[Provider: {self.name}] Unexpected error occurred: {exc}")
            return []
