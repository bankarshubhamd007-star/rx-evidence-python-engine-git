"""
rag/vector_store.py — Numpy Vector Store with Hybrid Search and Cross-Encoder Re-Ranking
========================================================================================
Replaces ChromaDB with an in-memory numpy-based vector store.
Implements:
  1. Dense retrieval (MiniLM embeddings + cosine similarity)
  2. Sparse retrieval (BM25 keyword search)
  3. Reciprocal Rank Fusion (RRF) to combine Dense and Sparse
  4. Cross-Encoder re-ranking to drastically improve precision of the top chunks.
"""

from __future__ import annotations

import asyncio
import uuid
import numpy as np
from dataclasses import dataclass
from typing import List

from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

from .chunker import EvidenceChunk


@dataclass
class SearchResult:
    """A single search result."""
    text: str
    title: str
    publisher: str
    url: str
    score: float


# Global models, loaded once per process to save memory and time
_embedder: SentenceTransformer | None = None
_reranker: CrossEncoder | None = None

def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder

def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker

def warm_models():
    """Call this during app startup to load models into memory."""
    get_embedder()
    get_reranker()


class VectorStore:
    """In-memory hybrid vector store for a single claim analysis session."""

    def __init__(self) -> None:
        self.chunks: List[EvidenceChunk] = []
        self.embeddings: np.ndarray | None = None
        self.bm25: BM25Okapi | None = None
        self.tokenized_corpus: List[List[str]] = []

    async def add_chunks_async(self, chunks: List[EvidenceChunk]) -> int:
        """Embed and store chunks. Runs in a thread to not block the event loop."""
        if not chunks:
            return 0

        self.chunks.extend(chunks)
        
        def _build_indices():
            # 1. Build dense embeddings
            texts = [c.text for c in chunks]
            embedder = get_embedder()
            new_embeddings = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            
            if self.embeddings is None:
                self.embeddings = new_embeddings
            else:
                self.embeddings = np.vstack((self.embeddings, new_embeddings))
            
            # 2. Build sparse BM25 index
            from .nlp import preprocess_text_for_bm25
            new_tokenized = [preprocess_text_for_bm25(text) for text in texts]
            self.tokenized_corpus.extend(new_tokenized)
            self.bm25 = BM25Okapi(self.tokenized_corpus)

        await asyncio.to_thread(_build_indices)
        return len(chunks)

    def add_chunks(self, chunks: List[EvidenceChunk]) -> int:
        """Synchronous version for backwards compatibility if needed."""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("Use add_chunks_async inside async functions.")
        return asyncio.run(self.add_chunks_async(chunks))

    async def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Hybrid search with cross-encoder re-ranking."""
        if not self.chunks or self.embeddings is None or self.bm25 is None:
            return []

        def _do_search():
            embedder = get_embedder()
            
            # 1. Dense Search (Cosine Similarity)
            query_vec = embedder.encode([query], convert_to_numpy=True, show_progress_bar=False)[0]
            # Normalize for cosine similarity
            norms = np.linalg.norm(self.embeddings, axis=1)
            query_norm = np.linalg.norm(query_vec)
            
            # Prevent division by zero
            valid_norms = norms > 0
            dense_scores = np.zeros(len(self.chunks))
            if query_norm > 0:
                dense_scores[valid_norms] = np.dot(self.embeddings[valid_norms], query_vec) / (norms[valid_norms] * query_norm)
            
            # 2. Sparse Search (BM25)
            from .nlp import preprocess_text_for_bm25
            tokenized_query = preprocess_text_for_bm25(query)
            sparse_scores = np.array(self.bm25.get_scores(tokenized_query))

            # 3. Reciprocal Rank Fusion (RRF)
            # Rank descending
            dense_ranks = np.argsort(dense_scores)[::-1]
            sparse_ranks = np.argsort(sparse_scores)[::-1]

            k = 60 # RRF constant
            rrf_scores = np.zeros(len(self.chunks))
            
            for rank, chunk_idx in enumerate(dense_ranks):
                rrf_scores[chunk_idx] += 1.0 / (k + rank + 1)
                
            for rank, chunk_idx in enumerate(sparse_ranks):
                rrf_scores[chunk_idx] += 1.0 / (k + rank + 1)

            # Get top N candidates for re-ranking (e.g., top 15)
            top_n = min(15, len(self.chunks))
            candidate_indices = np.argsort(rrf_scores)[::-1][:top_n]
            
            # 4. Cross-Encoder Re-Ranking
            reranker = get_reranker()
            cross_pairs = [[query, self.chunks[idx].text] for idx in candidate_indices]
            cross_scores = reranker.predict(cross_pairs)
            
            # Sort candidates by cross-encoder score
            best_order = np.argsort(cross_scores)[::-1]
            
            results = []
            for i in range(min(top_k, len(best_order))):
                best_idx = best_order[i]
                original_idx = candidate_indices[best_idx]
                chunk = self.chunks[original_idx]
                # Normalize cross score to 0-1 for compatibility (sigmoid)
                score = 1.0 / (1.0 + np.exp(-cross_scores[best_idx]))
                results.append(
                    SearchResult(
                        text=chunk.text,
                        title=chunk.title,
                        publisher=chunk.publisher,
                        url=chunk.url,
                        score=round(float(score), 4)
                    )
                )
            return results

        return await asyncio.to_thread(_do_search)

    def clear(self) -> None:
        """Clear memory."""
        self.chunks.clear()
        self.embeddings = None
        self.bm25 = None
        self.tokenized_corpus.clear()
