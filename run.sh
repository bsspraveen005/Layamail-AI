#!/usr/bin/env bash
# Starts backend (demo mode unless LAYAMAIL_DEMO=0) and the dashboard.
set -e
(cd backend && LAYAMAIL_DEMO=${LAYAMAIL_DEMO:-1} uvicorn app.main:app --port 8000) &
(cd frontend && npm run dev)
