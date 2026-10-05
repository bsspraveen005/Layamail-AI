"""Gmail access: a real OAuth 2.0 client and a seeded in-memory demo client with the same interface."""
import base64, os, re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from html.parser import HTMLParser
from datetime import date, datetime, time, timedelta, timezone

def day_query(day: date) -> str:
    """Gmail search terms for one local calendar day.
    Epoch seconds are used so the time zone is unambiguous."""
    start = datetime.combine(day, time.min).astimezone()                       # local 00:00
    end = datetime.combine(day + timedelta(days=1), time.min).astimezone()     # next local 00:00
    return f"after:{int(start.timestamp())} before:{int(end.timestamp())}"

SCOPE_MODIFY = ["https://www.googleapis.com/auth/gmail.modify"]   # read, label, trash (no permanent delete)
SCOPE_FULL = ["https://mail.google.com/"]                          # needed only for permanent delete
LABELS = {c: f"LayaMail/{c.capitalize()}" for c in ["essential", "promotional", "other", "unwanted", "review"]}

class _Strip(HTMLParser):
    def __init__(self):
        super().__init__(); self.out = []
    def handle_data(self, d): self.out.append(d)

def html_to_text(html: str) -> str:
    p = _Strip(); p.feed(html); return " ".join(p.out)

def _walk(part, plain, html):
    mime, data = part.get("mimeType", ""), part.get("body", {}).get("data")
    if data and mime == "text/plain": plain.append(base64.urlsafe_b64decode(data).decode("utf-8", "ignore"))
    elif data and mime == "text/html": html.append(base64.urlsafe_b64decode(data).decode("utf-8", "ignore"))
    for p in part.get("parts", []) or []: _walk(p, plain, html)

class GmailClient:
    def __init__(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        self.scopes = SCOPE_FULL if os.getenv("LAYAMAIL_PERMANENT_DELETE") == "1" else SCOPE_MODIFY
        token = os.getenv("LAYAMAIL_TOKEN", "token.json")
        creds = Credentials.from_authorized_user_file(token, self.scopes) if os.path.exists(token) else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(os.getenv("LAYAMAIL_CREDENTIALS", "credentials.json"), self.scopes)
                creds = flow.run_local_server(port=0)
            open(token, "w").write(creds.to_json())
        self.svc = build("gmail", "v1", credentials=creds, cache_discovery=False).users()
        self._label_ids = {}
        self.permanent_delete_available = self.scopes == SCOPE_FULL

    def profile(self): return self.svc.getProfile(userId="me").execute()["emailAddress"]

    def _label_id(self, name):
        if not self._label_ids:
            for l in self.svc.labels().list(userId="me").execute().get("labels", []): self._label_ids[l["name"]] = l["id"]
        if name not in self._label_ids:
            made = self.svc.labels().create(userId="me", body={"name": name, "labelListVisibility": "labelShow",
                                                               "messageListVisibility": "show"}).execute()
            self._label_ids[name] = made["id"]
        return self._label_ids[name]
    
    def list_message_ids(self, day=None, query="in:inbox", max_results=None):
        q = f"{query} {day_query(day)}" if day else query
        ids, token = [], None
        while True:
            r = self.svc.messages().list(userId="me", q=q, maxResults=500, pageToken=token).execute()
            ids += [m["id"] for m in r.get("messages", [])]
            token = r.get("nextPageToken")
            if not token or (max_results and len(ids) >= max_results):
                break
        return ids[:max_results] if max_results else ids
    
    def get_message(self, mid):
        m = self.svc.messages().get(userId="me", id=mid, format="full").execute()
        h = {x["name"].lower(): x["value"] for x in m["payload"].get("headers", [])}
        plain, html = [], []; _walk(m["payload"], plain, html)
        body = "\n".join(plain) or html_to_text("\n".join(html)) or m.get("snippet", "")
        return {"id": mid, "thread_id": m["threadId"], "sender": h.get("from", ""), "sender_email": parseaddr(h.get("from", ""))[1].lower(),
                "subject": h.get("subject", ""), "snippet": m.get("snippet", ""), "body": body,
                "received_at": datetime.fromtimestamp(int(m["internalDate"]) / 1000, timezone.utc).isoformat(),
                "label_ids": m.get("labelIds", []), "has_unsubscribe": "list-unsubscribe" in h}

    def set_category_label(self, mid, category):
        add = [self._label_id(LABELS[category])]
        remove = [self._label_id(n) for k, n in LABELS.items() if k != category and n in self._label_ids]
        self.svc.messages().modify(userId="me", id=mid, body={"addLabelIds": add, "removeLabelIds": remove}).execute()

    def trash(self, mid): self.svc.messages().trash(userId="me", id=mid).execute()
    def untrash(self, mid): self.svc.messages().untrash(userId="me", id=mid).execute()

    def batch_delete(self, ids):
        if not self.permanent_delete_available:
            raise PermissionError("Permanent delete needs the https://mail.google.com/ scope. Set LAYAMAIL_PERMANENT_DELETE=1, delete token.json and sign in again.")
        for i in range(0, len(ids), 1000):
            self.svc.messages().batchDelete(userId="me", body={"ids": ids[i:i + 1000]}).execute()

    def has_replied_to(self, addr):
        return bool(self.svc.messages().list(userId="me", q=f"in:sent to:{addr}", maxResults=1).execute().get("messages"))


_DEMO = [  # sender, subject, body, age_hours, extra_labels, unsubscribe
    ("HDFC Bank <alerts@hdfcbank.example>", "Your credit card statement for September", "Your statement is ready. Payment due on 15 Oct. Total amount due: 12,480.", 30, [], False),
    ("Priya Nair <priya@teamnorth.example>", "Interview panel for Thursday", "Can we confirm the interview slot at 11 AM? Sending the meeting link shortly.", 5, ["IMPORTANT"], False),
    ("Google <no-reply@accounts.google.example>", "Security alert: new sign-in", "A new sign-in to your account. If this was not you, change your password.", 50, [], False),
    ("Landlord <rent@sunrise.example>", "Invoice for October rent", "Please find the invoice and receipt attached. Payment due by the 5th.", 70, [], False),
    ("ShopZone <deals@shopzone.example>", "Flash sale: 60% off everything", "Limited time offer. Unsubscribe any time. New arrivals inside.", 8, [], True),
    ("Travelio <hello@travelio.example>", "Weekend getaways from 2,999", "Book now and save. Exclusive discount coupon inside.", 20, [], True),
    ("Stackly Newsletter <news@stackly.example>", "This week in cloud: 7 links", "Your weekly newsletter. Unsubscribe at the bottom.", 90, [], True),
    ("FitLife <promo@fitlife.example>", "Webinar: build a better routine", "Join our free webinar. Limited time offer on annual plans.", 120, [], True),
    ("LinkedIn <notifications@linkedin.example>", "You appeared in 4 searches", "See who is looking at your profile.", 40, [], False),
    ("GitHub <noreply@github.example>", "[repo] New comment on issue #42", "Someone commented on your issue.", 3, [], False),
    ("Lucky Draw <winner@prize-center.example>", "Congratulations! You have won the lottery", "Claim your prize now. Click here to verify your identity. Act now!", 100, [], False),
    ("Crypto Giveaway <promo@btc-double.example>", "Crypto giveaway: send 1 BTC get 2 back", "100% free. Wire transfer required to unlock. Act now.", 45, [], False),
    ("Dr. James <james@inheritance-fund.example>", "Inheritance of 4.5M USD awaits", "I am a barrister. Please reply with your bank details. Wire transfer fee applies.", 200, [], False),
    ("Best Casino <vip@casino-bonus.example>", "Your VIP casino bonus", "Spin now. 100% free credits. Make $500 a day.", 15, [], False),
    ("Account Support <support@paypa1-secure.example>", "Click here to verify your account", "Your account is limited. Click here to verify immediately.", 10, [], False),
    ("Old Friend <arjun@gmail.example>", "Reunion plans?", "Hey! We are thinking of a get-together in November. Are you in?", 60, [], False),
    ("Mystery Sender <info@random-leads.example>", "Quick question", "Hello, would you like to grow your reach with our service?", 30, [], False),
    ("Priya Nair <priya@teamnorth.example>", "Re: lunch?", "Sure, see you at 1.", 400, [], False),
    ("Cheap Pills <rx@meds-fast.example>", "Viagra 90% off, discreet shipping", "Buy now. 100% free shipping.", 2, [], False),
    ("City Library <desk@library.example>", "Your book is ready for pickup", "The book you reserved is available for the next 7 days.", 26, [], False),
]

class DemoGmail:
    """In-memory stand-in so the whole app (and dashboard) can be tried without Google credentials."""
    permanent_delete_available = True
    def __init__(self):
        now = datetime.now(timezone.utc); self.msgs = {}; self.labels = {}; self.trashed = set(); self.deleted = set()
        for i, (s, subj, body, age, lab, unsub) in enumerate(_DEMO):
            mid = f"demo{i:03d}"
            self.msgs[mid] = {"id": mid, "thread_id": mid, "sender": s, "sender_email": parseaddr(s)[1].lower(), "subject": subj,
                              "snippet": body[:90], "body": body, "received_at": (now - timedelta(hours=age)).isoformat(),
                              "label_ids": lab, "has_unsubscribe": unsub}
    def profile(self): return "demo@layamail.local"
    def list_message_ids(self, day=None, query="", max_results=None):
        ids = [m for m in self.msgs if m not in self.trashed and m not in self.deleted]
        if day:
            ids = [m for m in ids if datetime.fromisoformat(self.msgs[m]["received_at"]).astimezone().date() == day]
        ids.sort(key=lambda i: self.msgs[i]["received_at"], reverse=True)
        return ids[:max_results] if max_results else ids
    def get_message(self, mid): return dict(self.msgs[mid])
    def set_category_label(self, mid, category): self.labels[mid] = LABELS[category]
    def trash(self, mid): self.trashed.add(mid)
    def untrash(self, mid): self.trashed.discard(mid)
    def batch_delete(self, ids): self.deleted.update(ids); self.trashed.difference_update(ids)
    def has_replied_to(self, addr): return addr in {"priya@teamnorth.example", "arjun@gmail.example"}
