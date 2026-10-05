"""Sync -> classify -> decide -> label -> (maybe) trash. Every step is written to SQLite."""
import json
from datetime import datetime, timezone
from .db import db, get_settings, log_action
from .classifier import classify, active_model

def _age_hours(iso):
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600

def is_protected(gmail, e, settings):
    with db() as c:
        if c.execute("SELECT 1 FROM protected_senders WHERE email=?", (e["sender_email"],)).fetchone():
            return "sender is on the protected list"
    if "STARRED" in e["label_ids"] or "IMPORTANT" in e["label_ids"]:
        return "starred or marked important in Gmail"
    if settings["protect_replied"] and gmail.has_replied_to(e["sender_email"]):
        with db() as c:
            c.execute("INSERT OR IGNORE INTO protected_senders(email,reason) VALUES(?,?)", (e["sender_email"], "you have written to this sender"))
        return "you have written to this sender"
    return None

def _auto_trashed_today(c):
    return c.execute("SELECT COUNT(*) FROM actions WHERE action='trash' AND automatic=1 AND dry_run=0 AND date(created_at)=date('now')").fetchone()[0]

def process_email(gmail, e, settings, summary):
    with db() as c:
        blocked = c.execute("SELECT 1 FROM blocked_senders WHERE email=?", (e["sender_email"],)).fetchone()
    if blocked:
        cls = {"category": "unwanted", "confidence": 1.0, "priority": 1, "scam_prob": 1.0, "scores": {}, "model": "rule:blocked-sender"}
    else:
        cls = classify(e["sender"], e["subject"], e["body"], e["has_unsubscribe"])
    cat, conf, mode = cls["category"], cls["confidence"], settings["delete_mode"]
    final, status, reason, do_trash = cat, "labeled", "", False

    if conf < settings["review_below"]:
        final, status, reason = "review", "review", f"confidence {conf:.2f} below review threshold"
    elif cat == "unwanted":
        prot = is_protected(gmail, e, settings)
        if prot:
            final, status, reason = "review", "review", f"looked unwanted but protected: {prot}"
        elif conf < settings["trash_threshold"]:
            final, status, reason = "review", "review", f"unwanted at {conf:.2f}, under trash threshold {settings['trash_threshold']:.2f}"
        else:
            status = "pending_review" if mode != "off" else "labeled"
            reason = "high-confidence unwanted"
            if mode in ("auto_trash", "auto_delete"):
                with db() as c: capped = _auto_trashed_today(c) >= settings["daily_cap"]
                if capped: reason += "; daily cap reached, left for manual review"
                elif _age_hours(e["received_at"]) < settings["min_age_hours"]: reason += f"; younger than {settings['min_age_hours']}h, left for manual review"
                else: do_trash = True

    gmail.set_category_label(e["id"], final)
    with db() as c:
        c.execute("INSERT OR REPLACE INTO emails(id,thread_id,sender,sender_email,subject,snippet,received_at,has_unsubscribe,status) VALUES(?,?,?,?,?,?,?,?,?)",
                  (e["id"], e["thread_id"], e["sender"], e["sender_email"], e["subject"], e["snippet"], e["received_at"], int(e["has_unsubscribe"]), status))
        c.execute("INSERT INTO classifications(email_id,category,final_category,priority,confidence,scam_prob,model,scores_json,reason) VALUES(?,?,?,?,?,?,?,?,?)",
                  (e["id"], cat, final, cls["priority"], conf, cls["scam_prob"], cls["model"], json.dumps(cls["scores"], default=str), reason))
        log_action(c, e["id"], "label", f"LayaMail/{final.capitalize()} ({reason or 'classified'})", mode, True, False, conf)
    summary[final] = summary.get(final, 0) + 1
    if do_trash:
        from .delete_service import trash_emails
        trash_emails(gmail, [e["id"]], automatic=True, reason="auto-trash: " + reason)
        summary["auto_trashed"] = summary.get("auto_trashed", 0) + 1

def sync(gmail, day=None, limit=None, query="in:inbox"):
    """Classify every inbox email on `day` (or all recent mail if day is None). limit=None means no cap."""
    settings, summary = get_settings(), {"processed": 0, "day": str(day) if day else None}
    with db() as c: known = {r[0] for r in c.execute("SELECT id FROM emails")}
    ids = gmail.list_message_ids(day=day, query=query, max_results=limit)
    summary["found"] = len(ids)
    for mid in ids:
        if mid in known: continue
        process_email(gmail, gmail.get_message(mid), settings, summary)
        summary["processed"] += 1
    if settings["delete_mode"] == "auto_delete" and settings["permanent_delete_enabled"]:
        from .delete_service import purge_trashed
        summary["auto_purged"] = purge_trashed(gmail, settings["purge_after_days"], automatic=True)["count"]
    summary["model"] = active_model()
    return summary
