"""
main.py — GreenPack EPR Service (FastAPI application entry-point).

Endpoints:
  GET  /                               — Serves frontend.html (static)
  GET  /health                         — Health check (Render uptime probes)
  POST /submit                         — Validate & store a plastic declaration
  GET  /summary/{producer_id}/{month}  — Reconcile + LLM narrative
  POST /ask                            — RAG Q&A over EPR policy corpus

Startup (lifespan):
  1. Validate required environment variables
  2. Initialise SQLite tables
  3. Build FAISS index from corpus
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import groq as groq_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path as FPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import llm as llm_module
import rag
import storage
from models import (
    AskRequest,
    AskResponse,
    Citation,
    DeclarationRequest,
    DeclarationResponse,
    ReconciliationItem,
    SummaryResponse,
)
from reconcile import load_erp_feed, reconcile

# ---------------------------------------------------------------------------
# Bootstrap — load .env and configure logging before anything else
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,       # Render captures stdout, not stderr by default
)
logger = logging.getLogger(__name__)

# Resolve the directory that contains this file (works on Render)
_HERE = Path(__file__).parent
_FRONTEND_HTML = _HERE / "frontend.html"


# ---------------------------------------------------------------------------
# Startup environment validation
# ---------------------------------------------------------------------------

def _validate_env() -> None:
    """
    Check required environment variables are present.
    Logs a clear error and exits non-zero so Render marks the deploy failed
    rather than running silently broken.
    """
    required = {"GROQ_API_KEY"}
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.error(
            "STARTUP FAILED — missing required environment variable(s): %s. "
            "Set them in the Render dashboard under Environment → Environment Variables.",
            ", ".join(missing),
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup tasks before serving requests, teardown after."""
    logger.info("=== GreenPack EPR Service - starting up ===")

    # 1. Validate environment
    _validate_env()
    logger.info("[1/3] OK: Environment variables validated.")

    # 2. Initialise database (creates greenpack.db if absent)
    try:
        storage.init_db()
        logger.info("[2/3] OK: SQLite database initialised at: %s", storage.DB_PATH)
    except Exception as exc:
        logger.exception("[2/3] FAIL: SQLite initialisation failed: %s", exc)
        sys.exit(1)

    # 3. Build FAISS index from corpus
    try:
        num_chunks = rag.build_index()
        logger.info("[3/3] OK: FAISS index built - %d chunks indexed.", num_chunks)
    except Exception as exc:
        logger.exception("[3/3] FAIL: FAISS index build failed: %s", exc)
        sys.exit(1)

    logger.info("=== GreenPack EPR Service - API ready ===")

    yield  # application serves requests here

    logger.info("GreenPack EPR Service shutting down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GreenPack EPR Service",
    description=(
        "A FastAPI service for plastic packaging Extended Producer "
        "Responsibility (EPR) compliance workflows. Supports declaration "
        "submission, ERP reconciliation with LLM narrative, and "
        "policy Q&A via RAG."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so the hosted frontend (Render static URL,
# file://, localhost) can call the API freely.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Static — serve frontend.html at /
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    """Serve the HTML dashboard so users can open the Render URL directly."""
    if not _FRONTEND_HTML.exists():
        raise HTTPException(status_code=404, detail="frontend.html not found.")
    return FileResponse(str(_FRONTEND_HTML), media_type="text/html")


# ---------------------------------------------------------------------------
# Health check — Render uptime probes hit this
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health_check() -> JSONResponse:
    """
    Lightweight liveness probe.
    Returns HTTP 200 while the service is running normally.
    """
    return JSONResponse({"status": "ok", "service": "GreenPack EPR Service"})


# ---------------------------------------------------------------------------
# Helper — wrap LLM calls with consistent 503 handling
# ---------------------------------------------------------------------------

def _safe_llm_call(fn, *args, **kwargs) -> str:
    """
    Execute *fn(*args, **kwargs)* and raise HTTP 503 on any LLM failure.
    """
    try:
        return fn(*args, **kwargs)
    except groq_sdk.APIConnectionError as exc:
        logger.error("Groq API connection error: %s", exc)
        raise HTTPException(status_code=503, detail="LLM service unavailable — connection error.")
    except groq_sdk.RateLimitError as exc:
        logger.error("Groq rate limit: %s", exc)
        raise HTTPException(status_code=503, detail="LLM service unavailable — rate limit reached.")
    except groq_sdk.APIStatusError as exc:
        logger.error("Groq API status error %s: %s", exc.status_code, exc.message)
        raise HTTPException(status_code=503, detail="LLM service unavailable — API error.")
    except RuntimeError as exc:
        # e.g. missing API key surfaced at call time
        logger.error("LLM runtime error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected LLM error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


# ---------------------------------------------------------------------------
# POST /submit
# ---------------------------------------------------------------------------

@app.post(
    "/submit",
    response_model=DeclarationResponse,
    status_code=201,
    summary="Submit a plastic packaging declaration",
    tags=["Declarations"],
)
def submit_declaration(payload: DeclarationRequest) -> DeclarationResponse:
    """
    Validate and persist a plastic packaging quantity declaration.

    - No LLM calls are made here.
    - Pydantic handles all validation (month format, required keys, positive values).
    - Returns the stored record on success (HTTP 201).
    """
    try:
        record = storage.insert_declaration(
            producer_id=payload.producer_id,
            month=payload.month,
            rigid_kg=payload.declared_quantities_kg["rigid_plastic"],
            flexible_kg=payload.declared_quantities_kg["flexible_plastic"],
            multilayer_kg=payload.declared_quantities_kg["multilayer_plastic"],
        )
    except Exception as exc:
        logger.exception("Failed to insert declaration: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error.")

    return DeclarationResponse(**record)


# ---------------------------------------------------------------------------
# GET /summary/{producer_id}/{month}
# ---------------------------------------------------------------------------

@app.get(
    "/summary/{producer_id}/{month}",
    response_model=SummaryResponse,
    summary="Get reconciliation summary for a producer/month",
    tags=["Summary"],
)
def get_summary(
    producer_id: str = FPath(..., description="Producer identifier, e.g. GREENPACK-001"),
    month: str = FPath(..., description="Reporting month in YYYY-MM format, e.g. 2026-04"),
) -> SummaryResponse:
    """
    Fetch the stored declaration, reconcile it against the ERP feed (CSV),
    generate a compliance narrative via Llama-3.3-70b (Groq), and return
    the full summary.

    - Reconciliation arithmetic is 100% deterministic (no LLM).
    - LLM is only used to generate the human-readable narrative.
    """
    # 1. Fetch declaration from SQLite
    declaration = storage.fetch_declaration(producer_id, month)
    if declaration is None:
        raise HTTPException(
            status_code=404,
            detail=f"No declaration found for producer '{producer_id}' month '{month}'.",
        )

    declared: dict[str, float] = {
        "rigid_plastic": declaration["rigid_plastic_kg"],
        "flexible_plastic": declaration["flexible_plastic_kg"],
        "multilayer_plastic": declaration["multilayer_plastic_kg"],
    }

    # 2. Load ERP feed
    try:
        procured = load_erp_feed(producer_id, month)
    except FileNotFoundError as exc:
        logger.error("ERP feed missing: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Error loading ERP feed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error.")

    # 3. Deterministic reconciliation
    reconciliation_items = reconcile(declared, procured)
    flagged_categories = [item.category for item in reconciliation_items if item.flagged]

    # 4. LLM narrative
    reconciliation_data = {
        "producer_id": producer_id,
        "month": month,
        "reconciliation": [item.model_dump() for item in reconciliation_items],
        "flagged_categories": flagged_categories,
    }
    narrative = _safe_llm_call(
        llm_module.generate_reconciliation_narrative, reconciliation_data
    )

    return SummaryResponse(
        producer_id=producer_id,
        month=month,
        reconciliation=reconciliation_items,
        flagged_categories=flagged_categories,
        narrative=narrative,
    )


# ---------------------------------------------------------------------------
# POST /ask
# ---------------------------------------------------------------------------

@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a compliance question (RAG over EPR policy corpus)",
    tags=["Q&A"],
)
def ask_question(payload: AskRequest) -> AskResponse:
    """
    Answer a compliance-related question using Retrieval-Augmented Generation.

    1. Embeds the question and retrieves the top-3 matching corpus chunks (FAISS).
    2. Passes the question + chunks to Llama-3.3-70b (Groq) for grounded answer.
    3. Returns the answer and citations (even if LLM says it does not know).
    """
    # Retrieval
    try:
        chunks = rag.retrieve(payload.question)
    except RuntimeError as exc:
        logger.error("FAISS retrieval error: %s", exc)
        raise HTTPException(status_code=500, detail="Vector retrieval failed.")

    # Generation
    answer = _safe_llm_call(llm_module.generate_rag_answer, payload.question, chunks)

    # Build citations
    citations = [
        Citation(
            document=chunk["doc_name"],
            chunk_index=chunk["chunk_index"],
            excerpt=chunk["text"][:80],
        )
        for chunk in chunks
    ]

    return AskResponse(
        question=payload.question,
        answer=answer,
        citations=citations,
    )
