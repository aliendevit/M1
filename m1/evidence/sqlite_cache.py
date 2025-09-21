"""SQLite-backed evidence cache with delta computation."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from ..schemas import EvidenceChip, EvidenceKind


@dataclass
class Observation:
    id: str
    name: str
    value: str
    time: str
    kind: EvidenceKind
    unit: Optional[str] = None
    numeric_value: Optional[float] = None

    def to_chip(self, delta: Optional[str] = None) -> EvidenceChip:
        return EvidenceChip(
            id=self.id,
            kind=self.kind,
            name=self.name,
            value=self.value,
            delta=delta,
            time=self.time,
            source_id=self.id,
        )


class SQLiteChartCache:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialise(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    value TEXT NOT NULL,
                    unit TEXT,
                    numeric_value REAL,
                    time TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    delta TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_observations_name_time
                    ON observations(name, time);
                """
            )
            conn.commit()

    def ingest_observations(self, observations: Iterable[Observation]) -> None:
        with self._connect() as conn:
            for obs in observations:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO observations(id, name, value, unit, numeric_value, time, kind)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        obs.id,
                        obs.name,
                        obs.value,
                        obs.unit,
                        obs.numeric_value,
                        obs.time,
                        obs.kind.value,
                    ),
                )
            conn.commit()
        self._recompute_deltas()

    def ingest_bundle(self, observations: Iterable[Observation]) -> None:
        self.ingest_observations(observations)

    def context_window(self, window_hours: int) -> List[EvidenceChip]:
        cutoff = None
        if window_hours > 0:
            cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, value, unit, time, kind, delta
                FROM observations
                ORDER BY datetime(time) DESC
                """
            ).fetchall()
        chips: List[EvidenceChip] = []
        for row in rows:
            obs_time = _safe_parse_time(row["time"])
            if cutoff and obs_time:
                if obs_time.tzinfo is None:
                    obs_time = obs_time.replace(tzinfo=UTC)
                if obs_time < cutoff:
                    continue
            chips.append(
                EvidenceChip(
                    id=row["id"],
                    kind=EvidenceKind(row["kind"]),
                    name=row["name"],
                    value=row["value"],
                    delta=row["delta"],
                    time=row["time"],
                    source_id=row["id"],
                )
            )
        return chips

    def _recompute_deltas(self) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, numeric_value, time
                FROM observations
                WHERE numeric_value IS NOT NULL
                ORDER BY name, datetime(time)
                """
            ).fetchall()
            previous: dict[str, float] = {}
            deltas: dict[str, str] = {}
            for row in rows:
                name = row["name"]
                value = row["numeric_value"]
                obs_id = row["id"]
                if name in previous:
                    diff = round(value - previous[name], 2)
                    if diff > 0:
                        delta = f"+{diff}"
                    elif diff < 0:
                        delta = f"{diff}"
                    else:
                        delta = "↔"
                else:
                    delta = "↔"
                deltas[obs_id] = delta
                previous[name] = value
            for obs_id, delta in deltas.items():
                conn.execute("UPDATE observations SET delta = ? WHERE id = ?", (delta, obs_id))
            conn.commit()


def _safe_parse_time(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
