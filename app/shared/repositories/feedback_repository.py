"""
db/feedback_repo.py — Persistent Vector Store for Feedback
===========================================================
This module uses ChromaDB to persistently store user feedback (thumbs up / thumbs down)
on the local disk. It provides a quick similarity search to fetch past highly relevant
feedback during LLM synthesis.
"""

import logging
import os
import uuid
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class FeedbackRepository:
    def __init__(self, persist_directory: str = ".chroma"):
        self.persist_directory = os.path.abspath(persist_directory)
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Use PersistentClient to save to disk
        self.client = chromadb.PersistentClient(
            path=self.persist_directory, 
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name="claim_feedback",
            metadata={"hnsw:space": "cosine"} # Use cosine similarity
        )
        logger.info(f"[FeedbackRepository] Initialized at {self.persist_directory} with {self.collection.count()} items.")

    def save_feedback(self, claim: str, response_json: str, vote: str, analysis_id: str, reason: str | None = None):
        """
        Save or update feedback for an analysis result to the persistent vector store.
        Uses analysis_id as the document ID to prevent duplicate feedback entries.
        """
        
        metadata = {
            "response": response_json,
            "vote": vote,
        }
        if reason:
            metadata["reason"] = reason

        self.collection.upsert(
            documents=[claim],
            metadatas=[metadata],
            ids=[analysis_id]
        )
        logger.info(f"[FeedbackRepository] Saved '{vote}' feedback for claim: '{claim}'")

    def get_similar_feedback(self, query_claim: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieve similar past claims with their feedback.
        Returns a list of dicts: [{"claim": ..., "response": ..., "vote": ..., "reason": ...}]
        """
        if self.collection.count() == 0:
            return []

        # Chroma's cosine distance: 0 is exact match, 1 is orthogonal
        results = self.collection.query(
            query_texts=[query_claim],
            n_results=min(top_k, self.collection.count())
        )
        
        feedback_items = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if results.get("distances") else [0]*len(docs)
            
            for doc, meta, dist in zip(docs, metadatas, distances):
                # distance < 0.4 implies high similarity (cosine similarity > 0.6)
                if dist < 0.4:
                    item = {
                        "claim": doc,
                        "response": meta.get("response", ""),
                        "vote": meta.get("vote", ""),
                        "reason": meta.get("reason", ""),
                        "distance": dist
                    }
                    feedback_items.append(item)
                    
        return feedback_items

# Global instance
feedback_repo = FeedbackRepository()
