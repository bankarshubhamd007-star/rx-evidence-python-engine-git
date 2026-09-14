import json
import logging
from app.shared.core.cache import feedback_link_cache, claims_cache
from app.shared.repositories.feedback_repository import feedback_repo
from app.shared.repositories.mongo_repository import MongoRepository
from app.shared.repositories.semantic_cache_repository import semantic_cache_repo

logger = logging.getLogger(__name__)

class FeedbackService:
    @staticmethod
    async def submit(analysis_id: str, vote: str, reason: str | None = None) -> None:
        """
        Process a user's feedback vote.
        Saves to persistent ChromaDB and updates MongoDB counts.
        """
        cached_json = feedback_link_cache.get(analysis_id)
        if not cached_json:
            # Fallback to MongoDB
            db_result = await MongoRepository.get_analysis(analysis_id)
            if not db_result:
                logger.warning(f"Could not find analysis_id {analysis_id} in cache or DB. Feedback not saved.")
                return
            cached_json = db_result.model_dump_json()
            feedback_link_cache[analysis_id] = cached_json
            
        try:
            data = json.loads(cached_json)
            claim = data.get("claim")
            
            if claim:
                feedback_repo.save_feedback(
                    claim=claim,
                    response_json=cached_json,
                    vote=vote,
                    analysis_id=analysis_id,
                    reason=reason
                )
                
                # Map vote and update MongoDB synchronously to get the threshold result
                mapped_vote = "positive" if vote == "helpful" else "negative"
                should_invalidate = await MongoRepository.update_feedback(analysis_id, mapped_vote)
                
                # If the negative feedback threshold (>30%) is reached, remove it from all caches
                if should_invalidate:
                    try:
                        del feedback_link_cache[analysis_id]
                    except KeyError:
                        pass
                    
                    cache_key = claim.lower()
                    if cache_key in claims_cache:
                        del claims_cache[cache_key]
                        logger.info(f"Removed claim '{claim}' from exact-match CACHE due to negative feedback threshold.")
                        
                    semantic_cache_repo.delete_claim(analysis_id)
                    logger.info(f"Removed claim '{claim}' from semantic index due to negative feedback threshold.")
        except Exception as e:
            logger.error(f"Failed to process feedback for {analysis_id}: {e}")
