"""Versioned database migrations. They build the whole database from nothing, on SQLite and on PostgreSQL,
and they upgrade an older database one step at a time. Applied versions are recorded in `schema_migrations`.

Rules for adding one: append a new (version, name, [statements]) entry, never edit an old one.
Use `{PK}` for auto-numbered ids; everything else is plain standard SQL."""
from . import clock

_V1 = [
    """CREATE TABLE IF NOT EXISTS users(
      id {PK}, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('creator','reviewer','manager','admin')),
      team TEXT DEFAULT '', created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS guideline_docs(
      id {PK}, title TEXT NOT NULL, version TEXT DEFAULT '1', content TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS rules(
      id {PK}, code TEXT UNIQUE NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, description TEXT DEFAULT '',
      severity TEXT DEFAULT 'medium', kind TEXT NOT NULL, config TEXT DEFAULT '{}', guideline_ref TEXT DEFAULT '',
      human_lock INTEGER DEFAULT 0, active INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS glossary(
      id {PK}, preferred TEXT NOT NULL, banned TEXT DEFAULT '[]', kind TEXT DEFAULT 'term', note TEXT DEFAULT '',
      case_sensitive INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS assets(
      id {PK}, name TEXT UNIQUE NOT NULL, kind TEXT DEFAULT 'config', value TEXT DEFAULT '{}', notes TEXT DEFAULT '')""",
    """CREATE TABLE IF NOT EXISTS facts(
      id {PK}, key TEXT UNIQUE NOT NULL, statement TEXT NOT NULL, value TEXT DEFAULT '', category TEXT DEFAULT 'general',
      source_doc TEXT DEFAULT '', source_ref TEXT DEFAULT '', owner TEXT DEFAULT '', confidential INTEGER DEFAULT 0,
      verified_on TEXT, expires_on TEXT, review_interval_days INTEGER DEFAULT 90, version INTEGER DEFAULT 1,
      keywords TEXT DEFAULT '', active INTEGER DEFAULT 1, updated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS fact_versions(
      id {PK}, fact_id INTEGER NOT NULL, version INTEGER NOT NULL, statement TEXT, value TEXT, verified_on TEXT,
      expires_on TEXT, changed_by TEXT, changed_at TEXT, note TEXT DEFAULT '')""",
    """CREATE TABLE IF NOT EXISTS contents(
      id {PK}, title TEXT NOT NULL, fmt TEXT NOT NULL, owner_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
      current_version INTEGER DEFAULT 1, channel TEXT DEFAULT 'website', ai_assisted INTEGER DEFAULT 0,
      filename TEXT DEFAULT '', created_at TEXT, updated_at TEXT, published_at TEXT, needs_refresh INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS content_versions(
      id {PK}, content_id INTEGER NOT NULL, version INTEGER NOT NULL, text TEXT NOT NULL, meta TEXT DEFAULT '{}',
      analysis TEXT DEFAULT '{}', note TEXT DEFAULT '', created_by INTEGER, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS findings(
      id {PK}, content_id INTEGER NOT NULL, version INTEGER NOT NULL, rule_code TEXT NOT NULL, category TEXT,
      severity TEXT, span_start INTEGER, span_end INTEGER, excerpt TEXT, message TEXT, source_type TEXT, source_ref TEXT,
      source_id INTEGER, source_confidential INTEGER DEFAULT 0, confidence TEXT, confidence_score REAL,
      suggestions TEXT DEFAULT '[]', needs_human INTEGER DEFAULT 0, human_lock INTEGER DEFAULT 0,
      decision TEXT DEFAULT 'open', decision_by INTEGER, decision_reason TEXT, final_text TEXT, apply_start INTEGER,
      apply_end INTEGER, decided_at TEXT, produced_by TEXT DEFAULT 'rules', created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS comments(
      id {PK}, content_id INTEGER NOT NULL, version INTEGER, author_id INTEGER, body TEXT NOT NULL,
      anchor_start INTEGER, anchor_end INTEGER, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS approvals(
      id {PK}, content_id INTEGER NOT NULL, version INTEGER, user_id INTEGER, decision TEXT, note TEXT DEFAULT '',
      created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS publications(
      id {PK}, content_id INTEGER NOT NULL, version INTEGER, published_at TEXT, published_by INTEGER,
      snapshot TEXT DEFAULT '{}', active INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS passports(
      id {PK}, content_id INTEGER NOT NULL, publication_id INTEGER, fact_id INTEGER, fact_version INTEGER,
      claim_text TEXT, matched_raw TEXT DEFAULT '', approved_by INTEGER, created_at TEXT, active INTEGER DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS refresh_proposals(
      id {PK}, content_id INTEGER NOT NULL, passport_id INTEGER, old_text TEXT, new_text TEXT, message TEXT,
      status TEXT DEFAULT 'open', created_at TEXT, resolved_by INTEGER, resolved_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS notifications(
      id {PK}, user_id INTEGER NOT NULL, message TEXT NOT NULL, ref TEXT DEFAULT '', link TEXT DEFAULT '',
      created_at TEXT, read INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS audit_log(
      id {PK}, ts TEXT, actor TEXT, action TEXT, entity TEXT, entity_id INTEGER, detail TEXT DEFAULT '')""",
    """CREATE TABLE IF NOT EXISTS ai_log(
      id {PK}, ts TEXT, content_id INTEGER, step TEXT, engine TEXT, model TEXT, data_sent TEXT,
      masked_items INTEGER DEFAULT 0, note TEXT DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS idx_findings_content ON findings(content_id, version)",
    "CREATE INDEX IF NOT EXISTS idx_passports_fact ON passports(fact_id, active)",
]

_V2 = [
    """CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY, value TEXT DEFAULT '', updated_at TEXT, updated_by TEXT DEFAULT '')""",
]

_V3 = [
    # Per-person choices about where alerts go. Slack and webhook addresses are organisation settings.
    """CREATE TABLE IF NOT EXISTS notification_prefs(
      user_id INTEGER PRIMARY KEY, email_enabled INTEGER DEFAULT 1, slack_enabled INTEGER DEFAULT 1,
      webhook_enabled INTEGER DEFAULT 0, digest_enabled INTEGER DEFAULT 1, updated_at TEXT)""",
    # Alerts waiting to be sent outside the app. The in-app notice is always created at once.
    """CREATE TABLE IF NOT EXISTS alert_queue(
      id {PK}, user_id INTEGER NOT NULL, message TEXT NOT NULL, link TEXT DEFAULT '', ref TEXT DEFAULT '',
      kind TEXT DEFAULT 'alert', status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0, created_at TEXT,
      processed_at TEXT)""",
    # One row per attempt to deliver, for the audit trail and for retries.
    """CREATE TABLE IF NOT EXISTS alert_deliveries(
      id {PK}, queue_id INTEGER, user_id INTEGER, channel TEXT NOT NULL, target TEXT DEFAULT '',
      subject TEXT DEFAULT '', status TEXT NOT NULL, error TEXT DEFAULT '', ts TEXT)""",
    """CREATE TABLE IF NOT EXISTS scheduler_runs(
      id {PK}, job TEXT NOT NULL, trigger TEXT DEFAULT 'schedule', started_at TEXT, finished_at TEXT,
      status TEXT DEFAULT 'running', new_alerts INTEGER DEFAULT 0, delivered INTEGER DEFAULT 0, failed INTEGER DEFAULT 0,
      detail TEXT DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS idx_alert_queue_status ON alert_queue(status)",
]

_V4 = [
    """CREATE TABLE IF NOT EXISTS accuracy_runs(
      id {PK}, started_at TEXT, finished_at TEXT, dataset_name TEXT, dataset_size INTEGER, modes TEXT DEFAULT '[]',
      result TEXT DEFAULT '{}', run_by TEXT DEFAULT '')""",
]

MIGRATIONS = [
    (1, "base schema from Round 2", _V1),
    (2, "settings store", _V2),
    (3, "alerts, notification preferences and scheduler log", _V3),
    (4, "accuracy lab runs", _V4),
]


def migrate(db):
    db.exec_ddl("CREATE TABLE IF NOT EXISTS schema_migrations("
                "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
    applied = {r["version"] for r in db.q("SELECT version FROM schema_migrations")}
    done = []
    for version, name, statements in MIGRATIONS:
        if version in applied:
            continue
        db.exec_ddl(statements)
        db.run("INSERT INTO schema_migrations(version, name, applied_at) VALUES(?,?,?)", (version, name, clock.now()))
        done.append(version)
    return done


def current_version(db):
    row = db.one("SELECT MAX(version) v FROM schema_migrations")
    return (row or {}).get("v") or 0
