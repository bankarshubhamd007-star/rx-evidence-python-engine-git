"""
pipeline/engine.py — The Master Coordinator
===================================================
This module coordinates the entire lifecycle of a claim analysis:
  1. Fetch raw evidence from all APIs in parallel.
  2. Stream chunks into the VectorStore as they arrive.
  3. Short-circuit if high-quality evidence is found early.
  4. Search the vector store for the top K most relevant chunks.
  5. Pass the top K chunks to Gemini 2.5 Flash (Synthesizer) to get the final JSON.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from app.shared.core.cache import feedback_link_cache
from app.shared.core.config import settings
from app.shared.models.schemas import AnalysisResult
from app.providers import ALL_PROVIDERS, BaseProvider, RawEvidenceItem
from app.shared.core.chunker import SemanticChunker
from app.shared.core.nlp import extract_search_keywords
from app.shared.core.vector_store import VectorStore
from app.shared.repositories.feedback_repository import feedback_repo
from .synthesizer import LLMSynthesizer

logger = logging.getLogger(__name__)


class EvidenceEngine:
    """End-to-end evidence gathering and synthesis pipeline."""

    def __init__(self) -> None:
        self.providers: list[BaseProvider] = [provider_cls() for provider_cls in ALL_PROVIDERS]
        self.chunker = SemanticChunker(
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap
        )
        self.synthesizer = LLMSynthesizer()

    async def fetch_all_evidence(self, claim: str) -> list[RawEvidenceItem]:
        """Legacy helper. Kept for backwards compatibility if needed, but streaming is preferred."""
        search_query = extract_search_keywords(claim)
        tasks = [provider.safe_fetch(search_query) for provider in self.providers]
        done, _ = await asyncio.wait(tasks, timeout=settings.fetch_deadline)
        items = []
        for task in done:
            items.extend(task.result())
        return items

    async def analyze(self, claim: str, accuracy_level: str = "medium") -> AnalysisResult:
        """
        Run the complete pipeline for a given medical claim with streaming and early exit.
        """
        vector_store = VectorStore()
        t0 = time.time()
        
        logger.info(f"[Pipeline] Analyzing claim: '{claim}' across {len(self.providers)} providers...")
        
        # 0. Semantic Caching (Early Exit for Thumbs Up)
        try:
            similar_claims = feedback_repo.get_similar_feedback(claim, top_k=1)
            if similar_claims:
                best_match = similar_claims[0]
                # Distance < 0.10 roughly equates to > 90-95% semantic match
                if best_match["distance"] < 0.10 and best_match["vote"] == "helpful":
                    logger.info(f"[Semantic Cache] HIGH SIMILARITY HIT! Distance: {best_match['distance']:.3f}. Bypassing pipeline.")
                    cached_data = json.loads(best_match["response"])
                    cached_data["id"] = uuid.uuid4().hex
                    cached_data["claim"] = claim
                    if "created_at" not in cached_data and "createdAt" not in cached_data:
                        cached_data["created_at"] = time.time()
                    
                    # Create and cache the result
                    analysis_result = AnalysisResult(**cached_data)
                    feedback_link_cache[analysis_result.id] = analysis_result.model_dump_json()
                    
                    # Return in ~0.05s
                    return analysis_result
        except Exception as e:
            logger.error(f"[Semantic Cache] Failed to check semantic cache: {e}")
        
        try:
            # Pre-process claim to extract keywords for strict external APIs
            search_query = extract_search_keywords(claim)
            or_query = " OR ".join(search_query.split())
            logger.info(f"[Pipeline] Extracted strict search query: '{or_query}'")
            
            # 1. Fetch, Chunk, and Store in Parallel (Streaming)
            tasks = []
            active_providers = self.providers
            if accuracy_level == "low":
                # Use only the two fastest providers for instant responses
                active_providers = [p for p in self.providers if p.name in ["ClinicalTrials.gov", "Europe PMC"]]

            for provider in active_providers:
                if provider.name in ["PubMed", "ClinicalTrials.gov", "Europe PMC"]:
                    tasks.append(asyncio.create_task(provider.safe_fetch(or_query)))
                else:
                    tasks.append(asyncio.create_task(provider.safe_fetch(claim)))
            pending = set(tasks)
            
            total_chunks = 0
            deadline = time.time() + settings.fetch_deadline
            
            while pending:
                timeout = max(0.01, deadline - time.time())
                done, pending = await asyncio.wait(pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
                
                if not done:
                    # Timeout reached
                    break
                    
                for task in done:
                    try:
                        raw_evidence = task.result()
                    except Exception as e:
                        logger.error(f"Provider task failed: {e}")
                        continue
                        
                    if not raw_evidence:
                        continue
                        
                    # Chunk and add immediately
                    chunks = []
                    for item in raw_evidence:
                        chunks.extend(self.chunker.chunk(
                            text=item.text,
                            title=item.title,
                            publisher=item.publisher,
                            url=item.url
                        ))
                    
                    if chunks:
                        await vector_store.add_chunks_async(chunks)
                        total_chunks += len(chunks)
                        
                # 3. Early LLM Trigger (Short-circuit)
                if total_chunks >= 3:
                    # Quick check to see if we have 3 highly confident chunks
                    top_results = await vector_store.search(claim, top_k=3)
                    high_quality = sum(1 for res in top_results if res.score > 0.8)
                    if high_quality >= 3:
                        logger.info("[Pipeline] Short-circuit threshold met! High-quality evidence found early. Triggering LLM.")
                        break

            # Cancel remaining straggler tasks
            for task in pending:
                task.cancel()

            # 4. Final Search (Retrieve top K)
            t1 = time.time()
            top_results = await vector_store.search(claim, top_k=settings.top_k)
            t2 = time.time()
            logger.info(f"[Retrieval] Vector search completed in {t2 - t1:.2f}s")

            # 5. Synthesize
            t3 = time.time()
            analysis_result = await self.synthesizer.synthesize(claim, top_results, accuracy_level)
            t4 = time.time()
            
            logger.info(f"[Pipeline] Total end-to-end time for claim: {t4 - t0:.2f}s")
            # Cache the result for potential feedback
            feedback_link_cache[analysis_result.id] = analysis_result.model_dump_json()
            
            return analysis_result
        finally:
            vector_store.clear()

# Singleton instance of EvidenceEngine
_engine_instance: EvidenceEngine | None = None

def get_evidence_engine() -> EvidenceEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EvidenceEngine()
    return _engine_instance
