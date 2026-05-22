"""
models.py — Pydantic v2 models for GreenPack EPR Service
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# /submit
# ---------------------------------------------------------------------------

REQUIRED_CATEGORIES = frozenset({"rigid_plastic", "flexible_plastic", "multilayer_plastic"})
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


class DeclarationRequest(BaseModel):
    """Incoming payload for POST /submit."""

    producer_id: str
    month: str
    declared_quantities_kg: Dict[str, float]

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        if not MONTH_PATTERN.match(v):
            raise ValueError("month must match the format YYYY-MM (e.g. '2026-04')")
        return v

    @field_validator("declared_quantities_kg")
    @classmethod
    def validate_quantities(cls, v: Dict[str, float]) -> Dict[str, float]:
        # Check exact keys
        provided = set(v.keys())
        if provided != REQUIRED_CATEGORIES:
            missing = REQUIRED_CATEGORIES - provided
            extra = provided - REQUIRED_CATEGORIES
            parts: list[str] = []
            if missing:
                parts.append(f"missing keys: {sorted(missing)}")
            if extra:
                parts.append(f"unexpected keys: {sorted(extra)}")
            raise ValueError(
                "declared_quantities_kg must contain exactly the keys "
                f"rigid_plastic, flexible_plastic, multilayer_plastic. {'; '.join(parts)}"
            )
        # All values must be strictly positive
        for key, val in v.items():
            if val <= 0:
                raise ValueError(
                    f"All quantity values must be > 0. Got {val} for '{key}'."
                )
        return v

    @field_validator("producer_id")
    @classmethod
    def validate_producer_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("producer_id must not be empty.")
        return v


class DeclarationResponse(BaseModel):
    """Stored declaration returned by POST /submit."""

    record_id: str
    producer_id: str
    month: str
    declared_quantities_kg: Dict[str, float]
    created_at: str


# ---------------------------------------------------------------------------
# /summary
# ---------------------------------------------------------------------------

class ReconciliationItem(BaseModel):
    category: str
    declared_kg: float
    procured_kg: float
    difference_kg: float
    difference_pct: float
    flagged: bool


class SummaryResponse(BaseModel):
    producer_id: str
    month: str
    reconciliation: List[ReconciliationItem]
    flagged_categories: List[str]
    narrative: str


# ---------------------------------------------------------------------------
# /ask
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty.")
        return v


class Citation(BaseModel):
    document: str
    chunk_index: int
    excerpt: str


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: List[Citation]
