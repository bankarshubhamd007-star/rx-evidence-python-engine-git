"""
providers/openfda_provider.py — openFDA Drug Label Connector
================================================================
The openFDA API provides access to FDA drug labeling data, including:
  - Drug descriptions and indications
  - Warnings and black-box warnings
  - Adverse reactions
  - Contraindications

This is critical for verifying drug safety claims.  If someone claims
"Drug X is safe for pregnant women", we can check the FDA label's
warnings section.

API docs: https://open.fda.gov/apis/drug/label/
Rate limits: With API key → 240 requests/minute.
"""

from __future__ import annotations

import httpx
from app.http_client import get_client

from app.shared.core.config import settings
from .base import BaseProvider, RawEvidenceItem

OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"


class OpenFDAProvider(BaseProvider):
    """Searches openFDA for drug labels, warnings, and adverse reactions."""

    @property
    def name(self) -> str:
        return "openFDA"

    async def fetch(self, query: str, max_results: int = 3) -> list[RawEvidenceItem]:
        """
        Query the openFDA Drug Label API.

        We search across multiple label fields:
          - purpose, indications_and_usage, warnings, adverse_reactions
        """
        import re
        
        # Sanitize query for OpenFDA's strict Lucene parser (e.g. curly quotes cause 400 Bad Request)
        safe_query = query.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        # Remove any remaining non-ASCII characters that might break the search
        safe_query = re.sub(r'[^\x00-\x7F]+', ' ', safe_query)
        
        params: dict[str, str] = {
            "search": safe_query,
            "limit": str(min(max_results, 5)),  # openFDA max is 99
        }
        if settings.openfda_api_key:
            params["api_key"] = settings.openfda_api_key

        client = get_client()
        if True:
            resp = await client.get(OPENFDA_LABEL_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items: list[RawEvidenceItem] = []

        for result in data.get("results", []):
            # Build a combined text from the most relevant label sections.
            sections: list[str] = []

            for field_name in [
                "indications_and_usage",
                "warnings",
                "warnings_and_cautions",
                "adverse_reactions",
                "contraindications",
                "drug_interactions",
                "boxed_warning",
            ]:
                values = result.get(field_name, [])
                if values:
                    # Each field is a list of strings.
                    section_text = " ".join(values)
                    sections.append(f"[{field_name.upper()}] {section_text}")

            combined_text = " ".join(sections).strip()
            if not combined_text:
                continue

            # Extract drug name from openfda metadata.
            openfda = result.get("openfda", {})
            brand_names = openfda.get("brand_name", [])
            generic_names = openfda.get("generic_name", [])
            drug_name = (brand_names[0] if brand_names
                         else generic_names[0] if generic_names
                         else "Unknown Drug")

            # Build a URL pointing to DailyMed if an SPL ID is available.
            spl_ids = openfda.get("spl_id", [])
            url = (f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={spl_ids[0]}"
                   if spl_ids
                   else "https://open.fda.gov/")

            items.append(
                RawEvidenceItem(
                    text=combined_text[:3000],  # Truncate very long labels
                    title=f"FDA Label: {drug_name}",
                    publisher="openFDA",
                    url=url,
                    metadata={
                        "brand_name": brand_names[0] if brand_names else "",
                        "generic_name": generic_names[0] if generic_names else "",
                    },
                )
            )

        return items
