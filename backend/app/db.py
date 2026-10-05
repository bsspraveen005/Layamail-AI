import json, os, sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("LAYAMAIL_DB", "layamail.db")

DEFAULT_SETTINGS = {
    "delete_mode": "manual",        # off | manual | auto_trash | auto_delete
    "trash_threshold": 0.95,        # min confidence for automatic trashing
    "review_below": 0.55,            # below this confidence any email goes to LayaMail/Review
    "min_age_hours": 24,            # never auto-trash mail younger than this
    "daily_cap": 50,                # max automatic trashes per day (circuit breaker)
    "purge_after_days": 7,          # auto_delete: purge LayaMail-trashed mail after N days
    "dry_run": True,                # automatic deletions are only logged, not performed
    "permanent_delete_enabled": False,
    "protect_replied": True,        # never auto-trash senders you have written to
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails(
  id TEXT PRIMARY KEY, thread_id TEXT, sender TEXT, sender_email TEXT, subject TEXT,
  snippet TEXT, received_at TEXT, has_unsubscribe INTEGER DEFAULT 0,
  status TEXT DEFAULT 'labeled', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS classifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT, category TEXT, final_category TEXT,
  priority INTEGER, confidence REAL, scam_prob REAL, model TEXT, scores_json TEXT, reason TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT, action TEXT, detail TEXT, mode TEXT,
  automatic INTEGER DEFAULT 0, dry_run INTEGER DEFAULT 0, reverted INTEGER DEFAULT 0,
  confidence REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS protected_senders(email TEXT PRIMARY KEY, reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS blocked_senders(email TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT, predicted TEXT, corrected TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_cls_email ON classifications(email_id);
CREATE INDEX IF NOT EXISTS idx_act_email ON actions(email_id);
"""

@contextmanager
def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()

def init_db():
    with db() as c:
        c.executescript(SCHEMA)

def get_settings() -> dict:
    out = dict(DEFAULT_SETTINGS)
    with db() as c:
        for r in c.execute("SELECT key, value FROM settings"):
            if r["key"] in out:
                out[r["key"]] = json.loads(r["value"])
    return out

def save_settings(values: dict) -> dict:
    with db() as c:
        for k, v in values.items():
            if k in DEFAULT_SETTINGS:
                c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                          (k, json.dumps(v)))
    return get_settings()

def log_action(c, email_id, action, detail="", mode="", automatic=False, dry_run=False, confidence=None):
    cur = c.execute(
        "INSERT INTO actions(email_id,action,detail,mode,automatic,dry_run,confidence) VALUES(?,?,?,?,?,?,?)",
        (email_id, action, detail, mode, int(automatic), int(dry_run), confidence))
    return cur.lastrowid
