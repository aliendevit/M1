"""SQLite-backed cache for evidence items."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


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


def bundle_from_transcript(patient_id: str, transcript: str, extraction: dict) -> dict:
    """Create a normalized bundle structure from raw extraction pieces."""
    return {
        "patient_id": patient_id,
        "sections": {
            "subjective": {"transcript": transcript},
            "structured": extraction,
        },
    }
