# path: backend/db/repo.py
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from .models import Fact, ChipRow, SessionRow, KVPair

DEFAULT_DB = "data/chart.sqlite"
SCHEMA_PATH = os.path.join("backend", "db", "schema.sql")


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


class Repo:
    """
    Lightweight repository around SQLite with FTS5 and retention helpers.
    - Uses WAL mode (set via PRAGMA + schema.sql).
    - All rows returned as sqlite3.Row; mapping helpers in models.py
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Connection-level PRAGMAs (idempotent)
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_schema()

    def _init_schema(self):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            ddl = f.read()
        try:
            # IMPORTANT: executescript preserves triggers/batches (don’t split on ';')
            self.conn.executescript(ddl)
            self.conn.commit()
        except sqlite3.OperationalError as e:
            # Graceful fallback if FTS5 is missing on the target SQLite build
            if "fts5" in str(e).lower():
                fallback = """
                CREATE TABLE IF NOT EXISTS facts (
                  id TEXT PRIMARY KEY,
                  kind TEXT NOT NULL,
                  name TEXT NOT NULL,
                  value TEXT,
                  time TEXT,
                  source_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_facts_time ON facts(time);

                CREATE TABLE IF NOT EXISTS chips (
                  chip_id TEXT PRIMARY KEY,
                  slot TEXT, type TEXT, band TEXT, label TEXT, proposed TEXT,
                  confidence REAL, risk TEXT, evidence TEXT, actions TEXT,
                  state TEXT DEFAULT 'open', reason TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chips_band ON chips(band);
                CREATE INDEX IF NOT EXISTS idx_chips_state ON chips(state);
                CREATE INDEX IF NOT EXISTS idx_chips_updated ON chips(updated_at);

                CREATE TABLE IF NOT EXISTS sessions (
                  session_id TEXT PRIMARY KEY,
                  started_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  keystrokes INTEGER DEFAULT 0,
                  timers TEXT,
                  chip_counts TEXT
                );

                CREATE TABLE IF NOT EXISTS kv_cache (
                  k TEXT PRIMARY KEY,
                  v TEXT,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS transcripts (
                  id TEXT PRIMARY KEY,
                  text TEXT NOT NULL,
                  spans TEXT,
                  created_at TEXT NOT NULL
                );
                """
                self.conn.executescript(fallback)
                self.conn.commit()
            else:
                raise

    # ===== FACTS =====
    def upsert_fact(self, f: Fact) -> None:
        sql = """INSERT OR REPLACE INTO facts(id,kind,name,value,time,source_id)
                 VALUES (?,?,?,?,?,?)"""
        self.conn.execute(sql, f.to_tuple())
        self.conn.commit()

    def bulk_upsert_facts(self, facts: Iterable[Fact]) -> None:
        sql = """INSERT OR REPLACE INTO facts(id,kind,name,value,time,source_id)
                 VALUES (?,?,?,?,?,?)"""
        self.conn.executemany(sql, (f.to_tuple() for f in facts))
        self.conn.commit()

    def get_context(self, window_hours: int = 72) -> Dict[str, List[Dict]]:
        cutoff = (datetime.utcnow() - timedelta(hours=window_hours)).isoformat()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM facts WHERE time >= ? ORDER BY time DESC", (cutoff,))
        rows = [dict(r) for r in cur.fetchall()]
        out = {"labs": [], "vitals": [], "meds": [], "notes": [], "images": []}
        for r in rows:
            k = r.get("kind", "")
            if k == "lab":
                out["labs"].append(r)
            elif k == "vital":
                out["vitals"].append(r)
            elif k == "med":
                out["meds"].append(r)
            elif k == "image":
                out["images"].append(r)
            else:
                out["notes"].append(r)
        return out

    def fts_search_facts(self, query: str, limit: int = 50) -> List[Dict]:
        cur = self.conn.cursor()
        try:
            sql = """SELECT f.* FROM facts f
                     JOIN facts_fts ft ON ft.rowid = f.rowid
                     WHERE facts_fts MATCH ? LIMIT ?"""
            cur.execute(sql, (query, limit))
            return [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            # Fallback if FTS5 not present: crude LIKE search
            like = f"%{query}%"
            cur.execute(
                "SELECT * FROM facts WHERE name LIKE ? OR value LIKE ? LIMIT ?",
                (like, like, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def retention_cleanup_facts(self, days: int = 30) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM facts WHERE time < ?", (cutoff,))
        self.conn.commit()
        return cur.rowcount

    # ===== CHIPS =====
    def upsert_chip(self, c: ChipRow) -> None:
        sql = """INSERT OR REPLACE INTO chips(
                    chip_id,slot,type,band,label,proposed,confidence,risk,
                    evidence,actions,state,reason,created_at,updated_at
                 ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        self.conn.execute(sql, c.to_tuple())
        self.conn.commit()

    def get_chip(self, chip_id: str) -> Optional[ChipRow]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM chips WHERE chip_id=?", (chip_id,))
        r = cur.fetchone()
        return ChipRow.from_row(r) if r else None

    def list_chips(self, band: Optional[str] = None, state: Optional[str] = None, limit: int = 200) -> List[ChipRow]:
        sql = "SELECT * FROM chips"
        params: List[str] = []
        clauses: List[str] = []
        if band:
            clauses.append("band = ?")
            params.append(band)
        if state:
            clauses.append("state = ?")
            params.append(state)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(str(limit))
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return [ChipRow.from_row(r) for r in cur.fetchall()]

    def update_chip_state(self, chip_id: str, state: str, reason: Optional[str] = None) -> bool:
        now = _utcnow()
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE chips SET state=?, reason=?, updated_at=? WHERE chip_id=?",
            (state, reason, now, chip_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def retention_cleanup_chips(self, days: int = 30) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM chips WHERE updated_at < ?", (cutoff,))
        self.conn.commit()
        return cur.rowcount

    # ===== SESSIONS =====
    def start_session(self, session_id: str) -> None:
        now = _utcnow()
        sql = """INSERT OR IGNORE INTO sessions(
                   session_id, started_at, last_seen_at, keystrokes, timers, chip_counts
                 ) VALUES (?,?,?,?,?,?)"""
        self.conn.execute(sql, (session_id, now, now, 0, json.dumps({}), json.dumps({"A":0,"B":0,"C":0,"D":0})))
        self.conn.commit()

    def touch_session(self, session_id: str) -> None:
        self.conn.execute("UPDATE sessions SET last_seen_at=? WHERE session_id=?", (_utcnow(), session_id))
        self.conn.commit()

    def add_keystrokes(self, session_id: str, n: int = 1) -> None:
        self.conn.execute(
            "UPDATE sessions SET keystrokes = keystrokes + ?, last_seen_at=? WHERE session_id=?",
            (int(n), _utcnow(), session_id),
        )
        self.conn.commit()

    def add_timer_ms(self, session_id: str, timer_name: str, ms: int) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT timers FROM sessions WHERE session_id=?", (session_id,))
        r = cur.fetchone()
        timers = json.loads(r["timers"] or "{}") if r else {}
        timers[timer_name] = timers.get(timer_name, 0) + int(ms)
        self.conn.execute(
            "UPDATE sessions SET timers=?, last_seen_at=? WHERE session_id=?",
            (json.dumps(timers), _utcnow(), session_id),
        )
        self.conn.commit()

    def add_chip_count(self, session_id: str, band: str, n: int = 1) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT chip_counts FROM sessions WHERE session_id=?", (session_id,))
        r = cur.fetchone()
        counts = json.loads(r["chip_counts"] or '{"A":0,"B":0,"C":0,"D":0}') if r else {"A":0,"B":0,"C":0,"D":0}
        if band in counts:
            counts[band] += int(n)
        self.conn.execute(
            "UPDATE sessions SET chip_counts=?, last_seen_at=? WHERE session_id=?",
            (json.dumps(counts), _utcnow(), session_id),
        )
        self.conn.commit()

    def session_snapshot(self, session_id: str) -> Optional[Dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,))
        r = cur.fetchone()
        if not r:
            return None
        return {
            "session_id": r["session_id"],
            "started_at": r["started_at"],
            "last_seen_at": r["last_seen_at"],
            "keystrokes": r["keystrokes"],
            "timers": json.loads(r["timers"] or "{}"),
            "chip_counts": json.loads(r["chip_counts"] or '{"A":0,"B":0,"C":0,"D":0}'),
        }

    # ===== KV =====
    def kv_set(self, k: str, v: Optional[str]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO kv_cache(k,v,updated_at) VALUES (?,?,?)",
            (k, v, _utcnow()),
        )
        self.conn.commit()

    def kv_get(self, k: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT v FROM kv_cache WHERE k=?", (k,))
        r = cur.fetchone()
        return r["v"] if r else None

    # ===== Maintenance =====
    def optimize(self):
        self.conn.execute("PRAGMA optimize")
        self.conn.commit()

    def close(self):
        self.conn.close()
