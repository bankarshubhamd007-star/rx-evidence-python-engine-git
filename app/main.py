"""
app.py — FastAPI Application Entrypoint
=======================================
This file initializes the FastAPI application, configures CORS
(to allow the Chrome Extension to talk to it), and includes all routers.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import http_client
from app.shared.core.config import settings
from app.shared.core.vector_store import warm_models
from app.shared.repositories.user_repository import UserRepository
from app.auth.controllers import auth_controller
from app.chrome_extension.controllers import claims_controller, feedback_controller, health_controller

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared HTTP client with connection pooling
    http_client.client = httpx.AsyncClient(
        limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
    )
    # Enforce email uniqueness at the database level
    await UserRepository.ensure_indexes()
    # Warm up ML models (SentenceTransformer, CrossEncoder, etc)
    warm_models()

    yield
    
    # Teardown
    if http_client.client:
        await http_client.client.aclose()

# Configure basic logging with a clean, understandable format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S"
)

# Suppress noisy logs from third-party libraries so only our clean logs show
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("primp").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING) # Just in case
app = FastAPI(
    title="RX Evidence Engine API",
    description="Medical Claim Verification powered by Vector RAG and Gemini 2.5 Flash",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for the Chrome Extension and the physician dashboard frontend.
# allow_credentials=True cannot pair with a wildcard origin, so the frontend
# gets an explicit allowed origin. The extension is matched by ID format
# (32 lowercase a-p characters, per Chrome's extension ID scheme) rather
# than a fully open `.*`, which would let *any* installed extension request
# credentialed cross-origin access. The session cookie is also SameSite=Lax,
# so it's not attached to cross-site fetches from the extension anyway —
# this regex is defense-in-depth, not the only thing standing between the
# extension origin and the session cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_allowed_origin],
    allow_origin_regex=r"chrome-extension://[a-p]{32}$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_controller.router, prefix="/v1/auth", tags=["Auth"])
app.include_router(health_controller.router, prefix="/v1")
app.include_router(claims_controller.router, prefix="/v1/claims", tags=["Claims"])
app.include_router(feedback_controller.router, prefix="/v1/feedback", tags=["Feedback"])

# Physician Dashboard Routers
from app.physician_dashboard.search_bar.controllers import search_controller, feedback_controller as dashboard_feedback_controller
from app.physician_dashboard.trends.controllers import trends_controller
from app.physician_dashboard.appointments.controllers import appointment_controller

app.include_router(search_controller.router, prefix="/v1/physician-dashboard/search-bar", tags=["Physician Dashboard"])
app.include_router(dashboard_feedback_controller.router, prefix="/v1/physician-dashboard/search-bar/feedback", tags=["Physician Dashboard"])
app.include_router(trends_controller.router, prefix="/v1/physician-dashboard/trends", tags=["Physician Dashboard Trends"])
app.include_router(appointment_controller.router)
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def read_root():
    return RedirectResponse(url="/docs")

def main():
    """Entrypoint for the uv script."""
    workers = int(os.getenv("UVICORN_WORKERS", "1"))
    port = int(os.getenv("PORT", 8000))
    # Disable reload by default in production; WatchFiles can break in container environments
    reload_mode = os.getenv("ENVIRONMENT", "production") == "development"
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload_mode, workers=workers)

if __name__ == "__main__":
    main()
