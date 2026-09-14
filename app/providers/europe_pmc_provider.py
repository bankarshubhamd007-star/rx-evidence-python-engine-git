"""
providers/europe_pmc_provider.py — Europe PMC Article Search
================================================================
Europe PMC is a free, open-access biomedical literature database
maintained by EMBL-EBI.  It indexes PubMed, PMC, preprints, and
clinical guidelines from European sources.

Key advantages over PubMed alone:
  - Includes preprints (MedRxiv, BioRxiv)
  - No API key required
  - Returns full abstracts directly in JSON (no XML parsing needed)
  - Open-access full-text links

API docs: https://europepmc.org/RestfulWebService
Rate limits: Generous — no key required.
"""

from __future__ import annotations

import httpx
from app.http_client import get_client

from app.shared.core.config import settings
from .base import BaseProvider, RawEvidenceItem

EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePMCProvider(BaseProvider):
    """Searches Europe PMC for biomedical articles and preprints."""

    @property
    def name(self) -> str:
        return "Europe PMC"

    async def fetch(self, query: str, max_results: int = 5) -> list[RawEvidenceItem]:
        """
        Query the Europe PMC REST API.

        We filter to reviews, guidelines, and meta-analyses for high-quality
        evidence.
        """
        params = {
            "query": query,
            "format": "json",
            "pageSize": str(max_results),
            "resultType": "lite",
        }

        client = get_client()
        resp = await client.get(
            EUROPEPMC_SEARCH_URL,
            params=params,
            headers={
                "Accept": "application/json",
                "User-Agent": "rx-evidence-engine/0.1 (medical-claim-verification)",
            }
        )
        resp.raise_for_status()
        data = resp.json()

        items: list[RawEvidenceItem] = []

        result_list = data.get("resultList", {}).get("result", [])
        for article in result_list:
            title = article.get("title", "Untitled") or "Untitled"
            abstract = article.get("abstractText", "")
            text = abstract if abstract else title

            # Build URL from PMID or DOI.
            pmid = article.get("pmid", "")
            doi = article.get("doi", "")
            if pmid:
                url = f"https://europepmc.org/article/MED/{pmid}"
            elif doi:
                url = f"https://doi.org/{doi}"
            else:
                url = ""

            journal = article.get("journalTitle", "Europe PMC")
            year = article.get("pubYear", "")
            citation_count = article.get("citedByCount", 0)

            items.append(
                RawEvidenceItem(
                    text=text,
                    title=title,
                    publisher=journal if journal else "Europe PMC",
                    url=url,
                    metadata={
                        "pmid": pmid,
                        "doi": doi,
                        "year": year,
                        "citation_count": citation_count,
                    },
                )
            )

        return items
