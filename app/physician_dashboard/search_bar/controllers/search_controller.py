from fastapi import APIRouter, HTTPException, BackgroundTasks
import logging

from app.shared.models.schemas import AnalyzeRequest, AnalysisResult
from app.shared.services.analysis_service import AnalysisService
from app.shared.core.engine import get_evidence_engine

logger = logging.getLogger(__name__)
router = APIRouter()

# Use singleton engine to avoid loading ML models multiple times
engine = get_evidence_engine()

@router.post("/analyze", response_model=AnalysisResult)
async def analyze_claim_for_dashboard(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Analyze a medical claim from the Physician Dashboard search bar.
    """
    claim = req.claim.strip()
    if not claim:
        raise HTTPException(status_code=400, detail="Claim cannot be empty")
        
    try:
        return await AnalysisService.analyze(claim, background_tasks, engine, accuracy_level=req.accuracy_level)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
