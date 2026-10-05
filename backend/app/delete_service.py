"""All deletion paths. Explicit user clicks always run; dry-run only affects automatic actions."""
from datetime import datetime, timezone
from .db import db, get_settings, log_action

class DeleteError(Exception):
    def __init__(self, msg, code=400): super().__init__(msg); self.code = code

def _email(c, mid):
    return c.execute("SELECT e.*, (SELECT confidence FROM classifications WHERE email_id=e.id ORDER BY id DESC LIMIT 1) AS confidence, "
                     "(SELECT category FROM classifications WHERE email_id=e.id ORDER BY id DESC LIMIT 1) AS predicted FROM emails e WHERE id=?", (mid,)).fetchone()

def trash_emails(gmail, ids, automatic=False, reason="manual trash"):
    s = get_settings(); dry = automatic and s["dry_run"]; done = []
    for mid in ids:
        with db() as c:
            e = _email(c, mid)
            if not e or e["status"] in ("trashed", "purged"): continue
            if not dry:
                gmail.trash(mid)
                c.execute("UPDATE emails SET status='trashed' WHERE id=?", (mid,))
            log_action(c, mid, "trash", ("[dry run] " if dry else "") + reason, s["delete_mode"], automatic, dry, e["confidence"])
            done.append(mid)
    return {"count": len(done), "dry_run": dry, "ids": done}

def keep_emails(gmail, ids, protect_sender=False, to="other"):
    n = 0
    for mid in ids:
        with db() as c:
            e = _email(c, mid)
            if not e: continue
            gmail.set_category_label(mid, to)
            c.execute("UPDATE emails SET status='kept' WHERE id=?", (mid,))
            c.execute("INSERT INTO feedback(email_id,predicted,corrected) VALUES(?,?,?)", (mid, e["predicted"], to))
            log_action(c, mid, "keep", f"kept, relabelled LayaMail/{to.capitalize()}", "", False, False, e["confidence"])
            if protect_sender:
                c.execute("INSERT OR IGNORE INTO protected_senders(email,reason) VALUES(?,?)", (e["sender_email"], "kept by you"))
            n += 1
    return {"count": n}

def undo(gmail, action_id):
    with db() as c:
        a = c.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if not a or a["reverted"]: raise DeleteError("Nothing to undo", 404)
        if a["action"] == "purge": raise DeleteError("Permanently deleted mail cannot be restored", 409)
        if a["action"] != "trash" or a["dry_run"]: raise DeleteError("Only real trash actions can be undone", 409)
        e = _email(c, a["email_id"])
        gmail.untrash(a["email_id"]); gmail.set_category_label(a["email_id"], "review")
        c.execute("UPDATE emails SET status='review' WHERE id=?", (a["email_id"],))
        c.execute("UPDATE actions SET reverted=1 WHERE id=?", (action_id,))
        c.execute("INSERT INTO feedback(email_id,predicted,corrected) VALUES(?,?,?)", (a["email_id"], e["predicted"], "restored"))
        log_action(c, a["email_id"], "untrash", f"undo of action #{action_id}", "", False, False, e["confidence"])
    return {"ok": True}

def _pending_unwanted(c, threshold):
    return c.execute("SELECT e.id, e.sender, e.subject, cl.confidence FROM emails e JOIN classifications cl ON cl.id="
                     "(SELECT MAX(id) FROM classifications WHERE email_id=e.id) WHERE e.status='pending_review' AND cl.confidence>=? "
                     "ORDER BY cl.confidence DESC", (threshold,)).fetchall()

def trash_above(gmail, threshold, preview=True):
    with db() as c: rows = _pending_unwanted(c, threshold)
    if preview:
        return {"count": len(rows), "sample": [{"id": r["id"], "sender": r["sender"], "subject": r["subject"], "confidence": r["confidence"]} for r in rows[:5]]}
    return trash_emails(gmail, [r["id"] for r in rows], reason=f"bulk trash at confidence >= {threshold:.2f}")

def block_sender(gmail, sender_email):
    sender_email = sender_email.lower()
    with db() as c:
        c.execute("INSERT OR IGNORE INTO blocked_senders(email) VALUES(?)", (sender_email,))
        c.execute("DELETE FROM protected_senders WHERE email=?", (sender_email,))
        ids = [r[0] for r in c.execute("SELECT id FROM emails WHERE sender_email=? AND status NOT IN ('trashed','purged')", (sender_email,))]
        log_action(c, None, "block", sender_email, "", False, False, None)
    res = trash_emails(gmail, ids, reason=f"sender blocked: {sender_email}")
    return {"blocked": sender_email, "trashed": res["count"]}

def _purge_candidates(c, older_than_days):
    rows = c.execute("SELECT e.id, e.sender, e.subject, MAX(a.created_at) AS trashed_at FROM emails e JOIN actions a ON a.email_id=e.id "
                     "AND a.action='trash' AND a.dry_run=0 AND a.reverted=0 WHERE e.status='trashed' GROUP BY e.id").fetchall()
    now, out = datetime.now(timezone.utc), []
    for r in rows:
        t = datetime.fromisoformat(r["trashed_at"]).replace(tzinfo=timezone.utc)
        if (now - t).days >= older_than_days: out.append(r)
    return out

def purge_trashed(gmail, older_than_days=0, preview=False, automatic=False):
    """Permanently delete only mail that LayaMail itself trashed."""
    s = get_settings()
    with db() as c: rows = _purge_candidates(c, older_than_days)
    if preview:
        return {"count": len(rows), "sample": [{"id": r["id"], "sender": r["sender"], "subject": r["subject"]} for r in rows[:5]]}
    if not s["permanent_delete_enabled"]: raise DeleteError("Permanent delete is switched off in Settings", 403)
    if automatic and s["dry_run"]:
        with db() as c:
            for r in rows: log_action(c, r["id"], "purge", "[dry run] would permanently delete", s["delete_mode"], True, True)
        return {"count": 0, "dry_run": True, "would_delete": len(rows)}
    if not rows: return {"count": 0}
    try: gmail.batch_delete([r["id"] for r in rows])
    except PermissionError as exc: raise DeleteError(str(exc), 403)
    with db() as c:
        for r in rows:
            c.execute("UPDATE emails SET status='purged' WHERE id=?", (r["id"],))
            log_action(c, r["id"], "purge", "permanently deleted", s["delete_mode"], automatic, False)
    return {"count": len(rows)}
