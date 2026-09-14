import asyncio
import logging
import uuid
import time
from fastapi import BackgroundTasks

from app.shared.models.schemas import AnalysisResult
from app.shared.core.cache import claims_cache
from app.shared.core.engine import EvidenceEngine
from app.shared.repositories.semantic_cache_repository import semantic_cache_repo
from app.shared.repositories.mongo_repository import MongoRepository

logger = logging.getLogger(__name__)

# Global dictionary to hold in-flight analysis futures
in_flight_tasks = {}

class AnalysisService:
    @staticmethod
<<<<<<< HEAD
    async def analyze(claim: str, background_tasks: BackgroundTasks, engine: EvidenceEngine, user_id: str | None = None, accuracy_level: str = "medium") -> AnalysisResult:
        cache_key = claim.lower()
        if cache_key in claims_cache:
            logger.info(f"Cache hit for claim: {claim}")
            cached_result = claims_cache[cache_key]
            # feedback_link_cache is updated via a separate service if needed, 
            # but for now we'll import it or handle it in feedback service.
            from app.shared.core.cache import feedback_link_cache
            feedback_link_cache[cached_result.id] = cached_result.model_dump_json()
            
            if user_id:
                background_tasks.add_task(MongoRepository.save_user_claim, user_id, cached_result.id)
                
            return cached_result
=======
    def _is_sufficient_accuracy(cached_level: str, requested_level: str) -> bool:
        levels = {"low": 1, "medium": 2, "high": 3}
        return levels.get(cached_level, 2) >= levels.get(requested_level, 2)

    @staticmethod
    async def analyze(claim: str, background_tasks: BackgroundTasks, engine: EvidenceEngine, user_id: str | None = None, accuracy_level: str = "medium") -> AnalysisResult:
        cache_key = claim.lower()
        old_cached_result = None

        if cache_key in claims_cache:
            cached_result = claims_cache[cache_key]
            if AnalysisService._is_sufficient_accuracy(getattr(cached_result, "accuracy_level", "medium"), accuracy_level):
                logger.info(f"Cache hit for claim: {claim} with sufficient accuracy.")
                from app.shared.core.cache import feedback_link_cache
                feedback_link_cache[cached_result.id] = cached_result.model_dump_json()
                if user_id:
                    background_tasks.add_task(MongoRepository.save_user_claim, user_id, cached_result.id)
                return cached_result
            else:
                logger.info(f"Cache hit for claim: {claim} but insufficient accuracy. Requested: {accuracy_level}. Regenerating.")
                old_cached_result = cached_result
>>>>>>> python-engine

        # Check semantic cache
        similar_mongo_id = semantic_cache_repo.find_similar_claim(claim)
        if similar_mongo_id:
            if similar_mongo_id.startswith("inflight_"):
                logger.info(f"Waiting for in-flight semantic claim for: {claim}")
                try:
                    cached_result = await in_flight_tasks[similar_mongo_id]
<<<<<<< HEAD
                    logger.info(f"In-flight semantic cache hit for claim: {claim}")
                    claims_cache[cache_key] = cached_result
                    from app.shared.core.cache import feedback_link_cache
                    feedback_link_cache[cached_result.id] = cached_result.model_dump_json()
                    background_tasks.add_task(MongoRepository.increment_count, cached_result.id)
                    
                    if user_id:
                        background_tasks.add_task(MongoRepository.save_user_claim, user_id, cached_result.id)
                        
                    return cached_result
=======
                    if AnalysisService._is_sufficient_accuracy(getattr(cached_result, "accuracy_level", "medium"), accuracy_level):
                        logger.info(f"In-flight semantic cache hit for claim: {claim}")
                        claims_cache[cache_key] = cached_result
                        from app.shared.core.cache import feedback_link_cache
                        feedback_link_cache[cached_result.id] = cached_result.model_dump_json()
                        background_tasks.add_task(MongoRepository.increment_count, cached_result.id)
                        if user_id:
                            background_tasks.add_task(MongoRepository.save_user_claim, user_id, cached_result.id)
                        return cached_result
                    else:
                        old_cached_result = cached_result
>>>>>>> python-engine
                except Exception as e:
                    logger.warning(f"In-flight task failed or not found: {e}. Proceeding with analysis.")
            else:
                cached_result = await MongoRepository.get_analysis(similar_mongo_id)
                if cached_result:
<<<<<<< HEAD
                    logger.info(f"Semantic cache hit for claim: {claim}")
                    claims_cache[cache_key] = cached_result
                    from app.shared.core.cache import feedback_link_cache
                    feedback_link_cache[cached_result.id] = cached_result.model_dump_json()
                    background_tasks.add_task(MongoRepository.increment_count, similar_mongo_id)
                    
                    if user_id:
                        background_tasks.add_task(MongoRepository.save_user_claim, user_id, cached_result.id)
                        
                    return cached_result

        logger.info(f"Processing new claim: {claim}")
=======
                    if AnalysisService._is_sufficient_accuracy(getattr(cached_result, "accuracy_level", "medium"), accuracy_level):
                        logger.info(f"Semantic cache hit for claim: {claim}")
                        claims_cache[cache_key] = cached_result
                        from app.shared.core.cache import feedback_link_cache
                        feedback_link_cache[cached_result.id] = cached_result.model_dump_json()
                        background_tasks.add_task(MongoRepository.increment_count, similar_mongo_id)
                        if user_id:
                            background_tasks.add_task(MongoRepository.save_user_claim, user_id, cached_result.id)
                        return cached_result
                    else:
                        old_cached_result = cached_result

        logger.info(f"Processing new claim: {claim} at accuracy level: {accuracy_level}")
>>>>>>> python-engine
        
        inflight_id = f"inflight_{uuid.uuid4().hex}"
        future = asyncio.Future()
        in_flight_tasks[inflight_id] = future
        
        # Add to semantic index so concurrent tasks can find it
        semantic_cache_repo.add_claim(claim, inflight_id)
        
        try:
            result = await engine.analyze(claim, accuracy_level)
            
<<<<<<< HEAD
=======
            if old_cached_result:
                # Steal the ID from the old cached result to overwrite it in MongoDB smoothly
                result.id = old_cached_result.id
            
>>>>>>> python-engine
            # Cache the successful result
            claims_cache[cache_key] = result
            
            # Update semantic index to real ID
            semantic_cache_repo.delete_claim(inflight_id)
            semantic_cache_repo.add_claim(claim, result.id)
            
            # Save to MongoDB in the background
            background_tasks.add_task(MongoRepository.save_analysis, result, user_id)
            
            future.set_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze claim '{claim}': {e}", exc_info=True)
            semantic_cache_repo.delete_claim(inflight_id)
            future.set_exception(e)
            raise
        finally:
            if inflight_id in in_flight_tasks:
                del in_flight_tasks[inflight_id]
