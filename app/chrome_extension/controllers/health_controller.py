"""
routers/health.py — Health Check Endpoint
=========================================
"""

from fastapi import APIRouter

from app.shared.models.schemas import HealthStatus

router = APIRouter()

@router.get("/health", response_model=HealthStatus, tags=["System"])
async def health_check():
    """Verify that the API is running."""
    return HealthStatus(status="ok", version="1.0.0")
