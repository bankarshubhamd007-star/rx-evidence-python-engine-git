"""
http_client.py — Shared HTTP Client
====================================
Provides a single, process-wide httpx.AsyncClient instance.
Connection pooling avoids TLS/TCP overhead for every API call.
"""

from __future__ import annotations

import httpx

# We will initialize this in the FastAPI lifespan
client: httpx.AsyncClient | None = None

def get_client() -> httpx.AsyncClient:
    """Return the shared HTTP client. Raises RuntimeError if not initialized."""
    global client
    if client is None:
        raise RuntimeError("httpx.AsyncClient is not initialized. Check app lifespan.")
    return client
