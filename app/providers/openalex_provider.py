"""
providers/openalex_provider.py — OpenAlex Open-Access Paper Search
=====================================================================
OpenAlex is a free, open-source index of the global research system
(250M+ works).  It's an excellent complement to PubMed because it
covers journals, conferences, and preprints across all disciplines.

Key features:
  - Free API, no key required (but polite-pool email gets higher rate limits).
  - Returns open-access full-text links when available.
  - Citation counts and concept tags for filtering.

API docs: https://docs.openalex.org
Rate limits: Polite pool (with email) → 10 requests/sec.
             Without → 1 request/sec.
"""

from __future__ import annotations

import httpx
from app.http_client import get_client

from app.shared.core.config import settings
from .base import BaseProvider, RawEvidenceItem

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


class OpenAlexProvider(BaseProvider):
    """Searches OpenAlex for open-access academic papers."""

    @property
    def name(self) -> str:
        return "OpenAlex"

    async def fetch(self, query: str, max_results: int = 5) -> list[RawEvidenceItem]:
        """
        Query the OpenAlex Works API filtered to medical / health concepts.
        """
        params: dict[str, str] = {
            "search": query,
            "per_page": str(max_results),
            "sort": "relevance_score:desc",
            "select": "id,title,abstract_inverted_index,primary_location,cited_by_count,publication_year,doi",
        }

        # Use polite-pool email if an OpenAlex key is configured.
        if settings.openalex_api_key:
            params["mailto"] = settings.openalex_api_key  # OpenAlex uses email, not a key

        client = get_client()
        if True:
            resp = await client.get(OPENALEX_WORKS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items: list[RawEvidenceItem] = []

        for work in data.get("results", []):
            title = work.get("title", "Untitled") or "Untitled"

            # OpenAlex stores abstracts as inverted indexes — reconstruct.
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            text = abstract if abstract else title

            # Primary location for URL and journal name.
            primary = work.get("primary_location") or {}
            source = primary.get("source") or {}
            publisher = source.get("display_name", "OpenAlex")

            # Prefer DOI link, then landing page.
            doi = work.get("doi", "")
            landing_page = primary.get("landing_page_url", "")
            url = doi if doi else landing_page if landing_page else ""

            citation_count = work.get("cited_by_count", 0)
            year = work.get("publication_year", "")

            items.append(
                RawEvidenceItem(
                    text=text,
                    title=title,
                    publisher=publisher,
                    url=url,
                    metadata={
                        "citation_count": citation_count,
                        "year": year,
                    },
                )
            )

        return items


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """
    OpenAlex stores abstracts as inverted indexes:
        {"The": [0, 5], "study": [1], "found": [2], ...}

    Reconstruct the original text by sorting token positions.
    """
    if not inverted_index:
        return ""

    # Build a list of (position, word) tuples.
    position_word: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word.append((pos, word))

    # Sort by position and join.
    position_word.sort(key=lambda x: x[0])
    return " ".join(word for _, word in position_word)
