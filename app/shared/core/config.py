"""
config.py — Central Settings Loader
====================================
This file uses pydantic-settings to load all API keys and configuration
values from the .env file.  Every other file in the project imports settings
from here instead of reading environment variables directly.

How it works:
  1. Pydantic reads the .env file automatically.
  2. Each variable becomes a typed Python attribute (str, int, float).
  3. If a required key is missing, the app crashes on startup with a clear
     error message — so you catch configuration problems immediately.

Usage in any other file:
    from app.shared.core.config import settings
    print(settings.tavily_api_key)
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration values for the RX Evidence Engine."""

    # ── Where to find the .env file ──
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unexpected variables in .env
    )

    # ── Medical Data API Keys ──
    tavily_api_key: str = ""
    pubmed_api_key: str = ""
    openfda_api_key: str = ""
    semantic_scholar_api_key: str = ""
    openalex_api_key: str = ""

    # ── LLM Provider Keys ──
    openrouter_api_key: str = ""

    # ── LLM Configuration ──
    llm_model_low: str
    llm_model_medium: str
    llm_model_high: str
    llm_temperature: float = 0.1             # Low = more factual, less creative
    llm_max_tokens: int = 512                # Max tokens in LLM response



    # ── RAG Configuration ──
    chunk_size: int = 200                    # Words per chunk
    chunk_overlap: int = 30                  # Overlapping words between chunks
    top_k: int = 5                           # Number of top matches to retrieve

    # ── Provider Configuration ──
    provider_timeout: float = 4.0             # Seconds before API call times out
    provider_cache_ttl: int = 300             # Seconds to cache successful API calls
    fetch_deadline: float = 2.5               # Soft deadline for fetching evidence
    
    # ── Database Configuration ──
    mongodb_uri: str
    mongodb_db_name: str

    # ── Auth Configuration ──
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days
    cors_allowed_origin: str = "http://localhost:3000"
    cookie_secure: bool = False  # set True once served over HTTPS in production


# ── Single global instance used everywhere ──
settings = Settings()
