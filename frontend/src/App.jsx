import { useEffect, useState, useCallback, useRef } from "react";
import { fetchStats, fetchKocs, fetchKocDetail, triggerSync, fetchSyncLogs } from "./api";
import {
  Users, DollarSign, Refresh, Clock, CheckCircle, AlertTriangle, Loader,
  Search, Sun, Moon, ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown,
  ExternalLink, X, TrendingUp, Activity, Inbox,
} from "./icons";

/* ----------------------------------------------------------- formatters */
const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
const compact = (n) =>
  n == null ? "—" : new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
const money = (n, c) =>
  n == null ? "—" : `${Number(Math.round(n)).toLocaleString("en-US")}`;
const dt = (s) => (s ? new Date(s).toLocaleString("vi-VN") : "—");
const dtShort = (s) =>
  s ? new Date(s).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";

/* ----------------------------------------------------------- theme hook */
function useTheme() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("koc-theme");
    if (saved) return saved;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("koc-theme", theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

/* ----------------------------------------------------------- app shell */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const [stats, setStats] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [detail, setDetail] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const loadStats = useCallback(async () => {
    try { const s = await fetchStats(); setStats(s); return s; }
    catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  // Đồng bộ chạy ở background -> poll /api/stats đến khi status != "running".
  const onSync = async () => {
    setSyncing(true);
    try {
      await triggerSync();              // trả về ngay (HTTP 202, log "running")
      for (let i = 0; i < 40; i++) {    // poll tối đa ~60s
        await sleep(1500);
        const s = await loadStats();
        if (s?.last_sync && s.last_sync.status !== "running") break;
      }
      setReloadKey((k) => k + 1);       // làm mới bảng sau khi đồng bộ xong
    } catch (e) {
      alert("Đồng bộ lỗi: " + e.message);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="app">
      <header className="appbar">
        <div className="appbar-inner">
          <div className="brand">
            <div className="brand-mark"><Activity size={22} /></div>
            <div className="brand-text">
              <h1>KOC Data System</h1>
              <div className="sub">Theo dõi follower &amp; doanh thu KOC TikTok</div>
            </div>
          </div>
          <div className="appbar-actions">
            <button
              className="btn icon ghost"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
              title={theme === "dark" ? "Giao diện sáng" : "Giao diện tối"}
            >
              {theme === "dark" ? <Sun /> : <Moon />}
            </button>
            <button className="btn primary" onClick={onSync} disabled={syncing} aria-busy={syncing}>
              {syncing ? <Loader /> : <Refresh />}
              <span className="btn-text">{syncing ? "Đang đồng bộ…" : "Đồng bộ ngay"}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="wrap">
        <div className="section-head">
          <h2>Tổng quan</h2>
          <span className="hint">Số liệu cập nhật theo lần đồng bộ gần nhất</span>
          <button className="btn ghost btn-history" onClick={() => setShowHistory(true)}>
            <Clock size={16} /> <span className="btn-text">Lịch sử đồng bộ</span>
          </button>
        </div>
        <Dashboard stats={stats} />

        <div className="section-head">
          <h2>Danh sách KOC</h2>
          <span className="hint">Tìm kiếm, lọc và sắp xếp — nhấn vào dòng để xem chi tiết</span>
        </div>
        <KocTable reloadKey={reloadKey} onRowClick={async (id) => setDetail(await fetchKocDetail(id))} />
      </main>

      {detail && <DetailModal koc={detail} onClose={() => setDetail(null)} />}
      {showHistory && <SyncHistoryModal onClose={() => setShowHistory(false)} />}
    </div>
  );
}

/* ----------------------------------------------------------- dashboard */
const STATUS = {
  success: { cls: "success", label: "Thành công", Ico: CheckCircle },
  running: { cls: "running", label: "Đang chạy", Ico: Loader },
  failed:  { cls: "failed",  label: "Thất bại", Ico: AlertTriangle },
};

function Dashboard({ stats }) {
  const loading = stats == null;
  const last = stats?.last_sync;
  const st = (last && STATUS[last.status]) || { cls: "neutral", label: last?.status || "—", Ico: Clock };

  return (
    <section className="kpis" aria-label="Chỉ số tổng quan">
      <Kpi
        label="Tổng số KOC" icon={<Users size={20} />}
        value={loading ? null : compact(stats.total_koc)}
        foot={loading ? "" : `${fmt(stats.total_koc)} hồ sơ trong hệ thống`}
        loading={loading}
      />
      <Kpi
        label="Đồng bộ gần nhất" icon={<Clock size={20} />} iconTone="amber"
        value={loading ? null : dtShort(last?.started_at)} valueSm
        foot={loading ? "" : (last ? `Nguồn: ${last.source} · ${last.trigger_type}` : "Chưa có")}
        loading={loading}
      />
      <Kpi
        label="Trạng thái" icon={<Activity size={20} />}
        iconTone={st.cls === "failed" ? "red" : st.cls === "success" ? "green" : "amber"}
        custom={<span className={`badge ${st.cls}`}><st.Ico /> {st.label}</span>}
        foot={loading ? "" : (last?.finished_at ? `Hoàn tất ${dtShort(last.finished_at)}` : "—")}
        loading={loading}
      />
      <Kpi
        label="Kết quả lần cuối" icon={<TrendingUp size={20} />} iconTone="green"
        value={loading ? null : (last ? `+${last.records_inserted}` : "—")} valueSm
        foot={loading ? "" : (last ? `${last.records_inserted} mới · ${last.records_updated} cập nhật · ${last.records_fetched} tải về` : "—")}
        loading={loading}
      />
    </section>
  );
}

function Kpi({ label, icon, iconTone, value, valueSm, custom, foot, loading }) {
  return (
    <div className="kpi">
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        <span className={`kpi-ico ${iconTone || ""}`}>{icon}</span>
      </div>
      {loading ? (
        <span className="skel" style={{ width: "60%", height: 22 }} />
      ) : custom ? (
        <div>{custom}</div>
      ) : (
        <div className={`kpi-value num ${valueSm ? "sm" : ""}`}>{value}</div>
      )}
      {loading ? <span className="skel" style={{ width: "80%", height: 11 }} /> : <div className="kpi-foot">{foot}</div>}
    </div>
  );
}

/* ----------------------------------------------------------- table */
const PAGE_LIMIT = 12;

function KocTable({ onRowClick, reloadKey }) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: PAGE_LIMIT });
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    q: "", min_follower: "", max_follower: "", min_revenue: "", max_revenue: "",
    sort: "follower", order: "desc", page: 1, limit: PAGE_LIMIT,
  });
  const [qInput, setQInput] = useState("");
  const firstLoad = useRef(true);

  // debounce the free-text search so we don't hammer the API on each keystroke
  useEffect(() => {
    const id = setTimeout(() => setFilters((f) => ({ ...f, q: qInput, page: 1 })), 300);
    return () => clearTimeout(id);
  }, [qInput]);

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await fetchKocs(filters)); }
    catch (e) { console.error(e); }
    finally { setLoading(false); firstLoad.current = false; }
  }, [filters]);

  useEffect(() => { load(); }, [load, reloadKey]);

  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v, page: 1 }));
  const toggleSort = (col) =>
    setFilters((f) => ({
      ...f, sort: col,
      order: f.sort === col && f.order === "desc" ? "asc" : "desc", page: 1,
    }));
  const sortState = (col) =>
    filters.sort === col ? (filters.order === "desc" ? "descending" : "ascending") : "none";
  const SortIco = (col) =>
    filters.sort !== col ? <ArrowUpDown size={14} /> : filters.order === "desc" ? <ArrowDown size={14} /> : <ArrowUp size={14} />;

  const totalPages = Math.max(1, Math.ceil(data.total / data.limit));
  const startIdx = (data.page - 1) * data.limit;

  return (
    <section className="panel" aria-label="Bảng KOC">
      <div className="toolbar">
        <div className="field field-search">
          <label htmlFor="koc-q">Tìm kiếm</label>
          <div className="input-wrap">
            <span className="lead"><Search size={16} /></span>
            <input id="koc-q" className="input" type="search" inputMode="search"
              placeholder="Tìm theo tên KOC…" value={qInput}
              onChange={(e) => setQInput(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Follower</label>
          <div className="range-pair">
            <input className="input num" type="number" min="0" placeholder="Từ" aria-label="Follower từ"
              value={filters.min_follower} onChange={(e) => set("min_follower", e.target.value)} />
            <span className="range-sep">–</span>
            <input className="input num" type="number" min="0" placeholder="Đến" aria-label="Follower đến"
              value={filters.max_follower} onChange={(e) => set("max_follower", e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Doanh thu (USD)</label>
          <div className="range-pair">
            <input className="input num" type="number" min="0" placeholder="Từ" aria-label="Doanh thu từ"
              value={filters.min_revenue} onChange={(e) => set("min_revenue", e.target.value)} />
            <span className="range-sep">–</span>
            <input className="input num" type="number" min="0" placeholder="Đến" aria-label="Doanh thu đến"
              value={filters.max_revenue} onChange={(e) => set("max_revenue", e.target.value)} />
          </div>
        </div>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th style={{ width: 48 }}>#</th>
              <th>KOC</th>
              <th>Kênh</th>
              <th aria-sort={sortState("follower")}
                  onClick={() => toggleSort("follower")}
                  className={`num-col sortable ${filters.sort === "follower" ? "active" : ""}`}>
                <span className="th-in">Follower {SortIco("follower")}</span>
              </th>
              <th aria-sort={sortState("revenue")}
                  onClick={() => toggleSort("revenue")}
                  className={`num-col sortable ${filters.sort === "revenue" ? "active" : ""}`}>
                <span className="th-in">Doanh thu {SortIco("revenue")}</span>
              </th>
              <th>Cập nhật</th>
            </tr>
          </thead>
          <tbody>
            {loading && firstLoad.current
              ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
              : data.items.map((k, i) => (
                  <tr key={k.id} className="row" tabIndex={0} role="button"
                    onClick={() => onRowClick(k.id)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onRowClick(k.id); } }}>
                    <td><span className="rank num">{startIdx + i + 1}</span></td>
                    <td>
                      <div className="koc-cell">
                        <Avatar src={k.avatar_url} name={k.display_name} />
                        <div className="koc-name">
                          <b>{k.display_name}</b>
                          <div className="koc-handle">{k.username}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <a className="cell-link" href={k.channel_url} target="_blank" rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}>
                        Xem kênh <ExternalLink size={13} />
                      </a>
                    </td>
                    <td className="num-col num">{fmt(k.follower_count)}</td>
                    <td className="num-col num">
                      <span className="revenue-val">{money(k.revenue, k.currency)}</span>
                      <span className="revenue-cur">{k.currency}</span>
                    </td>
                    <td className="koc-handle" style={{ whiteSpace: "nowrap" }}>{dtShort(k.last_synced_at)}</td>
                  </tr>
                ))}
            {!loading && data.items.length === 0 && (
              <tr>
                <td colSpan="6">
                  <div className="empty">
                    <span className="empty-ico"><Inbox size={26} /></span>
                    <b>Không tìm thấy KOC nào</b>
                    <span>Thử nới lỏng bộ lọc hoặc xoá ô tìm kiếm.</span>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <span>
          {data.total > 0
            ? <>Hiển thị <b className="num">{startIdx + 1}–{Math.min(startIdx + data.limit, data.total)}</b> / <b className="num">{fmt(data.total)}</b> KOC</>
            : "Không có dữ liệu"}
        </span>
        <div className="pager-ctrl">
          <button className="btn icon" disabled={data.page <= 1}
            aria-label="Trang trước"
            onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>
            <ChevronLeft size={18} />
          </button>
          <span className="page-now">{data.page} / {totalPages}</span>
          <button className="btn icon" disabled={data.page >= totalPages}
            aria-label="Trang sau"
            onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>
            <ChevronRight size={18} />
          </button>
        </div>
      </div>
    </section>
  );
}

function SkeletonRow() {
  return (
    <tr>
      <td><span className="skel" style={{ width: 24, height: 24, borderRadius: 7 }} /></td>
      <td><div className="koc-cell">
        <span className="skel circle" />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="skel" style={{ width: 120 }} />
          <span className="skel" style={{ width: 70, height: 10 }} />
        </div>
      </div></td>
      <td><span className="skel" style={{ width: 70 }} /></td>
      <td className="num-col"><span className="skel" style={{ width: 70 }} /></td>
      <td className="num-col"><span className="skel" style={{ width: 80 }} /></td>
      <td><span className="skel" style={{ width: 90 }} /></td>
    </tr>
  );
}

/* ----------------------------------------------------------- detail modal */
function DetailModal({ koc, onClose }) {
  const closeRef = useRef(null);
  const [metric, setMetric] = useState("follower"); // follower | revenue

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  const series = (koc.snapshots || []).map((s) =>
    metric === "follower" ? s.follower_count : (s.revenue == null ? null : Number(s.revenue))
  );
  const times = (koc.snapshots || []).map((s) => s.captured_at);

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={`Chi tiết ${koc.display_name}`}
        onClick={(e) => e.stopPropagation()}>
        <button className="close" ref={closeRef} onClick={onClose} aria-label="Đóng"><X size={18} /></button>
        <div className="modal-pad">
          <div className="detail-head">
            <Avatar src={koc.avatar_url} name={koc.display_name} className="avatar lg" />
            <div>
              <h2>{koc.display_name}</h2>
              <div className="detail-meta">
                <span className="koc-handle">{koc.username}</span>
                {koc.category && <span className="chip">{koc.category}</span>}
                {koc.region && <span className="chip">{koc.region}</span>}
                {koc.channel_url && (
                  <a className="cell-link" href={koc.channel_url} target="_blank" rel="noreferrer">
                    Kênh TikTok <ExternalLink size={13} />
                  </a>
                )}
              </div>
            </div>
          </div>

          <div className="detail-grid">
            <MiniKpi label="Follower" value={fmt(koc.follower_count)} />
            <MiniKpi label={`Doanh thu (${koc.revenue_period || "30d"})`} value={`${money(koc.revenue)} ${koc.currency || ""}`} />
            <MiniKpi label="Cập nhật" value={dtShort(koc.last_synced_at)} />
          </div>

          <div className="chart-head">
            <h3>Lịch sử tăng trưởng</h3>
            <div className="seg" role="group" aria-label="Chọn chỉ số biểu đồ">
              <button aria-pressed={metric === "follower"} onClick={() => setMetric("follower")}>Follower</button>
              <button aria-pressed={metric === "revenue"} onClick={() => setMetric("revenue")}>Doanh thu</button>
            </div>
          </div>
          <div className="chart-card">
            <AreaChart values={series} times={times} />
            <div className="chart-foot">
              <span>{koc.snapshots?.length || 0} bản ghi lịch sử</span>
              {times.length >= 1 && <span>{dtShort(times[0])} → {dtShort(times[times.length - 1])}</span>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const MiniKpi = ({ label, value }) => (
  <div className="mini-kpi"><div className="l">{label}</div><div className="v num">{value}</div></div>
);

/* Avatar có fallback: nếu ảnh lỗi (vd unavatar.io không phản hồi) -> hiện
   chữ cái đầu trên nền màu, không để vỡ ảnh. */
function Avatar({ src, name, className = "avatar" }) {
  const [err, setErr] = useState(false);
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  if (!src || err) {
    return <span className={`${className} avatar-fallback`} aria-hidden="true">{initial}</span>;
  }
  return (
    <img className={className} src={src} alt="" loading="lazy"
      referrerPolicy="no-referrer" onError={() => setErr(true)} />
  );
}

/* ----------------------------------------------------------- sync history modal */
function SyncHistoryModal({ onClose }) {
  const closeRef = useRef(null);
  const [logs, setLogs] = useState(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    fetchSyncLogs(20).then(setLogs).catch((e) => { console.error(e); setLogs([]); });
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Lịch sử đồng bộ"
        onClick={(e) => e.stopPropagation()}>
        <button className="close" ref={closeRef} onClick={onClose} aria-label="Đóng"><X size={18} /></button>
        <div className="modal-pad">
          <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 600 }}>Lịch sử đồng bộ</h2>
          <p className="koc-handle" style={{ marginTop: 0, marginBottom: 16 }}>20 lần đồng bộ gần nhất</p>

          {logs == null ? (
            <div className="empty"><Loader size={26} /><span>Đang tải…</span></div>
          ) : logs.length === 0 ? (
            <div className="empty"><span className="empty-ico"><Inbox size={26} /></span><b>Chưa có lần đồng bộ nào</b></div>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Thời gian</th><th>Nguồn</th><th>Kiểu</th>
                    <th>Trạng thái</th><th className="num-col">Kết quả</th><th>Thời lượng</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l) => {
                    const st = STATUS[l.status] || { cls: "neutral", label: l.status, Ico: Clock };
                    const dur = l.finished_at
                      ? `${((new Date(l.finished_at) - new Date(l.started_at)) / 1000).toFixed(1)}s` : "—";
                    return (
                      <tr key={l.id} style={{ cursor: "default" }}>
                        <td style={{ whiteSpace: "nowrap" }}>{dtShort(l.started_at)}</td>
                        <td><span className="chip">{l.source}</span></td>
                        <td>{l.trigger_type === "schedule" ? "Tự động" : "Thủ công"}</td>
                        <td><span className={`badge ${st.cls}`}><st.Ico size={13} /> {st.label}</span></td>
                        <td className="num-col num">+{l.records_inserted} / {l.records_updated}</td>
                        <td className="num">{dur}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="koc-handle" style={{ marginTop: 12 }}>Cột "Kết quả": số bản ghi mới / số bản ghi cập nhật.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- area chart (pure SVG) */
function AreaChart({ values, times }) {
  const pts = (values || []).map((v) => (v == null ? null : Number(v)));
  const valid = pts.filter((v) => v != null);
  if (valid.length < 2) {
    return (
      <div className="empty" style={{ padding: "40px 20px" }}>
        <span className="empty-ico"><TrendingUp size={24} /></span>
        <b>Chưa đủ dữ liệu để vẽ biểu đồ</b>
        <span>Đồng bộ thêm một lần nữa để tạo lịch sử thay đổi.</span>
      </div>
    );
  }

  const w = 680, h = 200, padX = 12, padTop = 16, padBot = 24;
  const min = Math.min(...valid), max = Math.max(...valid);
  const span = max - min || 1;
  const n = pts.length;
  const xAt = (i) => padX + (i / (n - 1)) * (w - 2 * padX);
  const yAt = (v) => padTop + (1 - (v - min) / span) * (h - padTop - padBot);

  const coords = pts.map((v, i) => (v == null ? null : [xAt(i), yAt(v)])).filter(Boolean);
  const line = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${coords[coords.length - 1][0].toFixed(1)},${(h - padBot).toFixed(1)} L${coords[0][0].toFixed(1)},${(h - padBot).toFixed(1)} Z`;
  const last = coords[coords.length - 1];

  // 3 horizontal gridlines
  const grid = [0, 0.5, 1].map((t) => padTop + t * (h - padTop - padBot));

  return (
    <svg className="chart-svg" viewBox={`0 0 ${w} ${h}`} role="img"
      aria-label={`Biểu đồ lịch sử, từ ${fmt(min)} đến ${fmt(max)}`}>
      <defs>
        <linearGradient id="koc-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary-600)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--primary-600)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {grid.map((y, i) => (
        <line key={i} x1={padX} y1={y} x2={w - padX} y2={y}
          stroke="var(--border)" strokeWidth="1" strokeDasharray="3 4" />
      ))}
      <path d={area} fill="url(#koc-fill)" />
      <path d={line} fill="none" stroke="var(--primary-600)" strokeWidth="2.5"
        strokeLinejoin="round" strokeLinecap="round" />
      {coords.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i === coords.length - 1 ? 4 : 2.5}
          fill="var(--surface)" stroke="var(--primary-600)" strokeWidth="2" />
      ))}
      <text x={last[0]} y={Math.max(last[1] - 10, 12)} textAnchor="end"
        fontSize="12" fontFamily="var(--font-mono)" fontWeight="600" fill="var(--text)">
        {compact(valid[valid.length - 1])}
      </text>
    </svg>
  );
}
