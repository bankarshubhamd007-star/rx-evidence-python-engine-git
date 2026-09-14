"""
db/claim_index.py — Semantic Claim Indexing for Deduplication
=============================================================
This module uses ChromaDB to persistently index claims, allowing us to find
semantically identical claims (e.g. "Cortisol is why you can't lose belly fat"
vs "High cortisol is the reason you're unable to lose belly fat") to avoid
re-analyzing and to aggregate them in MongoDB.
"""

import logging
import os
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class SemanticCacheRepository:
    def __init__(self, persist_directory: str = ".chroma"):
        self.persist_directory = os.path.abspath(persist_directory)
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Use PersistentClient to save to disk
        self.client = chromadb.PersistentClient(
            path=self.persist_directory, 
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        # Create or get collection for claim deduplication
        self.collection = self.client.get_or_create_collection(
            name="semantic_claim_index",
            metadata={"hnsw:space": "cosine"} # Use cosine similarity
        )
        logger.info(f"[ClaimIndex] Initialized at {self.persist_directory} with {self.collection.count()} items.")

    def add_claim(self, claim: str, mongo_id: str):
        """
        Add a newly analyzed claim to the index, pointing to its MongoDB ID.
        """
        self.collection.add(
            documents=[claim],
            metadatas=[{"mongo_id": mongo_id}],
            ids=[mongo_id]
        )
        logger.info(f"[ClaimIndex] Indexed claim '{claim}' with ID {mongo_id}")

    def update_claim_id(self, old_id: str, new_mongo_id: str):
        """
        Updates the metadata for an existing claim to point to a new MongoDB ID.
        Useful for migrating from an 'inflight_' temporary ID to a real ID.
        """
        self.collection.update(
            ids=[old_id],
            metadatas=[{"mongo_id": new_mongo_id}]
        )
        logger.info(f"[ClaimIndex] Updated claim ID from {old_id} to {new_mongo_id}")
        
    def delete_claim(self, claim_id: str):
        """
        Deletes a claim from the index.
        """
        self.collection.delete(ids=[claim_id])
        logger.info(f"[ClaimIndex] Deleted claim ID {claim_id}")

    def find_similar_claim(self, query_claim: str, distance_threshold: float = 0.4) -> Optional[str]:
        """
        Retrieve a similar past claim. If found (distance < threshold),
        returns its MongoDB ID. Otherwise returns None.
        """
        if self.collection.count() == 0:
            return None

        # Chroma's cosine distance: 0 is exact match, 1 is orthogonal
        results = self.collection.query(
            query_texts=[query_claim],
            n_results=1
        )
        
        if results and results.get("documents") and results["documents"][0]:
            distances = results["distances"][0] if results.get("distances") else [0]
            metadatas = results["metadatas"][0]
            
            if distances and distances[0] < distance_threshold:
                mongo_id = metadatas[0].get("mongo_id")
                logger.info(f"[ClaimIndex] Found similar claim for '{query_claim}' (distance: {distances[0]:.3f}) -> ID: {mongo_id}")
                return mongo_id
                
        return None

# Global instance
semantic_cache_repo = SemanticCacheRepository()
