"""Local email classification with the open-source Laya decision model.

Laya answers typed questions (choice / score / noul) about a text in one forward pass,
so there is no text generation and nothing to parse. If Laya is unavailable the module
falls back to a keyword heuristic whose confidence is capped below the auto-trash
threshold, so the fallback can never delete anything on its own.
"""
import os, re, threading

CATEGORIES = ["essential", "promotional", "other", "unwanted"]

QUESTIONS = {
    "category": {
        "type": "choice",
        "instructions": "Which category best describes this email?",
        "criteria": {
            "essential": "personal or work messages, bills, receipts, bank, security alerts, jobs, appointments, anything the recipient must see",
            "promotional": "marketing, newsletters, sales, discounts, product announcements from legitimate companies",
            "other": "automated notifications, social updates, mailing lists, and anything not clearly in the other categories",
            "unwanted": "spam, scams, phishing, lottery or prize claims, fake invoices, unsolicited cold outreach with no value",
        },
    },
    "priority": {
        "type": "score",
        "instructions": "How important and time-sensitive is this email for the recipient?",
        "criteria": ["ignorable", "useful", "important and time-sensitive"],
    },
    "scam": {"type": "noul", "instructions": "Does this email look like phishing, a scam, or deceptive spam?"},
}

_lock = threading.Lock()
_router = None
_active = None  # "laya" | "heuristic"

def _load_laya():
    global _router
    if _router is None:
        from laya import Router
        _router = Router()  # downloads checkpoints on first use, then runs fully offline
    return _router

def active_model() -> str:
    return _active or os.getenv("LAYAMAIL_CLASSIFIER", "laya")

def build_state(sender, subject, body):
    body = re.sub(r"\s+", " ", body or "").strip()[:1800]
    return f"From: {sender}\nSubject: {subject}\n\n{body}"

def classify(sender: str, subject: str, body: str, has_unsubscribe: bool = False) -> dict:
    global _active
    if os.getenv("LAYAMAIL_CLASSIFIER", "laya") == "laya":
        try:
            with _lock:
                router = _load_laya()
                res = router.predict(build_state(sender, subject, body), QUESTIONS)
            _active = "laya"
            return _from_laya(res)
        except Exception as exc:  # missing package, offline first run, etc.
            print(f"[layamail] Laya unavailable ({exc!r}); using heuristic fallback")
    _active = "heuristic"
    return _heuristic(sender, subject, body, has_unsubscribe)

def _from_laya(res: dict) -> dict:
    ans = res["answers"]
    cat = ans["category"]
    category = cat["choice"]
    conf = float(cat.get("answer_confidence", cat.get("confidence", 0.0)))
    score = float(ans["priority"].get("score", 0.0))          # 0..2 for three criteria
    priority = max(1, min(10, round(1 + score / 2 * 9)))
    return {
        "category": category if category in CATEGORIES else "other",
        "confidence": conf,
        "priority": priority,
        "scam_prob": float(ans["scam"].get("noul", 0.0)),
        "scores": {"routing": res.get("routing", {}), "category": {k: v for k, v in cat.items() if k != "text"}},
        "model": "laya:" + str(res.get("routing", {}).get("model", "english")),
    }

_UNWANTED = r"lottery|you have won|claim your prize|crypto giveaway|wire transfer|nigerian|inheritance|act now|click here to verify|100% free|make \$\d+|viagra|casino"
_PROMO = r"% off|sale|discount|coupon|deal|newsletter|unsubscribe|limited time|offer|new arrivals|webinar"
_ESSENTIAL = r"invoice|receipt|statement|interview|appointment|security alert|password|otp|verification code|payment due|booking|boarding|meeting|offer letter"

def _heuristic(sender, subject, body, has_unsub):
    t = f"{sender} {subject} {body}".lower()
    if re.search(_UNWANTED, t):
        return _h("unwanted", 0.90, 1, 0.9)
    if re.search(_ESSENTIAL, t) and not has_unsub:
        return _h("essential", 0.80, 8, 0.05)
    if has_unsub or re.search(_PROMO, t):
        return _h("promotional", 0.75, 2, 0.1)
    return _h("other", 0.50, 3, 0.1)

def _h(cat, conf, prio, scam):
    # confidence capped at 0.90: never reaches the default 0.95 auto-trash threshold
    return {"category": cat, "confidence": min(conf, 0.90), "priority": prio, "scam_prob": scam,
            "scores": {}, "model": "heuristic"}
