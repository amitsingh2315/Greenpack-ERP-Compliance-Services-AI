"""
storage.py — SQLite helpers for GreenPack EPR Service.

Uses Python's built-in sqlite3 module. All functions are synchronous;
FastAPI routes call them directly (acceptable for SQLite workloads).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from pathlib import Path as _Path

# Anchor DB path to the directory that contains this file so it works
# on Render (where the working directory may differ from the source root).
_HERE = _Path(__file__).parent
DB_PATH = str(_HERE / "greenpack.db")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

CREATE_DECLARATIONS_SQL = """
CREATE TABLE IF NOT EXISTS declarations (
    record_id          TEXT PRIMARY KEY,
    producer_id        TEXT NOT NULL,
    month              TEXT NOT NULL,
    rigid_plastic_kg   REAL NOT NULL,
    flexible_plastic_kg REAL NOT NULL,
    multilayer_plastic_kg REAL NOT NULL,
    created_at         TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't already exist."""
    with get_connection() as conn:
        conn.execute(CREATE_DECLARATIONS_SQL)
        conn.commit()


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def insert_declaration(
    producer_id: str,
    month: str,
    rigid_kg: float,
    flexible_kg: float,
    multilayer_kg: float,
) -> dict:
    """
    Insert a new declaration record and return the full stored row as a dict.
    """
    record_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    sql = """
    INSERT INTO declarations
        (record_id, producer_id, month, rigid_plastic_kg,
         flexible_plastic_kg, multilayer_plastic_kg, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        conn.execute(
            sql,
            (record_id, producer_id, month, rigid_kg, flexible_kg, multilayer_kg, created_at),
        )
        conn.commit()

    return {
        "record_id": record_id,
        "producer_id": producer_id,
        "month": month,
        "declared_quantities_kg": {
            "rigid_plastic": rigid_kg,
            "flexible_plastic": flexible_kg,
            "multilayer_plastic": multilayer_kg,
        },
        "created_at": created_at,
    }


def fetch_declaration(producer_id: str, month: str) -> Optional[dict]:
    """
    Fetch a declaration by (producer_id, month).
    Returns a dict or None if not found.
    """
    sql = """
    SELECT * FROM declarations
    WHERE producer_id = ? AND month = ?
    ORDER BY created_at DESC
    LIMIT 1
    """
    with get_connection() as conn:
        row = conn.execute(sql, (producer_id, month)).fetchone()

    if row is None:
        return None

    return {
        "record_id": row["record_id"],
        "producer_id": row["producer_id"],
        "month": row["month"],
        "rigid_plastic_kg": row["rigid_plastic_kg"],
        "flexible_plastic_kg": row["flexible_plastic_kg"],
        "multilayer_plastic_kg": row["multilayer_plastic_kg"],
        "created_at": row["created_at"],
    }
