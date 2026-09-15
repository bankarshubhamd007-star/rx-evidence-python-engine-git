from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
import uuid
import time
import datetime
import logging

from app.auth.dependencies import get_current_user_optional
from app.shared.models.schemas import AnalyzeRequest, AnalysisResult, BatchAnalyzeRequest, BatchAnalyzeResponse, UserPublic
from app.shared.services.analysis_service import AnalysisService
from app.shared.core.engine import get_evidence_engine
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

# Use singleton engine to avoid loading ML models multiple times
engine = get_evidence_engine()

@router.post("/analyze", response_model=AnalysisResult)
async def analyze_claim(
    req: AnalyzeRequest, 
    background_tasks: BackgroundTasks,
    current_user: UserPublic | None = Depends(get_current_user_optional)
):
    """
    Analyze a medical claim using the Vector RAG pipeline.
    """
    claim = req.claim.strip()
    if not claim:
        raise HTTPException(status_code=400, detail="Claim cannot be empty")
        
    try:
        user_id = current_user.id if current_user else None
        return await AnalysisService.analyze(claim, background_tasks, engine, user_id=user_id, accuracy_level=req.accuracy_level)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/batch", response_model=BatchAnalyzeResponse)
async def analyze_claims_batch(
    req: BatchAnalyzeRequest, 
    background_tasks: BackgroundTasks,
    current_user: UserPublic | None = Depends(get_current_user_optional)
):
    """
    Analyze multiple medical claims in parallel.
    De-duplicates claims to avoid redundant work.
    """
    if not req.claims:
        raise HTTPException(status_code=400, detail="Claims list cannot be empty")

    unique_claims = list(set(c.strip() for c in req.claims if c.strip()))
    
    if not unique_claims:
        raise HTTPException(status_code=400, detail="No valid claims provided")
        
    user_id = current_user.id if current_user else None
        
    async def process_claim(claim: str) -> AnalysisResult:
        try:
            return await AnalysisService.analyze(claim, background_tasks, engine, user_id=user_id, accuracy_level=req.accuracy_level)
        except Exception as e:
            logger.error(f"Failed to analyze claim '{claim}' (batch): {e}")
            return AnalysisResult(
                id=uuid.uuid4().hex,
                claim=claim,
                confidence=0.0,
                is_accurate=False,
                summary=f"Analysis failed: {str(e)}",
                key_points=["Error during processing."],
                evidence=[],
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )

    results = await asyncio.gather(*[process_claim(c) for c in unique_claims])
    
    return BatchAnalyzeResponse(results=list(results))
