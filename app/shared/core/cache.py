"""
cache.py — Centralized Cache Management
=======================================
Provides strictly bounded, in-memory TTL caches to prevent memory leaks.
"""

from cachetools import TTLCache

from app.shared.models.schemas import AnalysisResult

# Cache for exact match claims (TTL: 24 hours). Avoids running the pipeline for duplicate queries.
claims_cache: TTLCache[str, AnalysisResult] = TTLCache(maxsize=10000, ttl=86400)

# Cache mapping analysis ID to response JSON for feedback linking (TTL: 24 hours).
feedback_link_cache: TTLCache[str, str] = TTLCache(maxsize=10000, ttl=86400)
