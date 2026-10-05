# LayaMail AI

Local-first Gmail triage. The open-source [Laya](https://github.com/NandhaKishorM/laya) decision model classifies each
email as Essential, Promotional, Other or Unwanted, with a priority and a confidence score. Labels are applied in Gmail,
every decision is written to SQLite, and nothing is sent to a paid LLM API.

## Quick start (no Google account needed)

```bash
# terminal 1: backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
LAYAMAIL_DEMO=1 uvicorn app.main:app --port 8000

# terminal 2: dashboard
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Demo mode seeds a sample inbox and touches nothing real. The first classification downloads the Laya checkpoint
(about 800 MB, once); after that it runs offline. If Laya cannot load, a keyword fallback is used and its confidence
is capped below the auto-trash threshold, so the fallback can never delete anything by itself.

## Connect real Gmail

1. In Google Cloud Console create a project, enable the Gmail API, and create an OAuth client of type **Desktop app**.
2. Save the JSON as `backend/credentials.json`. While the app is in "Testing", add your address as a test user.
3. Run without `LAYAMAIL_DEMO`. A browser window opens for consent; the token is stored in `backend/token.json`.

Default scope is `gmail.modify` (read, label, move to Trash). It cannot permanently delete.

## Delete options

| Mode | Behaviour |
|---|---|
| Label only | Applies `LayaMail/Unwanted`. |
| Manual review (default) | Unwanted mail waits in the Queue; you trash or keep it. |
| Auto-trash | Unwanted mail at or above the threshold (default 95%) goes to Gmail Trash. |
| Auto-trash and purge | Also permanently deletes mail LayaMail trashed, after N days. |

Safety rails: dry run (on by default; it only affects automatic actions), confidence threshold, minimum email age,
daily cap, protected senders (starred, important, anyone you have written to, anyone you chose to protect), a Review
label for anything uncertain, bulk trash with preview, sender blocking, and one-click Undo for every real trash.
Permanent delete only ever touches mail LayaMail itself trashed.

To enable permanent delete: set `LAYAMAIL_PERMANENT_DELETE=1`, delete `token.json`, sign in again (this requests the
broad `https://mail.google.com/` scope), then switch it on in Settings.

## Accuracy: read this

Laya's own docs report that the shipped checkpoints work zero-shot but that fine-tuning on your own domain is where
accuracy jumps (0.766 vs 0.362 on their typed-decisions benchmark). Run in **dry run** for a week, correct mistakes
in the Queue (they are saved in the `feedback` table), and use that data with Laya's fine-tuning notebook before
trusting auto-trash.

## Layout

```
backend/app/classifier.py      Laya typed questions + fallback
backend/app/pipeline.py        sync, classify, decide, label
backend/app/delete_service.py  trash, keep, undo, bulk, block, purge
backend/app/gmail_client.py    OAuth client + demo client
backend/app/db.py              SQLite schema and settings
frontend/src/                  React + Vite + Tailwind dashboard
```
