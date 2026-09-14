"""
providers/clinical_trials_provider.py — ClinicalTrials.gov API Connector
========================================================================
ClinicalTrials.gov (API v2) provides access to study records.
This provider fetches ongoing or completed trials. While the LLM will
primarily rely on published results from PubMed, ClinicalTrials.gov
can provide evidence of ongoing research, study protocols, and
experimental side effect tracking.

Because we use a Vector Database (ChromaDB) to rank all evidence before
it goes to the LLM, adding this provider does NOT overwhelm the LLM. 
The LLM still only reads the Top 5 most relevant chunks across all APIs.

API docs: https://clinicaltrials.gov/data-api/api
Rate limits: Free, no API key required.
"""

from __future__ import annotations

import httpx
from app.http_client import get_client

from app.shared.core.config import settings
from .base import BaseProvider, RawEvidenceItem

CLINICAL_TRIALS_URL = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsProvider(BaseProvider):
    """Searches ClinicalTrials.gov for study records and results."""

    @property
    def name(self) -> str:
        return "ClinicalTrials.gov"

    async def fetch(self, query: str, max_results: int = 3) -> list[RawEvidenceItem]:
        """
        Query the ClinicalTrials.gov API v2.
        """
        params = {
            "query.term": query,
            "pageSize": str(max_results),
            "format": "json",
        }

        client = get_client()
        if True:
            resp = await client.get(CLINICAL_TRIALS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items: list[RawEvidenceItem] = []

        for study in data.get("studies", []):
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            description = protocol.get("descriptionModule", {})
            status = protocol.get("statusModule", {})

            nct_id = identification.get("nctId", "")
            title = identification.get("briefTitle", "Untitled Study")
            
            # Combine brief summary and detailed description
            brief_summary = description.get("briefSummary", "")
            detailed_desc = description.get("detailedDescription", "")
            
            text_parts = []
            if brief_summary:
                text_parts.append(f"Brief Summary: {brief_summary}")
            if detailed_desc:
                text_parts.append(f"Detailed Description: {detailed_desc}")
            
            text = " ".join(text_parts).strip()
            if not text:
                text = title

            url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "https://clinicaltrials.gov/"

            items.append(
                RawEvidenceItem(
                    text=text,
                    title=f"Clinical Trial: {title}",
                    publisher="ClinicalTrials.gov",
                    url=url,
                    metadata={
                        "nct_id": nct_id,
                        "status": status.get("overallStatus", "Unknown"),
                    },
                )
            )

        return items
