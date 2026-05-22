"""
rag.py — RAG pipeline for GreenPack EPR Service.

Loads .txt documents from data/epr_corpus/, splits them into overlapping
chunks, embeds them with sentence-transformers all-MiniLM-L6-v2, and stores
the vectors in a FAISS IndexFlatL2 index.

The index is built once at application startup via build_index() and then
queried per /ask request via retrieve().
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
CORPUS_DIR = _HERE / "data" / "epr_corpus"

CHUNK_SIZE_WORDS = 200
OVERLAP_WORDS = 20
TOP_K = 3
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Module-level singletons populated by build_index()
_faiss_index: faiss.IndexFlatL2 | None = None
_metadata: List[dict] = []          # [{doc_name, chunk_index, text}, …]
_embed_model: SentenceTransformer | None = None


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Split *text* into overlapping word-based chunks.

    Args:
        text:       Full document text.
        chunk_size: Target number of words per chunk.
        overlap:    Number of words to repeat at the start of each new chunk.

    Returns:
        List of chunk strings.
    """
    words = text.split()
    chunks: List[str] = []
    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size  # safety guard

    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start += step

    return chunks


# ---------------------------------------------------------------------------
# Build index (called once at startup)
# ---------------------------------------------------------------------------

def build_index() -> int:
    """
    Load corpus docs → chunk → embed → build FAISS index.

    Populates module globals _faiss_index, _metadata, _embed_model.

    Returns:
        Total number of chunks indexed.
    """
    global _faiss_index, _metadata, _embed_model

    # Load embedding model
    logger.info("Loading sentence-transformer model '%s'…", EMBED_MODEL_NAME)
    _embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    # Collect all chunks and metadata
    all_chunks: List[str] = []
    _metadata = []

    if not CORPUS_DIR.exists():
        raise RuntimeError(f"Corpus directory not found: {CORPUS_DIR}")

    txt_files = sorted(CORPUS_DIR.glob("*.txt"))
    if not txt_files:
        raise RuntimeError(f"No .txt files found in {CORPUS_DIR}")

    for doc_path in txt_files:
        doc_name = doc_path.name
        text = doc_path.read_text(encoding="utf-8").strip()
        chunks = _chunk_text(text, CHUNK_SIZE_WORDS, OVERLAP_WORDS)

        for idx, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            _metadata.append(
                {"doc_name": doc_name, "chunk_index": idx, "text": chunk}
            )

    # Embed all chunks
    logger.info("Embedding %d chunks…", len(all_chunks))
    embeddings: np.ndarray = _embed_model.encode(
        all_chunks, show_progress_bar=False, convert_to_numpy=True
    )

    # Normalise to unit vectors (L2 distance on unit vectors ≈ cosine similarity ranking)
    faiss.normalize_L2(embeddings)

    # Build FAISS index
    dim = embeddings.shape[1]
    _faiss_index = faiss.IndexFlatL2(dim)
    _faiss_index.add(embeddings)

    logger.info("FAISS index built with %d chunks (dim=%d).", len(all_chunks), dim)
    return len(all_chunks)


# ---------------------------------------------------------------------------
# Retrieval (called per /ask request)
# ---------------------------------------------------------------------------

def retrieve(question: str, top_k: int = TOP_K) -> List[dict]:
    """
    Embed *question* and retrieve the top_k nearest chunks from the FAISS index.

    Args:
        question: User's natural-language question.
        top_k:    Number of chunks to return.

    Returns:
        List of metadata dicts: [{doc_name, chunk_index, text}, …]

    Raises:
        RuntimeError: If the index has not been built yet.
    """
    if _faiss_index is None or _embed_model is None:
        raise RuntimeError("FAISS index is not initialised. Call build_index() first.")

    # Embed the query
    query_vec: np.ndarray = _embed_model.encode(
        [question], show_progress_bar=False, convert_to_numpy=True
    )
    faiss.normalize_L2(query_vec)

    # Search
    k = min(top_k, _faiss_index.ntotal)
    _distances, indices = _faiss_index.search(query_vec, k)

    results: List[dict] = []
    for idx in indices[0]:
        if idx == -1:
            continue  # FAISS returns -1 for empty slots
        results.append(_metadata[idx])

    return results
