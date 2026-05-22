"""
llm.py — LLM call wrappers for GreenPack EPR Service.

All calls use Groq API with model llama-3.3-70b-versatile.
GROQ_API_KEY is loaded from the .env file via python-dotenv.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List

from groq import Groq, APIConnectionError, RateLimitError, APIStatusError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_ID = "llama-3.3-70b-versatile"

# Lazy singleton — created on first use so startup doesn't fail if key is missing
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Create a .env file with GROQ_API_KEY=your_key_here"
            )
        _client = Groq(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# /summary  — reconciliation narrative
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM = (
    "You are a compliance analyst assistant. "
    "Generate a concise 3-5 sentence summary explaining the reconciliation "
    "results below. Explain any flagged categories in plain English and "
    "recommend one clear action. "
    "Do not add information not in the data provided."
)


def generate_reconciliation_narrative(reconciliation_data: dict) -> str:
    """
    Call the LLM to generate a narrative summary of the reconciliation results.

    Args:
        reconciliation_data: dict with keys producer_id, month, reconciliation,
                             flagged_categories.

    Returns:
        Narrative text string.

    Raises:
        RuntimeError: wrapped as HTTP 503 by the caller.
    """
    client = _get_client()

    user_content = (
        "Reconciliation data (JSON):\n"
        + json.dumps(reconciliation_data, indent=2)
    )

    logger.debug("Calling Groq LLM for reconciliation narrative…")
    response = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=300,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user",   "content": user_content},
        ],
    )

    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# /ask  — RAG answer generation
# ---------------------------------------------------------------------------

ASK_SYSTEM = (
    "You are a compliance assistant. "
    "Answer ONLY using the provided context. "
    "If the answer is not in the context, respond with exactly: "
    "I do not know based on the provided documents. "
    "Do not make up information."
)

NOT_FOUND_SENTINEL = "I do not know based on the provided documents."


def generate_rag_answer(question: str, context_chunks: List[dict]) -> str:
    """
    Call the LLM to answer a question using retrieved RAG chunks.

    Args:
        question: The user's question string.
        context_chunks: List of dicts with keys doc_name, chunk_index, text.

    Returns:
        Answer text string. May equal NOT_FOUND_SENTINEL.

    Raises:
        RuntimeError: wrapped as HTTP 503 by the caller.
    """
    client = _get_client()

    # Format context for the prompt
    context_parts = []
    for i, chunk in enumerate(context_chunks, start=1):
        context_parts.append(
            f"[{i}] Source: {chunk['doc_name']} (chunk {chunk['chunk_index']})\n"
            f"{chunk['text']}"
        )
    context_block = "\n\n---\n\n".join(context_parts)

    user_content = (
        f"Question: {question}\n\n"
        f"Context:\n{context_block}"
    )

    logger.debug("Calling Groq LLM for RAG answer…")
    response = client.chat.completions.create(
        model=MODEL_ID,
        max_tokens=400,
        messages=[
            {"role": "system", "content": ASK_SYSTEM},
            {"role": "user",   "content": user_content},
        ],
    )

    return response.choices[0].message.content.strip()
