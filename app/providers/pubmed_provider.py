"""
providers/pubmed_provider.py — NCBI PubMed E-Utilities Connector
===================================================================
PubMed is the world's largest biomedical literature database.  This
provider uses the NCBI E-Utilities (ESearch + EFetch) to find relevant
abstracts for a medical claim.

How it works:
  1. ESearch:  Sends the claim as a query, restricted to high-quality
               publication types (Practice Guidelines, Systematic Reviews,
               Meta-Analyses, Clinical Trials).
               Returns a list of PMIDs (PubMed IDs).
  2. EFetch:   Takes those PMIDs and returns the full article metadata
               including title, abstract, journal, and publication date.

API docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
Rate limits: Without an API key → 3 requests/sec.
             With an API key → 10 requests/sec.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from app.http_client import get_client

from app.shared.core.config import settings
from .base import BaseProvider, RawEvidenceItem

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Focus on the highest-quality evidence types.
PUBMED_FILTERS = "(Practice Guideline[pt] OR Systematic Review[pt] OR Meta-Analysis[pt] OR Clinical Trial[pt] OR Review[pt])"


class PubMedProvider(BaseProvider):
    """Searches PubMed for clinical guidelines, reviews, and trials."""

    @property
    def name(self) -> str:
        return "PubMed"

    async def fetch(self, query: str, max_results: int = 5) -> list[RawEvidenceItem]:
        """
        Two-step PubMed search: ESearch → EFetch.
        """
        client = get_client()
        if True:
            # ── Step 1: ESearch — get PMIDs ──
            search_params = {
                "db": "pubmed",
                "term": f"({query}) AND {PUBMED_FILTERS}",
                "retmax": str(max_results),
                "retmode": "json",
                "sort": "relevance",
            }
            if settings.pubmed_api_key:
                search_params["api_key"] = settings.pubmed_api_key

            search_resp = await client.get(ESEARCH_URL, params=search_params)
            search_resp.raise_for_status()
            search_data = search_resp.json()

            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []

            # ── Step 2: EFetch — get full article metadata ──
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "rettype": "xml",
                "retmode": "xml",
            }
            if settings.pubmed_api_key:
                fetch_params["api_key"] = settings.pubmed_api_key

            fetch_resp = await client.get(EFETCH_URL, params=fetch_params)
            fetch_resp.raise_for_status()

        return _parse_pubmed_xml(fetch_resp.text)


def _parse_pubmed_xml(xml_text: str) -> list[RawEvidenceItem]:
    """Parse PubMed EFetch XML into RawEvidenceItem list."""
    items: list[RawEvidenceItem] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for article_el in root.findall(".//PubmedArticle"):
        # Extract PMID.
        pmid_el = article_el.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None and pmid_el.text else ""

        # Extract title.
        title_el = article_el.find(".//ArticleTitle")
        title = title_el.text if title_el is not None and title_el.text else "Untitled"

        # Extract abstract (may have multiple AbstractText elements).
        abstract_parts: list[str] = []
        for abs_el in article_el.findall(".//AbstractText"):
            label = abs_el.get("Label", "")
            text = abs_el.text or ""
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)

        abstract = " ".join(abstract_parts).strip()
        if not abstract:
            abstract = title  # Fall back to title if no abstract.

        # Extract journal name.
        journal_el = article_el.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None and journal_el.text else "PubMed"

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        items.append(
            RawEvidenceItem(
                text=abstract,
                title=title,
                publisher=journal if journal != "PubMed" else "PubMed",
                url=url,
                metadata={"pmid": pmid, "journal": journal},
            )
        )

    return items
