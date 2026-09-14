from fastapi import APIRouter
from app.shared.models.schemas import FeedbackAck, FeedbackRequest
from app.shared.services.feedback_service import FeedbackService

router = APIRouter()

@router.post("", response_model=FeedbackAck)
async def submit_feedback(feedback: FeedbackRequest):
    """
    Accept helpful/not helpful votes from the extension.
    Saves the feedback to the persistent ChromaDB for dynamic few-shot prompting.
    """
    await FeedbackService.submit(
        analysis_id=feedback.analysis_id,
        vote=feedback.vote.value,
        reason=feedback.reason
    )
    return FeedbackAck()
