"""SQLite-backed cache for evidence items."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


@dataclass(slots=True)
class EvidenceItem:
    patient_id: str
    section: str
    payload: dict


class SQLiteEvidenceCache:
    """Lightweight SQLite wrapper for storing structured evidence."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    patient_id TEXT NOT NULL,
                    section TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (patient_id, section)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
                    patient_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT
                )
                """
            )
            conn.commit()

    def upsert_items(self, items: Sequence[EvidenceItem]) -> None:
        if not items:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                REPLACE INTO evidence(patient_id, section, payload)
                VALUES (?, ?, ?)
                """,
                ((item.patient_id, item.section, json.dumps(item.payload)) for item in items),
            )
            conn.executemany(
                """
                INSERT INTO audit_log(patient_id, action, detail)
                VALUES (?, 'UPSERT_EVIDENCE', ?)
                """,
                ((item.patient_id, item.section) for item in items),
            )
            conn.commit()

    def fetch_items(self, patient_id: str) -> List[EvidenceItem]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT patient_id, section, payload FROM evidence WHERE patient_id = ? ORDER BY section",
                (patient_id,),
            )
            rows = cursor.fetchall()
        return [
            EvidenceItem(patient_id=row[0], section=row[1], payload=json.loads(row[2]))
            for row in rows
        ]

    def upsert_bundle(self, bundle: dict) -> str:
        patient_id = bundle.get("patient_id", "unknown")
        sections = bundle.get("sections", {})
        items = [
            EvidenceItem(patient_id=patient_id, section=section, payload=value)
            for section, value in sections.items()
        ]
        self.upsert_items(items)
        return patient_id

    async def a_upsert_items(self, items: Sequence[EvidenceItem]) -> None:
        await asyncio.to_thread(self.upsert_items, items)

    async def a_fetch_items(self, patient_id: str) -> List[EvidenceItem]:
        return await asyncio.to_thread(self.fetch_items, patient_id)

    async def a_upsert_bundle(self, bundle: dict) -> str:
        return await asyncio.to_thread(self.upsert_bundle, bundle)


class SQLiteChartCache(SQLiteEvidenceCache):
    """Chart cache with explicit contract for clinical context lookups."""

    def _ensure_schema(self) -> None:
        super()._ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context (
                    patient_id TEXT NOT NULL,
                    snippet TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS labs (
                    patient_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value REAL,
                    unit TEXT,
                    ts TEXT,
                    PRIMARY KEY (patient_id, name, ts)
                )
                """
            )
            conn.commit()

    def initialise(self) -> None:
        self.initialize()

    def initialize(self) -> None:
        self._ensure_schema()

    def ingest_bundle(self, bundle: Dict[str, Any]) -> str:
        patient_id = super().upsert_bundle(bundle)
        sections = bundle.get("sections", {})
        structured = sections.get("structured", {}) if isinstance(sections, dict) else {}
        vitals = structured.get("vitals", {}) if isinstance(structured, dict) else {}
        plan = structured.get("plan", []) if isinstance(structured, dict) else []
        summary_parts = []
        if vitals:
            summary_parts.append("Vitals: " + ", ".join(f"{k}={v}" for k, v in vitals.items()))
        if plan:
            summary_parts.append("Plan: " + "; ".join(plan))
        summary = summary_parts or ["No structured summary available"]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO context(patient_id, snippet) VALUES (?, ?)",
                (patient_id, " | ".join(summary)),
            )
            labs = structured.get("labs", []) if isinstance(structured, dict) else []
            if isinstance(labs, list):
                for lab in labs:
                    name = lab.get("name")
                    if not name:
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO labs(patient_id, name, value, unit, ts)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            patient_id,
                            name,
                            _safe_float(lab.get("value")),
                            lab.get("unit"),
                            lab.get("ts"),
                        ),
                    )
            conn.commit()
        return patient_id

    def context_window(self, patient_id: str, limit: int = 5) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT snippet FROM context WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?",
                (patient_id, limit),
            )
            rows = cursor.fetchall()
        return [row[0] for row in rows]

    def lab_deltas(self, patient_id: str, lab_name: str) -> List[float]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM labs WHERE patient_id = ? AND name = ? ORDER BY ts",
                (patient_id, lab_name),
            )
            values = [row[0] for row in cursor.fetchall() if row[0] is not None]
        deltas: List[float] = []
        for previous, current in zip(values, values[1:]):
            deltas.append(current - previous)
        return deltas


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def bundle_from_transcript(patient_id: str, transcript: str, extraction: dict) -> dict:
    """Create a normalized bundle structure from raw extraction pieces."""
    return {
        "patient_id": patient_id,
        "sections": {
            "subjective": {"transcript": transcript},
            "structured": extraction,
        },
    }
