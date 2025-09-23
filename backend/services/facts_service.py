# path: backend/services/facts_service.py
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List

def _load_config() -> Dict:
    try:
        import yaml
        with open(os.path.join("config", "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {"cache": {"db": "data/chart.sqlite", "window_hours": 72}, "privacy": {"log_retention_days": 30}}

DDL = """
PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  value TEXT,
  time TEXT,
  source_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_time ON facts(time);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
  kind, name, value,
  content='facts', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
  INSERT INTO facts_fts(rowid, kind, name, value) VALUES (new.rowid, new.kind, new.name, new.value);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, kind, name, value) VALUES('delete', old.rowid, old.kind, old.name, old.value);
END;
CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, kind, name, value) VALUES('delete', old.rowid, old.kind, old.name, old.value);
  INSERT INTO facts_fts(rowid, kind, name, value) VALUES (new.rowid, new.kind, new.name, new.value);
END;
"""

DDL_FALLBACK_NO_FTS = """
PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  value TEXT,
  time TEXT,
  source_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_time ON facts(time);
"""

class FactsService:
    """
    SQLite-backed 72h context facts with FTS5.
    """
    _instance: "FactsService" | None = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "FactsService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.cfg = _load_config()
        db_path = self.cfg.get("cache", {}).get("db", "data/chart.sqlite")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Set PRAGMAs at connection level too (idempotent)
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        try:
            self.conn.executescript(DDL)
            self.conn.commit()
        except sqlite3.OperationalError as e:
            if "fts5" in str(e).lower():
                self.conn.executescript(DDL_FALLBACK_NO_FTS)
                self.conn.commit()
            else:
                raise

    def get_context(self, window_hours: int | None = None) -> Dict:
        wh = window_hours or self.cfg.get("cache", {}).get("window_hours", 72)
        cutoff = (datetime.utcnow() - timedelta(hours=wh)).isoformat()
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

    def add_fact(self, fact: Dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO facts(id,kind,name,value,time,source_id) VALUES (?,?,?,?,?,?)",
            (fact.get("id"), fact.get("kind"), fact.get("name"), fact.get("value"), fact.get("time"), fact.get("source_id")),
        )
        self.conn.commit()

    def fts_search(self, query: str, limit: int = 50) -> List[Dict]:
        cur = self.conn.cursor()
        try:
            cur.execute(
                """SELECT f.* FROM facts f
                   JOIN facts_fts ft ON ft.rowid = f.rowid
                   WHERE facts_fts MATCH ? LIMIT ?""",
                (query, limit),
            )
            return [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            like = f"%{query}%"
            cur.execute(
                "SELECT * FROM facts WHERE name LIKE ? OR value LIKE ? LIMIT ?",
                (like, like, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def retention_cleanup(self) -> int:
        days = int(self.cfg.get("privacy", {}).get("log_retention_days", 30))
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        cur = self.conn.cursor()
        cur.execute("DELETE FROM facts WHERE time < ?", (cutoff,))
        self.conn.commit()
        return cur.rowcount
