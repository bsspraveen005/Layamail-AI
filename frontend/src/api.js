async function req(path, opts = {}) {
  const res = await fetch("/api" + path, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

const post = (p, body = {}) => req(p, { method: "POST", body: JSON.stringify(body) });
export const api = {
  status: () => req("/status"),
  stats: () => req("/stats"),
  emails: (q = "") => req("/emails" + q),
  actions: () => req("/actions"),
  settings: () => req("/settings"),
  saveSettings: (s) => req("/settings", { method: "PUT", body: JSON.stringify(s) }),
  sync: (day) => post(`/sync${day ? `?day=${day}` : ""}`),
  undo: (id) => post(`/actions/${id}/undo`),
  trash: (ids) => post("/queue/trash", { ids }),
  keep: (ids, protect_sender = false) => post("/queue/keep", { ids, protect_sender }),
  trashAbove: (threshold, preview) => post("/queue/trash-above", { threshold, preview }),
  block: (sender_email) => post("/senders/block", { sender_email }),
  purge: (older_than_days, preview) => post("/trash/purge", { older_than_days, preview }),
};
