const BASE = "/api";

async function get(path) {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export function fetchStats() {
  return get("/stats");
}

export function fetchKocs(params) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v !== null && v !== undefined) qs.append(k, v);
  });
  return get(`/kocs?${qs.toString()}`);
}

export function fetchKocDetail(id) {
  return get(`/kocs/${id}`);
}

export function fetchSyncLogs(limit = 20) {
  return get(`/sync-logs?limit=${limit}`);
}

// Trả về dòng sync_log "running" ngay lập tức (đồng bộ chạy ở background).
export async function triggerSync() {
  const r = await fetch(`${BASE}/sync`, { method: "POST" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
