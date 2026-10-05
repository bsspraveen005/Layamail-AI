import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { Btn } from "./ui.jsx";
import Overview from "./Overview.jsx";
import Emails from "./Emails.jsx";
import Queue from "./Queue.jsx";
import Activity from "./Activity.jsx";
import Settings from "./Settings.jsx";

const TABS = [["overview", "Overview"], ["emails", "Emails"], ["queue", "Queue"], ["activity", "Activity"], ["settings", "Settings"]];

export default function App() {
  const [tab, setTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState(null);
  const [day, setDay] = useState(new Date().toLocaleDateString("en-CA")); // yyyy-mm-dd in local time
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const refresh = useCallback(() => {
    api.stats().then(setStats).catch(() => {});
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    api.status().then(setStatus).catch(() => setNote("Backend not reachable on port 8000."));
    refresh();
  }, [refresh]);

  const sync = async () => {
    setBusy(true);
    setNote("");
    try {
      const r = await api.sync(day);
      setNote(`Found ${r.found}, processed ${r.processed} new email(s)${r.auto_trashed ? `, auto-trashed ${r.auto_trashed}` : ""}.`);
      api.status().then(setStatus);
    } catch (e) {
      setNote(e.message);
    }
    setBusy(false);
    refresh();
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16">
      <header className="flex flex-wrap items-center gap-4 py-6">
        <h1 className="font-display text-2xl font-bold">LayaMail<span className="text-brand"> AI</span></h1>
        {status && (
          <span className="rounded-full border border-line px-2.5 py-0.5 text-xs text-muted">
            {status.demo ? "demo inbox · " : ""}model: {status.model}
          </span>
        )}
        <span className="text-sm text-muted" role="status">{note}</span>
        <input
          type="date"
          value={day}
          onChange={(e) => setDay(e.target.value)}
          className="ml-auto rounded-md border border-line bg-card px-2 py-1.5 text-sm"
          aria-label="Date to process"
        />
        <Btn kind="primary" onClick={sync} disabled={busy || !day}>
          {busy ? "Syncing…" : "Sync this day"}
        </Btn>
      </header>

      <nav className="mb-6 flex gap-1 border-b border-line" aria-label="Sections">
        {TABS.map(([k, l]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            aria-current={tab === k ? "page" : undefined}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${tab === k ? "border-brand text-ink" : "border-transparent text-muted hover:text-ink"}`}
          >
            {l}
            {k === "queue" && stats?.queue ? <span className="ml-1.5 rounded-full bg-review px-1.5 text-xs text-white">{stats.queue}</span> : null}
          </button>
        ))}
      </nav>

      {tab === "overview" && <Overview stats={stats} />}
      {tab === "emails" && <Emails version={version} />}
      {tab === "queue" && <Queue version={version} onChange={refresh} status={status} />}
      {tab === "activity" && <Activity version={version} onChange={refresh} />}
      {tab === "settings" && <Settings status={status} />}
    </div>
  );
}