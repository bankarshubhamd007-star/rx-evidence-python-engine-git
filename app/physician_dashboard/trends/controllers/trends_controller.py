from fastapi import APIRouter, HTTPException
import logging

from app.shared.repositories.mongo_repository import MongoRepository
from app.shared.models.schemas import TrendResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/top", response_model=list[TrendResponse])
async def get_top_trends(limit: int = 10):
    """
    Get top trending viral misinformation claims.
    """
    try:
        trends = await MongoRepository.get_top_trends(limit=limit)
        results = []
        for doc in trends:
            results.append(TrendResponse(
                id=doc["id"],
                claim=doc["claim"],
                confidence=doc["confidence"],
                is_accurate=doc.get("is_accurate", False),
                summary=doc["summary"],
                key_points=doc["key_points"],
                evidence=doc.get("evidence", []),
                created_at=doc["created_at"],
                count=doc.get("count", 0)
            ))
        return results
    except Exception as e:
        logger.error(f"[TrendsController] Failed to fetch top trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all", response_model=list[TrendResponse])
async def get_all_claims(limit: int = 50):
    """
    Get all analyzed claims ordered by recency.
    """
    try:
        claims = await MongoRepository.get_all_claims(limit=limit)
        results = []
        for doc in claims:
            results.append(TrendResponse(
                id=doc["id"],
                claim=doc["claim"],
                confidence=doc["confidence"],
                is_accurate=doc.get("is_accurate", False),
                summary=doc["summary"],
                key_points=doc["key_points"],
                evidence=doc.get("evidence", []),
                created_at=doc["created_at"],
                count=doc.get("count", 0)
            ))
        return results
    except Exception as e:
        logger.error(f"[TrendsController] Failed to fetch all claims: {e}")
        raise HTTPException(status_code=500, detail=str(e))
