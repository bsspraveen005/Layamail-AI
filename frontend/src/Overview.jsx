import React from "react";
import { Card, CAT } from "./ui.jsx";
const ORDER = ["essential", "promotional", "other", "unwanted", "review"];
export default function Overview({ stats }) {
  if (!stats) return null;
  const total = stats.total || 1, maxH = Math.max(1, ...stats.confidence_hist), maxD = Math.max(1, ...stats.daily.map((d) => d.n));
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Card title="Processed" className="lg:col-span-1">
        <div className="font-display text-5xl font-bold">{stats.total}</div>
        <p className="mt-1 text-sm text-muted">emails classified, average confidence {(stats.avg_confidence * 100).toFixed(0)}%</p>
        <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-muted">Waiting for you</dt><dd className="text-xl font-semibold">{stats.queue}</dd></div>
          <div><dt className="text-muted">In Trash</dt><dd className="text-xl font-semibold">{stats.status.trashed || 0}</dd></div>
          <div><dt className="text-muted">Permanently deleted</dt><dd className="text-xl font-semibold">{stats.status.purged || 0}</dd></div>
          <div><dt className="text-muted">Your corrections</dt><dd className="text-xl font-semibold">{stats.corrections}</dd></div>
        </dl>
      </Card>
      <Card title="Where your mail went" className="lg:col-span-2">
        <div className="flex h-5 overflow-hidden rounded bg-line">
          {ORDER.map((k) => stats.categories[k] ? <div key={k} style={{ width: `${(stats.categories[k] / total) * 100}%`, background: CAT[k].color }} title={`${CAT[k].label}: ${stats.categories[k]}`} /> : null)}
        </div>
        <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-5">
          {ORDER.map((k) => (
            <li key={k}><span className="inline-block h-2 w-2 rounded-full align-middle" style={{ background: CAT[k].color }} /> <span className="text-muted">{CAT[k].label}</span>
              <div className="text-xl font-semibold">{stats.categories[k] || 0}</div></li>
          ))}
        </ul>
      </Card>
      <Card title="Confidence spread" className="lg:col-span-2">
        <div className="flex h-32 items-end gap-1.5">
          {stats.confidence_hist.map((n, i) => (
            <div key={i} className="flex flex-1 flex-col items-center justify-end gap-1">
              <span className="text-[11px] text-muted">{n || ""}</span>
              <div className="w-full rounded-t bg-brand" style={{ height: `${(n / maxH) * 100}%`, minHeight: n ? 3 : 0, opacity: 0.35 + i * 0.07 }} />
            </div>
          ))}
        </div>
        <div className="mt-1 flex justify-between text-xs text-muted"><span>0%</span><span>confidence</span><span>100%</span></div>
      </Card>
      <Card title="Last 14 days">
        <div className="flex h-32 items-end gap-1">
          {stats.daily.map((d) => <div key={d.d} title={`${d.d}: ${d.n}`} className="flex-1 rounded-t bg-ink/70" style={{ height: `${(d.n / maxD) * 100}%` }} />)}
          {!stats.daily.length && <p className="text-sm text-muted">Nothing yet. Run a sync.</p>}
        </div>
      </Card>
    </div>
  );
}
