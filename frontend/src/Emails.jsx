import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { Card, Chip, ConfBar, when } from "./ui.jsx";
export default function Emails({ version }) {
  const [rows, setRows] = useState([]); const [cat, setCat] = useState("");
  useEffect(() => { api.emails(cat ? `?category=${cat}` : "").then(setRows); }, [cat, version]);
  return (
    <Card title="Classified emails" aside={
      <select value={cat} onChange={(e) => setCat(e.target.value)} className="rounded-md border border-line bg-card px-2 py-1 text-sm" aria-label="Filter by category">
        <option value="">All categories</option>
        {["essential", "promotional", "other", "unwanted", "review"].map((c) => <option key={c} value={c}>{c}</option>)}
      </select>}>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted"><tr><th className="pb-2 font-medium">Email</th><th className="pb-2 font-medium">Category</th><th className="pb-2 font-medium">Priority</th><th className="pb-2 font-medium">Confidence</th><th className="pb-2 font-medium">State</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-line align-top">
                <td className="max-w-md py-2.5 pr-4"><div className="truncate font-medium">{r.subject || "(no subject)"}</div><div className="truncate text-xs text-muted">{r.sender} · {when(r.received_at)}</div>{r.reason && <div className="text-xs text-muted">{r.reason}</div>}</td>
                <td className="py-2.5 pr-4"><Chip cat={r.final_category} /></td>
                <td className="py-2.5 pr-4 tabular-nums">{r.priority}/10</td>
                <td className="py-2.5 pr-4"><ConfBar v={r.confidence} /></td>
                <td className="py-2.5 text-xs text-muted">{r.status.replace("_", " ")}</td>
              </tr>))}
          </tbody>
        </table>
        {!rows.length && <p className="py-6 text-sm text-muted">No emails yet. Press Sync.</p>}
      </div>
    </Card>
  );
}
