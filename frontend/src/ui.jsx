import React from "react";
export const CAT = {
  essential: { label: "Essential", color: "var(--color-essential)" },
  promotional: { label: "Promotional", color: "var(--color-promo)" },
  other: { label: "Other", color: "var(--color-other)" },
  unwanted: { label: "Unwanted", color: "var(--color-unwanted)" },
  review: { label: "Review", color: "var(--color-review)" },
};
export const Chip = ({ cat }) => {
  const c = CAT[cat] || CAT.other;
  return <span className="inline-flex items-center gap-1.5 text-xs font-medium"><span className="h-2 w-2 rounded-full" style={{ background: c.color }} />{c.label}</span>;
};
export const ConfBar = ({ v }) => (
  <div className="flex items-center gap-2" title={`${(v * 100).toFixed(1)}%`}>
    <div className="h-1.5 w-16 rounded bg-line"><div className="h-1.5 rounded bg-brand" style={{ width: `${v * 100}%` }} /></div>
    <span className="text-xs tabular-nums text-muted">{(v * 100).toFixed(0)}%</span>
  </div>
);
export const Btn = ({ kind = "default", className = "", ...p }) => {
  const k = { default: "border border-line bg-card hover:bg-paper", primary: "bg-brand text-white hover:opacity-90",
    danger: "bg-unwanted text-white hover:opacity-90", ghost: "text-muted hover:text-ink" }[kind];
  return <button {...p} className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed ${k} ${className}`} />;
};
export const Card = ({ title, aside, children, className = "" }) => (
  <section className={`rounded-lg border border-line bg-card p-5 ${className}`}>
    {(title || aside) && <div className="mb-4 flex items-center justify-between"><h2 className="font-display text-base font-semibold">{title}</h2>{aside}</div>}
    {children}
  </section>
);
export function Confirm({ open, title, body, confirmLabel = "Confirm", danger, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-lg bg-card p-6 shadow-xl">
        <h3 className="font-display text-lg font-semibold">{title}</h3>
        <div className="mt-2 text-sm text-muted">{body}</div>
        <div className="mt-5 flex justify-end gap-2">
          <Btn onClick={onCancel}>Cancel</Btn>
          <Btn kind={danger ? "danger" : "primary"} onClick={onConfirm}>{confirmLabel}</Btn>
        </div>
      </div>
    </div>
  );
}
export const when = (iso) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
