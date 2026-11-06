"""Tiny SQLite layer. The SQL is plain and standard, so moving to PostgreSQL later is easy
(see docs/ROADMAP.md)."""
import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('creator','reviewer','manager','admin')),
  team TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS guideline_docs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, version TEXT DEFAULT '1',
  content TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rules(
  id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, category TEXT NOT NULL,
  title TEXT NOT NULL, description TEXT DEFAULT '', severity TEXT DEFAULT 'medium',
  kind TEXT NOT NULL, config TEXT DEFAULT '{}', guideline_ref TEXT DEFAULT '',
  human_lock INTEGER DEFAULT 0, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS glossary(
  id INTEGER PRIMARY KEY AUTOINCREMENT, preferred TEXT NOT NULL, banned TEXT DEFAULT '[]',
  kind TEXT DEFAULT 'term', note TEXT DEFAULT '', case_sensitive INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS assets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, kind TEXT DEFAULT 'config',
  value TEXT DEFAULT '{}', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS facts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL, statement TEXT NOT NULL,
  value TEXT DEFAULT '', category TEXT DEFAULT 'general', source_doc TEXT DEFAULT '',
  source_ref TEXT DEFAULT '', owner TEXT DEFAULT '', confidential INTEGER DEFAULT 0,
  verified_on TEXT, expires_on TEXT, review_interval_days INTEGER DEFAULT 90,
  version INTEGER DEFAULT 1, keywords TEXT DEFAULT '', active INTEGER DEFAULT 1, updated_at TEXT);
CREATE TABLE IF NOT EXISTS fact_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fact_id INTEGER NOT NULL, version INTEGER NOT NULL,
  statement TEXT, value TEXT, verified_on TEXT, expires_on TEXT, changed_by TEXT,
  changed_at TEXT, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS contents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, fmt TEXT NOT NULL,
  owner_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft', current_version INTEGER DEFAULT 1,
  channel TEXT DEFAULT 'website', ai_assisted INTEGER DEFAULT 0, filename TEXT DEFAULT '',
  created_at TEXT, updated_at TEXT, published_at TEXT, needs_refresh INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS content_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, version INTEGER NOT NULL,
  text TEXT NOT NULL, meta TEXT DEFAULT '{}', analysis TEXT DEFAULT '{}', note TEXT DEFAULT '',
  created_by INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS findings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, version INTEGER NOT NULL,
  rule_code TEXT NOT NULL, category TEXT, severity TEXT, span_start INTEGER, span_end INTEGER,
  excerpt TEXT, message TEXT, source_type TEXT, source_ref TEXT, source_id INTEGER,
  source_confidential INTEGER DEFAULT 0, confidence TEXT, confidence_score REAL,
  suggestions TEXT DEFAULT '[]', needs_human INTEGER DEFAULT 0, human_lock INTEGER DEFAULT 0,
  decision TEXT DEFAULT 'open', decision_by INTEGER, decision_reason TEXT, final_text TEXT,
  apply_start INTEGER, apply_end INTEGER, decided_at TEXT, produced_by TEXT DEFAULT 'rules',
  created_at TEXT);
CREATE TABLE IF NOT EXISTS comments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, version INTEGER,
  author_id INTEGER, body TEXT NOT NULL, anchor_start INTEGER, anchor_end INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, version INTEGER,
  user_id INTEGER, decision TEXT, note TEXT DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS publications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, version INTEGER,
  published_at TEXT, published_by INTEGER, snapshot TEXT DEFAULT '{}', active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS passports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, publication_id INTEGER,
  fact_id INTEGER, fact_version INTEGER, claim_text TEXT, matched_raw TEXT DEFAULT '',
  approved_by INTEGER, created_at TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS refresh_proposals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, passport_id INTEGER,
  old_text TEXT, new_text TEXT, message TEXT, status TEXT DEFAULT 'open', created_at TEXT,
  resolved_by INTEGER, resolved_at TEXT);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL,
  ref TEXT DEFAULT '', link TEXT DEFAULT '', created_at TEXT, read INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT, entity TEXT,
  entity_id INTEGER, detail TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS ai_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, content_id INTEGER, step TEXT, engine TEXT,
  model TEXT, data_sent TEXT, masked_items INTEGER DEFAULT 0, note TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_findings_content ON findings(content_id, version);
CREATE INDEX IF NOT EXISTS idx_passports_fact ON passports(fact_id, active);
"""


def jdump(v):
    return json.dumps(v, ensure_ascii=False)


def jload(s, default=None):
    if s in (None, ""):
        return default
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default


class DB:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.conn.execute("PRAGMA foreign_keys=ON")

    def init(self):
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def q(self, sql, params=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def run(self, sql, params=()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid

    def insert(self, table, data):
        cols = ",".join(data)
        marks = ",".join("?" * len(data))
        return self.run(f"INSERT INTO {table}({cols}) VALUES({marks})", tuple(data.values()))

    def update(self, table, row_id, data):
        if not data:
            return
        sets = ",".join(f"{k}=?" for k in data)
        self.run(f"UPDATE {table} SET {sets} WHERE id=?", (*data.values(), row_id))

    def close(self):
        self.conn.close()
