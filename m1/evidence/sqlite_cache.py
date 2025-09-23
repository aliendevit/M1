from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from m1.models import EvidenceChip

ISO_FMT = "%Y-%m-%dT%H:%M:%S%z"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SQLiteChartCache:
    """Lightweight evidence cache backed by SQLite."""

    db_path: Path

    def initialise(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS patient (
                    patient_id TEXT PRIMARY KEY,
                    name TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS encounter (
                    encounter_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    type TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS observation (
                    obs_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT,
                    ts TEXT NOT NULL,
                    code TEXT,
                    label TEXT,
                    value_num REAL,
                    value_text TEXT,
                    unit TEXT,
                    ref_low REAL,
                    ref_high REAL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS note (
                    note_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT,
                    ts TEXT NOT NULL,
                    author TEXT,
                    content TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    note_id,
                    content
                )
                """
            )
            conn.commit()

    def ingest_bundle(self, bundle: dict[str, Any]) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            patient = bundle.get("patient", {})
            if patient:
                cur.execute(
                    "REPLACE INTO patient(patient_id, name) VALUES (?, ?)",
                    (patient.get("id", "demo-patient"), patient.get("name")),
                )
            for enc in bundle.get("encounters", []):
                cur.execute(
                    "REPLACE INTO encounter(encounter_id, patient_id, started_at, finished_at, type) VALUES (?, ?, ?, ?, ?)",
                    (
                        enc.get("id"),
                        enc.get("patient_id", patient.get("id", "demo-patient")),
                        self._normalise_ts(enc.get("started_at")),
                        self._normalise_ts(enc.get("finished_at")),
                        enc.get("type"),
                    ),
                )
            for obs in bundle.get("observations", []):
                obs_id = obs.get("id") or f"obs-{obs.get('code', 'unknown')}-{obs.get('ts')}"
                value = obs.get("value")
                value_num = self._coerce_float(value)
                cur.execute(
                    "REPLACE INTO observation(obs_id, patient_id, encounter_id, ts, code, label, value_num, value_text, unit, ref_low, ref_high) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        obs_id,
                        obs.get("patient_id", patient.get("id", "demo-patient")),
                        obs.get("encounter_id"),
                        self._normalise_ts(obs.get("ts")),
                        obs.get("code"),
                        obs.get("label"),
                        value_num,
                        self._to_text(value),
                        obs.get("unit"),
                        self._coerce_float(obs.get("ref_low")),
                        self._coerce_float(obs.get("ref_high")),
                    ),
                )
            for note in bundle.get("notes", []):
                note_id = note.get("id") or f"note-{note.get('ts')}"
                ts = self._normalise_ts(note.get("ts"))
                cur.execute(
                    "REPLACE INTO note(note_id, patient_id, encounter_id, ts, author, content) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        note_id,
                        note.get("patient_id", patient.get("id", "demo-patient")),
                        note.get("encounter_id"),
                        ts,
                        note.get("author"),
                        note.get("content", ""),
                    ),
                )
                cur.execute(
                    "REPLACE INTO notes_fts(note_id, content) VALUES (?, ?)",
                    (note_id, note.get("content", "")),
                )
            conn.commit()

    def context_window(self, window_hours: int, patient_id: str = "demo-patient") -> dict[str, Any]:
        since = _now() - timedelta(hours=window_hours)
        labs = list(self._labs_since(patient_id, since))
        notes = list(self._notes_since(patient_id, since))
        return {
            "labs": labs,
            "vitals": [],
            "notes": notes,
        }

    def build_evidence_chips(self, patient_id: str, window_hours: int) -> list[EvidenceChip]:
        labs = self.context_window(window_hours, patient_id)["labs"]
        chips: list[EvidenceChip] = []
        for lab in labs:
            chips.append(
                EvidenceChip(
                    chip_id=f"lab-{lab['code']}",
                    label=f"{lab['label']} {lab['display_value']}",
                    band=lab.get("band", "B"),
                    confidence=lab.get("confidence", 0.75),
                    rationale=lab.get("delta_text"),
                    metadata={"ts": lab.get("ts"), "unit": lab.get("unit"), "value": lab.get("value")},
                )
            )
        return chips

    def _labs_since(self, patient_id: str, since: datetime) -> Iterable[dict[str, Any]]:
        query = (
            "SELECT obs_id, ts, code, label, value_num, value_text, unit FROM observation WHERE patient_id=? AND ts>=? ORDER BY code, ts"
        )
        rows = self._fetchall(query, (patient_id, since.strftime(ISO_FMT)))
        grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            grouped[row["code"] or row["obs_id"]].append(row)
        for code, code_rows in grouped.items():
            if not code_rows:
                continue
            latest = code_rows[-1]
            previous = code_rows[-2] if len(code_rows) > 1 else None
            value = self._pick_value(latest)
            delta_text = self._delta_text(latest, previous)
            yield {
                "id": latest["obs_id"],
                "code": code,
                "label": latest["label"] or code,
                "value": value,
                "unit": latest["unit"],
                "ts": latest["ts"],
                "display_value": self._format_value(value, latest["unit"], delta_text),
                "delta_text": delta_text,
                "confidence": 0.75,
                "band": "B" if delta_text and delta_text.startswith("+") else "C" if delta_text and delta_text.startswith("-") else "B",
            }

    def _notes_since(self, patient_id: str, since: datetime) -> Iterable[dict[str, Any]]:
        query = (
            "SELECT note_id, ts, author, content FROM note WHERE patient_id=? AND ts>=? ORDER BY ts DESC"
        )
        rows = self._fetchall(query, (patient_id, since.strftime(ISO_FMT)))
        for row in rows:
            yield {
                "id": row["note_id"],
                "ts": row["ts"],
                "author": row["author"],
                "preview": row["content"][:180],
            }

    def _format_value(self, value: float | str | None, unit: str | None, delta: str | None) -> str:
        base = "" if value is None else f"{value:g}" if isinstance(value, (int, float)) else str(value)
        if unit:
            base = f"{base} {unit}".strip()
        if delta:
            base = f"{base} ({delta})" if delta != "\u2194" else f"{base} (\u2194)"
        return base.strip()

    def _delta_text(self, latest: sqlite3.Row, previous: sqlite3.Row | None) -> str | None:
        if previous is None:
            return None
        latest_val = self._pick_value(latest)
        prev_val = self._pick_value(previous)
        if latest_val is None or prev_val is None:
            return None
        delta = round(latest_val - prev_val, 2)
        if delta == 0:
            return "\u2194"
        sign = "+" if delta > 0 else ""
        return f"{sign}{delta}"

    def _pick_value(self, row: sqlite3.Row) -> float | None:
        value = row["value_num"]
        if value is not None:
            return float(value)
        try:
            return float(row["value_text"])
        except (TypeError, ValueError):
            return None

    def _fetchall(self, query: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, params)
            return cur.fetchall()

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_text(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return f"{value}"
        return str(value)

    @staticmethod
    def _normalise_ts(value: Any) -> str:
        if not value:
            return _now().strftime(ISO_FMT)
        if isinstance(value, datetime):
            dt = value.astimezone(timezone.utc)
        else:
            text = str(value).replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                dt = _now()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        return dt.strftime(ISO_FMT)
