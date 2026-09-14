"""
providers/__init__.py — Medical Evidence API Providers Package
================================================================
This package contains async HTTP connectors to live medical databases
and search APIs.  Each provider fetches raw evidence from a different
source, all sharing the same RawEvidenceItem output format.

Available providers:
  - TavilyProvider:           Society guideline search (ADA, AHA, CDC, WHO)
  - PubMedProvider:           NCBI E-Utilities (PubMed abstracts)
  - OpenFDAProvider:          FDA drug labels & safety warnings
  - SemanticScholarProvider:  Semantic Scholar paper search
  - OpenAlexProvider:         OpenAlex open-access paper search
  - EuropePMCProvider:        Europe PMC clinical article search
  - ClinicalTrialsProvider:   ClinicalTrials.gov study records
"""

from .base import BaseProvider, RawEvidenceItem
from .ddg_provider import DDGProvider
from .pubmed_provider import PubMedProvider
from .openfda_provider import OpenFDAProvider
from .openalex_provider import OpenAlexProvider
from .europe_pmc_provider import EuropePMCProvider
from .clinical_trials_provider import ClinicalTrialsProvider

ALL_PROVIDERS: list[type[BaseProvider]] = [
    DDGProvider,
    PubMedProvider,
    OpenFDAProvider,
    OpenAlexProvider,
    EuropePMCProvider,
    ClinicalTrialsProvider,
]

__all__ = [
    "BaseProvider",
    "RawEvidenceItem",
    "DDGProvider",
    "PubMedProvider",
    "OpenFDAProvider",
    "OpenAlexProvider",
    "EuropePMCProvider",
    "ClinicalTrialsProvider",
    "ALL_PROVIDERS",
]
