import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { Btn, Card, when } from "./ui.jsx";
export default function Activity({ version, onChange }) {
  const [rows, setRows] = useState([]); const [err, setErr] = useState("");
  useEffect(() => { api.actions().then(setRows); }, [version]);
  const undo = async (id) => { try { await api.undo(id); setErr(""); onChange(); } catch (e) { setErr(e.message); } };
  return (
    <Card title="Action history">
      {err && <p className="mb-3 rounded bg-paper px-3 py-2 text-sm text-unwanted" role="alert">{err}</p>}
      <ul>
        {rows.map((a) => (
          <li key={a.id} className="flex items-start gap-3 border-t border-line py-2.5 text-sm">
            <span className="w-14 shrink-0 font-medium">{a.action}</span>
            <div className="min-w-0 flex-1"><div className="truncate">{a.subject || a.detail}</div><div className="truncate text-xs text-muted">{a.detail}</div></div>
            <div className="shrink-0 text-right text-xs text-muted">{when(a.created_at)}<br />{a.automatic ? "automatic" : "manual"}{a.dry_run ? " · dry run" : ""}{a.reverted ? " · undone" : ""}</div>
            {a.action === "trash" && !a.dry_run && !a.reverted && <Btn onClick={() => undo(a.id)}>Undo</Btn>}
          </li>))}
      </ul>
      {!rows.length && <p className="py-6 text-sm text-muted">No actions yet.</p>}
    </Card>
  );
}
