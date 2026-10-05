import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { Btn, Card, Chip, ConfBar, Confirm } from "./ui.jsx";
export default function Queue({ version, onChange, status }) {
  const [rows, setRows] = useState([]); const [sel, setSel] = useState(new Set());
  const [thr, setThr] = useState(0.95); const [dlg, setDlg] = useState(null); const [msg, setMsg] = useState("");
  const load = () => api.emails("?status=pending_review,review").then((r) => { setRows(r); setSel(new Set()); });
  useEffect(() => { load(); }, [version]);
  const ids = [...sel];
  const done = async (text, fn) => { try { const r = await fn(); setMsg(typeof text === "function" ? text(r) : text); } catch (e) { setMsg(e.message); } setDlg(null); await load(); onChange(); };
  const toggle = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const openAbove = async () => { const p = await api.trashAbove(thr, true); setDlg({ kind: "above", ...p }); };
  const openPurge = async () => { const p = await api.purge(0, true); setDlg({ kind: "purge", ...p }); };
  return (
    <div className="space-y-5">
      <Card title="Review queue" aside={<span className="text-sm text-muted">{rows.length} waiting</span>}>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Btn kind="danger" disabled={!ids.length} onClick={() => setDlg({ kind: "trash" })}>Trash selected ({ids.length})</Btn>
          <Btn disabled={!ids.length} onClick={() => done((r) => `Kept ${r.count} email(s) and relabelled them Other.`, () => api.keep(ids))}>Keep selected</Btn>
          <Btn disabled={!ids.length} onClick={() => done((r) => `Kept ${r.count}; those senders are now protected.`, () => api.keep(ids, true))}>Keep and protect sender</Btn>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <label htmlFor="thr" className="text-muted">Trash all unwanted at</label>
            <input id="thr" type="range" min="0.8" max="0.99" step="0.01" value={thr} onChange={(e) => setThr(+e.target.value)} />
            <span className="w-10 tabular-nums">{Math.round(thr * 100)}%+</span>
            <Btn onClick={openAbove}>Preview</Btn>
          </div>
        </div>
        {msg && <p className="mb-3 rounded bg-paper px-3 py-2 text-sm" role="status">{msg}</p>}
        <ul>
          {rows.map((r) => (
            <li key={r.id} className="flex items-start gap-3 border-t border-line py-3">
              <input type="checkbox" className="mt-1" checked={sel.has(r.id)} onChange={() => toggle(r.id)} aria-label={`Select ${r.subject}`} />
              <div className="min-w-0 flex-1"><div className="truncate font-medium">{r.subject}</div><div className="truncate text-xs text-muted">{r.sender}</div><div className="mt-0.5 text-xs text-muted">{r.reason}</div></div>
              <div className="hidden w-28 sm:block"><Chip cat={r.category === "unwanted" && r.final_category === "unwanted" ? "unwanted" : r.final_category} /><div className="mt-1"><ConfBar v={r.confidence} /></div></div>
              <Btn kind="ghost" onClick={() => setDlg({ kind: "block", row: r })}>Block sender</Btn>
            </li>))}
        </ul>
        {!rows.length && <p className="py-6 text-sm text-muted">The queue is empty. Nothing needs your attention.</p>}
      </Card>
      <Card title="LayaMail trash" aside={<Btn onClick={openPurge} disabled={!status?.permanent_delete_scope}>Review permanent delete</Btn>}>
        <p className="text-sm text-muted">Emails LayaMail moved to Gmail Trash stay recoverable for 30 days. Permanent deletion only ever touches mail LayaMail itself trashed, never the rest of your Trash.{!status?.permanent_delete_scope && " It is off until you enable the broader Gmail permission (see README)."}</p>
      </Card>
      <Confirm open={dlg?.kind === "trash"} title={`Move ${ids.length} email(s) to Trash?`} body="They can be restored from Activity or from Gmail Trash for 30 days." confirmLabel="Move to Trash" danger
        onCancel={() => setDlg(null)} onConfirm={() => done((r) => `Moved ${r.count} to Trash.`, () => api.trash(ids))} />
      <Confirm open={dlg?.kind === "above"} title={`${dlg?.count} email(s) at ${Math.round(thr * 100)}%+ confidence`} confirmLabel="Trash them" danger
        body={<ul className="list-disc pl-5">{dlg?.sample?.map((s) => <li key={s.id}>{s.subject}</li>)}{dlg?.count > 5 && <li>and {dlg.count - 5} more</li>}{!dlg?.count && <li>Nothing matches.</li>}</ul>}
        onCancel={() => setDlg(null)} onConfirm={() => done((r) => `Moved ${r.count} to Trash.`, () => api.trashAbove(thr, false))} />
      <Confirm open={dlg?.kind === "block"} title="Block this sender?" confirmLabel="Block and trash" danger
        body={`${dlg?.row?.sender} will be trashed now, and everything they send later is treated as unwanted.`}
        onCancel={() => setDlg(null)} onConfirm={() => done((r) => `Blocked ${r.blocked}; trashed ${r.trashed}.`, () => api.block(dlg.row.sender_email))} />
      <Confirm open={dlg?.kind === "purge"} title={`Permanently delete ${dlg?.count} email(s)?`} confirmLabel="Delete forever" danger
        body={<><p>This cannot be undone. Only mail LayaMail trashed is included.</p><ul className="mt-2 list-disc pl-5">{dlg?.sample?.map((s) => <li key={s.id}>{s.subject}</li>)}</ul></>}
        onCancel={() => setDlg(null)} onConfirm={() => done((r) => `Permanently deleted ${r.count}.`, () => api.purge(0, false))} />
    </div>
  );
}
