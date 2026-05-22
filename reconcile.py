"""
reconcile.py — Deterministic reconciliation logic for GreenPack EPR Service.

No LLM calls here. Pure arithmetic.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from models import ReconciliationItem

_HERE = Path(__file__).parent
ERP_FEED_PATH = _HERE / "data" / "erp_feed.csv"

FLAG_THRESHOLD_PCT = 5.0  # flag if difference exceeds 5 %


def load_erp_feed(producer_id: str, month: str) -> dict[str, float]:
    """
    Read data/erp_feed.csv and return a mapping of
    {category: procured_kg} filtered by producer_id and month.

    CSV columns: producer_id, month, category, procured_kg
    """
    if not ERP_FEED_PATH.exists():
        raise FileNotFoundError(f"ERP feed not found at {ERP_FEED_PATH}")

    result: dict[str, float] = {}
    with ERP_FEED_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["producer_id"] == producer_id and row["month"] == month:
                result[row["category"]] = float(row["procured_kg"])

    return result


def reconcile(
    declared: dict[str, float],
    procured: dict[str, float],
) -> List[ReconciliationItem]:
    """
    For each category in declared, compute reconciliation metrics.

    Args:
        declared: {category: declared_kg}  — from SQLite
        procured: {category: procured_kg}  — from ERP CSV

    Returns:
        List of ReconciliationItem (one per category).
    """
    items: List[ReconciliationItem] = []

    for category, declared_kg in declared.items():
        procured_kg = procured.get(category, 0.0)

        difference_kg = declared_kg - procured_kg

        # Avoid ZeroDivisionError — if procured is 0, pct is 100 %
        if procured_kg != 0:
            difference_pct = round(abs(difference_kg / procured_kg) * 100, 2)
        else:
            difference_pct = 100.0

        flagged = difference_pct > FLAG_THRESHOLD_PCT

        items.append(
            ReconciliationItem(
                category=category,
                declared_kg=declared_kg,
                procured_kg=procured_kg,
                difference_kg=round(difference_kg, 2),
                difference_pct=difference_pct,
                flagged=flagged,
            )
        )

    # Sort for deterministic output order
    items.sort(key=lambda x: x.category)
    return items
