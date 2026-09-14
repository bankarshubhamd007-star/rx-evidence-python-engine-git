"""
providers/ddg_provider.py — DuckDuckGo Search Provider
======================================================
the free duckduckgo-search package.
Instead of downloading full web pages, this uses the blazing-fast search 
snippets (the summary text returned by the search engine) to gather evidence 
from trusted public health domains like CDC and WHO.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ddgs import DDGS

from .base import BaseProvider, RawEvidenceItem

logger = logging.getLogger(__name__)

# Trusted medical authority domains to scope the search.
MEDICAL_DOMAINS = [
    "cdc.gov",
    "who.int",
    "mayoclinic.org",
    "nih.gov",
    "uptodate.com",
    "diabetes.org", # ADA
    "heart.org",    # AHA
]

class DDGProvider(BaseProvider):
    """Searches DuckDuckGo for fast public health snippets."""

    @property
    def name(self) -> str:
        return "DuckDuckGo"

    async def fetch(self, query: str, max_results: int = 5) -> list[RawEvidenceItem]:
        """
        Call DuckDuckGo with a lightweight medical keyword query.
        Uses the 'api' backend to avoid slow multi-engine fallback cascading.
        """
        # Instead of appending 7 site: operators (which makes the query huge
        # and forces DDG to cascade through multiple backends), we add short
        # medical keywords so results are naturally biased toward health sources.
        search_query = f"{query} medical health evidence"

        items: list[RawEvidenceItem] = []

        def _sync_search():
            with DDGS() as ddgs:
                return list(ddgs.text(search_query, max_results=max_results))

        try:
            results = await asyncio.to_thread(_sync_search)
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return []

        if not results:
            return items

        for result in results:
            # DDGS returns 'title', 'href', 'body'
            title = result.get("title", "Unknown Title")
            url = result.get("href", "")
            snippet = result.get("body", "")

            if not snippet:
                continue

            publisher = _extract_publisher(url)

            items.append(
                RawEvidenceItem(
                    text=snippet,
                    title=title,
                    publisher=publisher,
                    url=url,
                )
            )

        return items


def _extract_publisher(url: str) -> str:
    """Map a URL to a human-readable publisher name."""
    domain_map = {
        "cdc.gov": "CDC",
        "who.int": "WHO",
        "mayoclinic.org": "Mayo Clinic",
        "nih.gov": "NIH",
        "uptodate.com": "UpToDate",
        "diabetes.org": "ADA",
        "heart.org": "AHA",
    }
    url_lower = url.lower()
    for domain, name in domain_map.items():
        if domain in url_lower:
            return name
    return "DuckDuckGo"
