"""
rag/chunker.py — Semantic Text Chunker
=======================================
When we retrieve a long medical article or guideline from an API (e.g., a
3000-word PubMed abstract or an FDA drug label), we cannot send the entire
text to ChromaDB or the LLM.  We need to break it into smaller, meaningful
pieces called "chunks".

What this file does:
  1. Takes a long piece of text + its metadata (title, publisher, url).
  2. Splits it into chunks of approximately `chunk_size` words.
  3. Adds an `overlap` of words between consecutive chunks so that no
     sentence meaning is lost at the boundary.
  4. Returns a list of EvidenceChunk objects, each containing:
     - text:      The chunk content (200 words).
     - title:     The original article title.
     - publisher: The source (e.g., "ADA", "PubMed", "openFDA").
     - url:       The original source URL.

Why chunking matters:
  - ChromaDB embeds each chunk as a separate vector.
  - Smaller chunks = more precise cosine similarity matching.
  - The LLM receives only the most relevant 3-5 chunks, not the whole article.

Usage:
    from app.shared.core.chunker import SemanticChunker
    chunker = SemanticChunker(chunk_size=200, overlap=30)
    chunks = chunker.chunk(text="...", title="ADA Guidelines", publisher="ADA", url="https://...")
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceChunk:
    """A single chunk of evidence text with its source metadata."""

    text: str           # The chunk content (approximately 200 words)
    title: str          # Article / guideline title
    publisher: str      # Source name (e.g., "ADA", "PubMed", "openFDA")
    url: str            # Original source URL
    chunk_index: int    # Position of this chunk in the original document (0, 1, 2, ...)


class SemanticChunker:
    """
    Splits long medical text into overlapping word-based chunks.

    Parameters:
        chunk_size (int): Target number of words per chunk (default: 200).
        overlap (int):    Number of overlapping words between chunks (default: 30).
    """

    def __init__(self, chunk_size: int = 200, overlap: int = 30) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(
        self,
        text: str,
        title: str = "",
        publisher: str = "",
        url: str = "",
    ) -> list[EvidenceChunk]:
        """
        Split `text` into chunks and attach metadata to each chunk.

        Args:
            text:      The full article / guideline / abstract text.
            title:     Source article title.
            publisher: Source publisher name.
            url:       Source URL.

        Returns:
            A list of EvidenceChunk objects.
        """
        # Step 1: Clean whitespace and split into words.
        words = text.split()

        # If the text is already short enough, return it as one chunk.
        if len(words) <= self.chunk_size:
            return [
                EvidenceChunk(
                    text=text.strip(),
                    title=title,
                    publisher=publisher,
                    url=url,
                    chunk_index=0,
                )
            ]

        # Step 2: Slide a window across the word list.
        chunks: list[EvidenceChunk] = []
        start = 0
        chunk_index = 0

        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            chunks.append(
                EvidenceChunk(
                    text=chunk_text,
                    title=title,
                    publisher=publisher,
                    url=url,
                    chunk_index=chunk_index,
                )
            )

            # Move the window forward by (chunk_size - overlap) words.
            # The overlap ensures continuity between chunks.
            start += self.chunk_size - self.overlap
            chunk_index += 1

        return chunks
