import os, threading
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from . import delete_service as ds
from .classifier import active_model
from .db import DEFAULT_SETTINGS, db, get_settings, init_db, save_settings
from .pipeline import sync
from datetime import date

app = FastAPI(title="LayaMail AI")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
init_db()
_gmail, _lock = None, threading.Lock()
DEMO = os.getenv("LAYAMAIL_DEMO") == "1"

def gmail():
    global _gmail
    with _lock:
        if _gmail is None:
            if DEMO:
                from .gmail_client import DemoGmail; _gmail = DemoGmail()
            else:
                from .gmail_client import GmailClient; _gmail = GmailClient()
    return _gmail

def guard(fn, *a, **k):
    try: return fn(*a, **k)
    except ds.DeleteError as e: raise HTTPException(e.code, str(e))

class SettingsIn(BaseModel):
    delete_mode: Literal["off", "manual", "auto_trash", "auto_delete"]
    trash_threshold: float = Field(ge=0.80, le=0.99)
    review_below: float = Field(ge=0.0, le=0.9)
    min_age_hours: int = Field(ge=0, le=720)
    daily_cap: int = Field(ge=0, le=1000)
    purge_after_days: int = Field(ge=1, le=60)
    dry_run: bool
    permanent_delete_enabled: bool
    protect_replied: bool

class Ids(BaseModel): ids: list[str]
class KeepIn(Ids): protect_sender: bool = False; to: Literal["essential", "promotional", "other"] = "other"
class AboveIn(BaseModel): threshold: float = Field(ge=0.8, le=1.0); preview: bool = True
class BlockIn(BaseModel): sender_email: str
class PurgeIn(BaseModel): older_than_days: int = Field(default=0, ge=0); preview: bool = True
class FeedbackIn(BaseModel): email_id: str; corrected: Literal["essential", "promotional", "other", "unwanted"]
@app.post("/api/sync")

def run_sync(day: Optional[date] = None, limit: Optional[int] = Query(None, ge=1)):
    return sync(gmail(), day=day, limit=limit)

@app.get("/api/status")

def status():
    return {"demo": DEMO, "model": active_model(), "permanent_delete_scope": bool(os.getenv("LAYAMAIL_PERMANENT_DELETE") == "1" or DEMO)}

@app.post("/api/sync")
def run_sync(limit: int = Query(50, ge=1, le=500)):
    return sync(gmail(), limit)

@app.get("/api/settings")
def read_settings(): return get_settings()

@app.put("/api/settings")
def write_settings(s: SettingsIn):
    if s.permanent_delete_enabled and not (DEMO or os.getenv("LAYAMAIL_PERMANENT_DELETE") == "1"):
        raise HTTPException(400, "Set LAYAMAIL_PERMANENT_DELETE=1, delete token.json and sign in again before enabling permanent delete.")
    return save_settings(s.model_dump())

@app.get("/api/stats")
def stats():
    with db() as c:
        last = "(SELECT MAX(id) FROM classifications GROUP BY email_id)"
        cats = {r[0]: r[1] for r in c.execute(f"SELECT final_category, COUNT(*) FROM classifications WHERE id IN {last} GROUP BY 1")}
        st = {r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM emails GROUP BY 1")}
        hist = [0] * 10
        for (v,) in c.execute(f"SELECT confidence FROM classifications WHERE id IN {last}"): hist[min(9, int(v * 10))] += 1
        daily = [dict(r) for r in c.execute("SELECT date(created_at) d, COUNT(*) n FROM emails GROUP BY 1 ORDER BY 1 DESC LIMIT 14")][::-1]
        avg = c.execute(f"SELECT AVG(confidence) FROM classifications WHERE id IN {last}").fetchone()[0]
        total = c.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        corrections = c.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    return {"total": total, "categories": cats, "status": st, "confidence_hist": hist, "daily": daily,
            "avg_confidence": avg or 0, "queue": st.get("pending_review", 0) + st.get("review", 0), "corrections": corrections}

@app.get("/api/emails")
def emails(category: Optional[str] = None, status: Optional[str] = None, limit: int = Query(100, le=500), offset: int = 0):
    sql = ("SELECT e.id, e.sender, e.sender_email, e.subject, e.received_at, e.status, e.has_unsubscribe, cl.category, cl.final_category, "
           "cl.priority, cl.confidence, cl.scam_prob, cl.model, cl.reason FROM emails e JOIN classifications cl ON cl.id="
           "(SELECT MAX(id) FROM classifications WHERE email_id=e.id) WHERE 1=1")
    args = []
    if category: sql += " AND cl.final_category=?"; args.append(category)
    if status:
        marks = ",".join("?" for _ in status.split(",")); sql += f" AND e.status IN ({marks})"; args += status.split(",")
    sql += " ORDER BY e.received_at DESC LIMIT ? OFFSET ?"; args += [limit, offset]
    with db() as c: return [dict(r) for r in c.execute(sql, args)]

@app.get("/api/actions")
def actions(limit: int = Query(100, le=500)):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT a.*, e.sender, e.subject FROM actions a LEFT JOIN emails e ON e.id=a.email_id "
                                           "WHERE a.action!='label' OR a.id IN (SELECT id FROM actions ORDER BY id DESC LIMIT 30) "
                                           "ORDER BY a.id DESC LIMIT ?", (limit,))]

@app.post("/api/actions/{action_id}/undo")
def undo(action_id: int): return guard(ds.undo, gmail(), action_id)

@app.post("/api/queue/trash")
def q_trash(b: Ids): return ds.trash_emails(gmail(), b.ids)

@app.post("/api/queue/keep")
def q_keep(b: KeepIn): return ds.keep_emails(gmail(), b.ids, b.protect_sender, b.to)

@app.post("/api/queue/trash-above")
def q_above(b: AboveIn): return ds.trash_above(gmail(), b.threshold, b.preview)

@app.post("/api/senders/block")
def block(b: BlockIn): return ds.block_sender(gmail(), b.sender_email)

@app.post("/api/trash/purge")
def purge(b: PurgeIn): return guard(ds.purge_trashed, gmail(), b.older_than_days, b.preview)

@app.post("/api/feedback")
def feedback(b: FeedbackIn):
    with db() as c:
        row = c.execute("SELECT category FROM classifications WHERE email_id=? ORDER BY id DESC LIMIT 1", (b.email_id,)).fetchone()
        if not row: raise HTTPException(404, "Unknown email")
        c.execute("INSERT INTO feedback(email_id,predicted,corrected) VALUES(?,?,?)", (b.email_id, row[0], b.corrected))
    if b.corrected != "unwanted": gmail().set_category_label(b.email_id, b.corrected)
    return {"ok": True}
