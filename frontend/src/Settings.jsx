import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { Btn, Card } from "./ui.jsx";
const MODES = [
  ["off", "Label only", "Applies LayaMail/Unwanted and nothing else."],
  ["manual", "Manual review", "Unwanted mail waits in the queue until you trash or keep it."],
  ["auto_trash", "Auto-trash", "High-confidence unwanted mail goes to Gmail Trash automatically."],
  ["auto_delete", "Auto-trash and purge", "Also permanently deletes LayaMail-trashed mail after a delay. Needs the broader Gmail permission."],
];
const Row = ({ label, hint, children }) => (<div className="flex items-center justify-between gap-6 border-t border-line py-3"><div><div className="text-sm font-medium">{label}</div>{hint && <div className="text-xs text-muted">{hint}</div>}</div>{children}</div>);
export default function Settings({ status }) {
  const [s, setS] = useState(null); const [msg, setMsg] = useState("");
  useEffect(() => { api.settings().then(setS); }, []);
  if (!s) return null;
  const set = (k, v) => setS({ ...s, [k]: v });
  const num = (k, props) => <input type="number" value={s[k]} onChange={(e) => set(k, +e.target.value)} className="w-24 rounded-md border border-line bg-card px-2 py-1 text-sm" {...props} />;
  const toggle = (k) => <input type="checkbox" className="h-5 w-5" checked={s[k]} onChange={(e) => set(k, e.target.checked)} />;
  const save = async () => { try { setS(await api.saveSettings(s)); setMsg("Saved."); } catch (e) { setMsg(e.message); } };
  return (
    <div className="space-y-5">
      <Card title="Delete mode">
        <div className="grid gap-3 sm:grid-cols-2">
          {MODES.map(([v, name, d]) => (
            <label key={v} className={`cursor-pointer rounded-md border p-3 ${s.delete_mode === v ? "border-brand bg-paper" : "border-line"}`}>
              <input type="radio" name="mode" className="mr-2" checked={s.delete_mode === v} onChange={() => set("delete_mode", v)} /><span className="font-medium">{name}</span>
              <p className="mt-1 text-xs text-muted">{d}</p>
            </label>))}
        </div>
      </Card>
      <Card title="Safety rails">
        <Row label="Dry run" hint="Automatic deletions are logged but not performed. Your own clicks always run."><div>{toggle("dry_run")}</div></Row>
        <Row label={`Auto-trash confidence: ${Math.round(s.trash_threshold * 100)}%`} hint="Unwanted mail below this goes to LayaMail/Review instead."><input type="range" min="0.8" max="0.99" step="0.01" value={s.trash_threshold} onChange={(e) => set("trash_threshold", +e.target.value)} /></Row>
        <Row label="Send to Review below" hint="Any category under this confidence is held for you."><input type="range" min="0" max="0.9" step="0.05" value={s.review_below} onChange={(e) => set("review_below", +e.target.value)} /></Row>
        <Row label="Minimum age before auto-trash (hours)">{num("min_age_hours", { min: 0 })}</Row>
        <Row label="Daily auto-trash cap" hint="Circuit breaker if the model misbehaves.">{num("daily_cap", { min: 0 })}</Row>
        <Row label="Protect senders you have written to" hint="Checks your Sent mail.">{toggle("protect_replied")}</Row>
      </Card>
      <Card title="Permanent delete">
        <Row label="Allow permanent deletion" hint={status?.permanent_delete_scope ? "Gmail permission is granted." : "Needs LAYAMAIL_PERMANENT_DELETE=1 and a fresh sign-in (see README)."}>{toggle("permanent_delete_enabled")}</Row>
        <Row label="Purge LayaMail-trashed mail after (days)" hint="Used by Auto-trash and purge.">{num("purge_after_days", { min: 1 })}</Row>
      </Card>
      <div className="flex items-center gap-3"><Btn kind="primary" onClick={save}>Save settings</Btn><span className="text-sm text-muted" role="status">{msg}</span></div>
    </div>
  );
}
