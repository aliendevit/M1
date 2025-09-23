-- NOTE: PRAGMAs moved to runtime (repo.py / facts_service.py) to avoid parser errors.

-- ===== FACTS (72h context cache) =====
CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,            -- lab | vital | med | note | image
  name TEXT NOT NULL,
  value TEXT,
  time TEXT,                     -- ISO8601
  source_id TEXT                 -- external/local source reference used for citations
);

CREATE INDEX IF NOT EXISTS idx_facts_time ON facts(time);

-- Full-text search for name/value (requires SQLite built with FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
  kind, name, value,
  content='facts', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
  INSERT INTO facts_fts(rowid, kind, name, value) VALUES (new.rowid, new.kind, new.name, new.value);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, kind, name, value) VALUES ('delete', old.rowid, old.kind, old.name, old.value);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
  INSERT INTO facts_fts(facts_fts, rowid, kind, name, value) VALUES ('delete', old.rowid, old.kind, old.name, old.value);
  INSERT INTO facts_fts(rowid, kind, name, value) VALUES (new.rowid, new.kind, new.name, new.value);
END;

-- ===== CHIPS (UI confirmation units + states) =====
CREATE TABLE IF NOT EXISTS chips (
  chip_id TEXT PRIMARY KEY,
  slot TEXT,                     -- e.g., troponin_series
  type TEXT,                     -- value|missing|guard|ambiguity|timer|unit
  band TEXT,                     -- A|B|C|D
  label TEXT,
  proposed TEXT,
  confidence REAL,               -- [0..1]
  risk TEXT,                     -- low|medium|high
  evidence TEXT,                 -- JSON array string of source_ids
  actions TEXT,                  -- JSON array string of allowed actions
  state TEXT DEFAULT 'open',     -- open|accepted|edited|overridden|dismissed
  reason TEXT,                   -- required when overridden
  created_at TEXT NOT NULL,      -- ISO8601
  updated_at TEXT NOT NULL       -- ISO8601
);

CREATE INDEX IF NOT EXISTS idx_chips_band ON chips(band);
CREATE INDEX IF NOT EXISTS idx_chips_state ON chips(state);
CREATE INDEX IF NOT EXISTS idx_chips_updated ON chips(updated_at);

-- ===== SESSIONS (summary only; detailed audit is JSONL) =====
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  keystrokes INTEGER DEFAULT 0,
  timers TEXT,                   -- JSON: {"decode_ms":..., "extract_ms":..., "compose_ms":...}
  chip_counts TEXT               -- JSON: {"A":0,"B":0,"C":0,"D":0}
);

-- ===== KV CACHE (generic small config/state cache) =====
CREATE TABLE IF NOT EXISTS kv_cache (
  k TEXT PRIMARY KEY,
  v TEXT,
  updated_at TEXT NOT NULL
);

-- ===== OPTIONAL: transcripts cache (ASR spans for reproducibility) =====
CREATE TABLE IF NOT EXISTS transcripts (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  spans TEXT,                    -- JSON array of spans
  created_at TEXT NOT NULL
);
