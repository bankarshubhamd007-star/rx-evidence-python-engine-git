import logging
from pymongo import ReturnDocument
from app.shared.core.config import settings
from app.shared.models.schemas import AnalysisResult, EvidenceSource
from app.shared.database.mongo import get_mongo_client

logger = logging.getLogger(__name__)

class MongoRepository:
    @staticmethod
    async def save_analysis(result: AnalysisResult, user_id: str | None = None) -> None:
        """
        Saves the AnalysisResult securely to the 'chrome-extension' collection.
        Strictly isolated to avoid touching any other collections.
        """
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["chrome-extension"]
            
            document = {
                "id": result.id,
                "claim": result.claim,
                "confidence": result.confidence,
                "summary": result.summary,
                "key_points": result.key_points,
                "evidence": [ev.model_dump() for ev in result.evidence],
                "created_at": result.created_at,
                "accuracy_level": getattr(result, "accuracy_level", "medium"),
            }
            
            await collection.update_one(
                {"id": result.id},
                {
                    "$set": document,
                    "$setOnInsert": {
                        "count": 1,
                        "feedback": {
                            "positive": 0,
                            "negative": 0,
                            "none": 1
                        }
                    }
                },
                upsert=True
            )
            logger.info(f"[MongoRepository] Successfully saved analysis result {result.id} to chrome-extension collection.")
            
            if user_id:
                await MongoRepository.save_user_claim(user_id, result.id)
                
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to save analysis result to MongoDB: {e}")

    @staticmethod
    async def save_user_claim(user_id: str, claim_id: str) -> None:
        """Saves the relationship between a user and a claim they analyzed."""
        try:
            import time
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["user_claims"]
            
            document = {
                "user_id": user_id,
                "claim_id": claim_id,
                "created_at": time.time()
            }
            # Use upsert to avoid duplicate entries for the same user and claim
            await collection.update_one(
                {"user_id": user_id, "claim_id": claim_id},
                {"$set": document},
                upsert=True
            )
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to save user claim to MongoDB: {e}")

    @staticmethod
    async def get_user_claims(user_id: str, limit: int = 50) -> list[AnalysisResult]:
        """Fetches historical claims analyzed by a specific user."""
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            user_claims_coll = db["user_claims"]
            
            # Find claim IDs for the user
            cursor = user_claims_coll.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
            claim_ids = []
            async for doc in cursor:
                claim_ids.append(doc["claim_id"])
                
            if not claim_ids:
                return []
                
            # Fetch the actual AnalysisResult docs
            claims_coll = db["chrome-extension"]
            claims_cursor = claims_coll.find({"id": {"$in": claim_ids}})
            
            # Create a dictionary to map results back to ordered list
            claims_dict = {}
            async for doc in claims_cursor:
                evidence_items = []
                for ev in doc.get("evidence", []):
                    evidence_items.append(EvidenceSource(**ev))
                    
                claims_dict[doc["id"]] = AnalysisResult(
                    id=doc["id"],
                    claim=doc["claim"],
                    confidence=doc["confidence"],
                    is_accurate=doc.get("is_accurate", False),
                    summary=doc["summary"],
                    key_points=doc["key_points"],
                    evidence=evidence_items,
                    created_at=doc["created_at"]
                )
                
            # Return in the original sorted order
            return [claims_dict[cid] for cid in claim_ids if cid in claims_dict]
            
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to get user claims: {e}")
            return []

    @staticmethod
    async def increment_count(mongo_id: str) -> None:
        """
        Increments the count of a claim and its 'none' feedback count.
        """
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["chrome-extension"]
            await collection.update_one(
                {"id": mongo_id},
                {"$inc": {"count": 1, "feedback.none": 1}}
            )
            logger.info(f"[MongoRepository] Incremented count for claim ID: {mongo_id}")
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to increment count for {mongo_id}: {e}")

    @staticmethod
    async def update_feedback(mongo_id: str, vote: str) -> bool:
        """
        Updates feedback counts for a claim.
        vote should be 'positive' or 'negative'.
        Returns True if the negative feedback exceeds 30% of the total count.
        """
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["chrome-extension"]
            
            updated_doc = await collection.find_one_and_update(
                {"id": mongo_id},
                {"$inc": {f"feedback.{vote}": 1, "feedback.none": -1}},
                return_document=ReturnDocument.AFTER
            )
            logger.info(f"[MongoRepository] Updated feedback '{vote}' for claim ID: {mongo_id}")
            
            if updated_doc:
                count = updated_doc.get("count", 1)
                feedback = updated_doc.get("feedback", {})
                negative = feedback.get("negative", 0)
                
                if (negative / max(1, count)) > 0.3:
                    return True
            return False
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to update feedback for {mongo_id}: {e}")
            return False

    @staticmethod
    async def get_analysis(mongo_id: str) -> AnalysisResult | None:
        """
        Retrieves an AnalysisResult by its ID from MongoDB.
        """
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["chrome-extension"]
            
            doc = await collection.find_one({"id": mongo_id})
            if doc:
                count = doc.get("count", 1)
                feedback = doc.get("feedback", {})
                negative = feedback.get("negative", 0)
                if (negative / max(1, count)) > 0.3:
                    logger.warning(f"[MongoRepository] Claim {mongo_id} has >30% negative feedback. Ignoring cache.")
                    try:
                        from app.shared.repositories.semantic_cache_repository import semantic_cache_repo
                        semantic_cache_repo.delete_claim(mongo_id)
                    except Exception as e:
                        pass
                    return None

                evidence_items = []
                for ev in doc.get("evidence", []):
                    evidence_items.append(EvidenceSource(**ev))
                    
                return AnalysisResult(
                    id=doc["id"],
                    claim=doc["claim"],
                    confidence=doc["confidence"],
                    is_accurate=doc.get("is_accurate", False),
                    summary=doc["summary"],
                    key_points=doc["key_points"],
                    evidence=evidence_items,
                    created_at=doc["created_at"]
                )
            return None
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to get analysis by id {mongo_id}: {e}")
            return None

    @staticmethod
    async def get_top_trends(limit: int = 10) -> list[dict]:
        """
        Retrieves top trends based on count.
        """
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["chrome-extension"]
            
            cursor = collection.find({}).sort("count", -1).limit(limit)
            results = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to get top trends: {e}")
            return []

    @staticmethod
    async def get_all_claims(limit: int = 50) -> list[dict]:
        """
        Retrieves all claims sorted by recency.
        """
        try:
            client = get_mongo_client()
            db = client[settings.mongodb_db_name]
            collection = db["chrome-extension"]
            
            cursor = collection.find({}).sort("created_at", -1).limit(limit)
            results = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                results.append(doc)
            return results
        except Exception as e:
            logger.error(f"[MongoRepository] Failed to get all claims: {e}")
            return []
