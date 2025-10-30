// alarms-modal.js — abortable fetch + requestId + loader visual + BUSCADOR en tiempo real

const EP = (window.RT_ENDPOINTS || {});
const Q  = (sel) => document.querySelector(sel);

/* =========================
 * Estado / filtros actuales
 * ========================= */
function getStateSafe() {
  try { return (typeof window.getState === "function" ? window.getState() : {}) || {}; }
  catch { return {}; }
}
function getMirror() { return (document.body && document.body.dataset) || {}; }

function currentFilters() {
  const st = getStateSafe();
  const ds = getMirror();
  return {
    severity:        st.severityFilter        ?? ds.severityFilter        ?? "",
    device:          st.deviceFilter          ?? ds.deviceFilter          ?? "",
    action:          st.actionFilter          ?? ds.actionFilter          ?? "",
    hour:            st.hourFilter            ?? ds.hourFilter            ?? "",
    msg_severity:    st.msgSeverityFilter     ?? ds.msgSeverityFilter     ?? "",
    level:           st.levelFilter           ?? ds.levelFilter           ?? "",
    subtype:         st.subtypeFilter         ?? ds.subtypeFilter         ?? "",
    // log_description se mantiene por compat (aunque el gráfico fue retirado)
    log_description: st.logDescriptionFilter  ?? ds.logDescriptionFilter  ?? "",
  };
}

function buildURL(params) {
  const u = new URL(EP.alarms, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v == null) return;
    if (Array.isArray(v) && v.length) u.searchParams.set(k, v.join(","));
    else if (typeof v === "string" && v.trim() !== "") u.searchParams.set(k, v.trim());
  });
  u.searchParams.set("_ts", Date.now().toString()); // cache-bust
  return u.toString();
}

function fmtTime(iso) {
  if (!iso) return "—";
  try { const d = new Date(iso); return d.toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" }); }
  catch { return String(iso); }
}

/* =========================
 * Modal helpers
 * ========================= */
function showModal() { Q("#alarmsModal")?.classList.remove("hidden"); }
function hideModal() { Q("#alarmsModal")?.classList.add("hidden"); }

function renderCount(n) {
  const h = Q("#alarmsModalTitle");
  if (h) h.innerHTML = `Alarmas <span style="margin-left:.5rem;font-weight:600;opacity:.9">(${n})</span>`;
}

function ensureSpinnerStyles() {
  if (document.getElementById("ao-spinner-styles")) return;
  const css = `
  @keyframes ao-spin { to { transform: rotate(360deg); } }
  .ao-loading { display:flex; align-items:center; justify-content:center; gap:.6rem; padding:14px 8px; }
  .ao-spinner { width:22px; height:22px; border-radius:50%; border:3px solid rgba(255,255,255,.25); border-top-color:#fff; animation: ao-spin .8s linear infinite; }
  .ao-loading span { font-family: Inter, system-ui, Segoe UI, Arial, sans-serif; font-size: .95rem; opacity:.9; }
  @media (prefers-color-scheme: light){
    .ao-spinner { border:3px solid rgba(30,41,59,.25); border-top-color:#0f172a; }
    .ao-loading span { color:#0f172a; }
  }`;
  const tag = document.createElement("style");
  tag.id = "ao-spinner-styles";
  tag.textContent = css;
  document.head.appendChild(tag);
}

function renderLoading() {
  ensureSpinnerStyles();
  const tbody = Q("#alarmsTable tbody");
  if (!tbody) return;
  tbody.innerHTML = `
    <tr>
      <td colspan="7">
        <div class="ao-loading">
          <div class="ao-spinner" aria-hidden="true"></div>
          <span>Cargando datos…</span>
        </div>
      </td>
    </tr>
  `;
  renderCount("…");
}

function clearRows() {
  const tbody = Q("#alarmsTable tbody");
  if (tbody) tbody.innerHTML = "";
}

/* =========================
 * Cache + render con filtro
 * ========================= */
let _rowsCache = [];   // copia tal cual viene del backend
let _lastQuery = "";   // query actual (para mantener al refrescar)

function setRowsCache(rows) {
  _rowsCache = Array.isArray(rows) ? rows.slice() : [];
}

function passFilter(row, q) {
  if (!q) return true;
  const needle = q.toLowerCase();
  // concatenamos todos los campos renderizados
  const haystack = [
    fmtTime(row.eventtime),
    (row.msg_severity || row.severity || "").toString(),
    row.device || "",
    row.level || "",
    row.action || "",
    row.subtype || "",
    row.log_description || "",
  ].join(" | ").toLowerCase();
  return haystack.includes(needle);
}

function renderRowsFromCache(query) {
  _lastQuery = query || "";
  const tbody = Q("#alarmsTable tbody");
  if (!tbody) return;

  const filtered = _rowsCache.filter(r => passFilter(r, _lastQuery));
  tbody.innerHTML = "";

  filtered.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${fmtTime(r.eventtime)}</td>
      <td>${(r.msg_severity || r.severity || "").toUpperCase()}</td>
      <td>${r.device || "—"}</td>
      <td>${r.level || "—"}</td>
      <td>${r.action || "—"}</td>
      <td>${r.subtype || "—"}</td>
      <td>${r.log_description || "—"}</td>
    `.trim();
    tr.addEventListener("click", () => openLog(r.alarmid));
    tbody.appendChild(tr);
  });

  // actualizar el contador con la cantidad filtrada
  renderCount(filtered.length);
}

function wireSearch() {
  const input = Q("#alarmsSearch");
  if (!input) return;

  // limpiar valor al abrir si venimos de otro modal
  if (input.dataset.wired !== "1") {
    input.addEventListener("input", () => {
      const q = (input.value || "").trim();
      renderRowsFromCache(q);
    });
    input.dataset.wired = "1";
  }
  // reseteamos a la última query recordada (útil si reabrimos)
  input.value = _lastQuery || "";
}

/* =========================
 * LOG modal
 * ========================= */
async function openLog(alarmid) {
  try {
    const u = new URL(EP.log, window.location.origin);
    u.searchParams.set("alarmid", alarmid);
    u.searchParams.set("_ts", Date.now().toString());
    const r = await fetch(u, { headers: { "Accept": "application/json" } });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "No se pudo cargar");

    const metaEl = document.getElementById("logMeta");
    if (metaEl) {
      const m = j.meta || {};
      metaEl.innerHTML = `
        <div><strong>ID:</strong> ${m.alarmid ?? "—"}</div>
        <div><strong>Hora:</strong> ${m.eventtime ?? "—"}</div>
        <div><strong>Severidad:</strong> ${(m.msg_severity || m.severity || "").toString().toUpperCase()}</div>
        <div><strong>Dispositivo:</strong> ${m.device ?? "—"}</div>
        <div><strong>Level:</strong> ${m.level ?? "—"}</div>
        <div><strong>Action:</strong> ${m.action ?? "—"}</div>
        <div><strong>Subtype:</strong> ${m.subtype ?? "—"}</div>
      `;
    }
    const htmlEl = document.getElementById("logHtml");
    if (htmlEl) htmlEl.innerHTML = j.html || "<em>Sin detalles</em>";
    document.getElementById("logModal")?.classList.remove("hidden");
    document.querySelector("#logModal [data-close-log]")?.addEventListener("click", () => {
      document.getElementById("logModal")?.classList.add("hidden");
    });
    document.querySelector("#logModal .modal-backdrop")?.addEventListener("click", () => {
      document.getElementById("logModal")?.classList.add("hidden");
    });
  } catch (e) {
    alert("No se pudo abrir el log: " + e.message);
  }
}

/* =========================
 * Chart helpers
 * ========================= */
function getChartByCanvasId(id) {
  const cv = document.getElementById(id);
  return (cv && window.Chart && Chart.getChart) ? Chart.getChart(cv) : null;
}
function visibleLabelsNonZero(chart) {
  if (!chart) return [];
  const labels = chart.data?.labels || [];
  const data = chart.data?.datasets?.[0]?.data || [];
  const out = [];
  for (let i = 0; i < labels.length; i++) {
    const v = Number(data[i] || 0);
    if (v > 0) out.push(String(labels[i]));
  }
  return out;
}

/* =========================
 * AbortController + requestId
 * ========================= */
let currentController = null;
let lastReqId = 0;

async function fetchRowsAbortable(params) {
  if (currentController) { try { currentController.abort(); } catch {} }
  const controller = new AbortController();
  currentController = controller;
  const reqId = ++lastReqId;

  const url = buildURL(params);
  const r = await fetch(url, { headers: { "Accept": "application/json" }, signal: controller.signal });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  if (reqId !== lastReqId) return null; // respuesta obsoleta
  return j;
}

// al cerrar modal, abortar en curso
(function wireClose(){
  Q("[data-close-alarms]")?.addEventListener("click", () => {
    if (currentController) { try { currentController.abort(); } catch {} }
    hideModal();
  });
  Q("#alarmsModal .modal-backdrop")?.addEventListener("click", () => {
    if (currentController) { try { currentController.abort(); } catch {} }
    hideModal();
  });
})();

/* =========================
 * Abridores por gráfico
 * ========================= */
async function openFromSubtype() {
  const st = getStateSafe();
  const params = { ...currentFilters() };
  if (String(st.subtypeFilter || "").trim()) {
    params.subtype = st.subtypeFilter;
  } else {
    const labels = visibleLabelsNonZero(getChartByCanvasId("subtypeBar"));
    if (labels.length) params.subtypes = labels;
  }
  showModal(); clearRows(); renderLoading();
  wireSearch(); // preparar buscador
  try {
    const j = await fetchRowsAbortable(params);
    if (!j) return;
    setRowsCache(j.rows || []);
    renderRowsFromCache(""); // sin query inicial
  } catch { setRowsCache([]); renderRowsFromCache(""); }
}

async function openFromLevel() {
  const st = getStateSafe();
  const params = { ...currentFilters() };
  if (String(st.levelFilter || "").trim()) params.level = st.levelFilter;
  showModal(); clearRows(); renderLoading();
  wireSearch();
  try {
    const j = await fetchRowsAbortable(params);
    if (!j) return;
    setRowsCache(j.rows || []);
    renderRowsFromCache("");
  } catch { setRowsCache([]); renderRowsFromCache(""); }
}

async function openFromSeverity() {
  const st = getStateSafe();
  const params = { ...currentFilters() };
  if (String(st.severityFilter || "").trim()) params.severity = st.severityFilter;
  showModal(); clearRows(); renderLoading();
  wireSearch();
  try {
    const j = await fetchRowsAbortable(params);
    if (!j) return;
    setRowsCache(j.rows || []);
    renderRowsFromCache("");
  } catch { setRowsCache([]); renderRowsFromCache(""); }
}

async function openFromActions() {
  const st = getStateSafe();
  const params = { ...currentFilters() };
  if (String(st.actionFilter || "").trim()) params.action = st.actionFilter;
  showModal(); clearRows(); renderLoading();
  wireSearch();
  try {
    const j = await fetchRowsAbortable(params);
    if (!j) return;
    setRowsCache(j.rows || []);
    renderRowsFromCache("");
  } catch { setRowsCache([]); renderRowsFromCache(""); }
}

async function openFromMsgSeverity() {
  const st = getStateSafe();
  const params = { ...currentFilters() };
  if (String(st.msgSeverityFilter || "").trim()) params.msg_severity = st.msgSeverityFilter;
  showModal(); clearRows(); renderLoading();
  wireSearch();
  try {
    const j = await fetchRowsAbortable(params);
    if (!j) return;
    setRowsCache(j.rows || []);
    renderRowsFromCache("");
  } catch { setRowsCache([]); renderRowsFromCache(""); }
}

async function openFromHourly() {
  const st = getStateSafe();
  const params = { ...currentFilters() };
  if (String(st.hourFilter || "").trim()) {
    params.hour = st.hourFilter;
  } else {
    const chart = getChartByCanvasId("hourlyChart");
    const labels = chart?.data?.labels || [];
    const data = chart?.data?.datasets?.[0]?.data || [];
    const hours = [];
    for (let i = 0; i < labels.length; i++) {
      const v = Number(data[i] || 0);
      if (v > 0) hours.push(String(labels[i]).padStart(2, "0"));
    }
    if (hours.length) params.hours = hours;
  }
  showModal(); clearRows(); renderLoading();
  wireSearch();
  try {
    const j = await fetchRowsAbortable(params);
    if (!j) return;
    setRowsCache(j.rows || []);
    renderRowsFromCache("");
  } catch { setRowsCache([]); renderRowsFromCache(""); }
}

/* =========================
 * Wire buttons + API pública
 * ========================= */
(function wireButtons(){
  Q("#btn-open-subtype-alarms")?.addEventListener("click", openFromSubtype);
  Q("#btn-open-level-alarms")?.addEventListener("click", openFromLevel);
  Q("#btn-open-severity-alarms")?.addEventListener("click", openFromSeverity);
  Q("#btn-open-action-alarms")?.addEventListener("click", openFromActions);
  Q("#btn-open-msgsev-alarms")?.addEventListener("click", openFromMsgSeverity);
  Q("#btn-open-hourly-alarms")?.addEventListener("click", openFromHourly);
})();

window.openSubtypeAlarms     = openFromSubtype;
window.openLevelAlarms       = openFromLevel;
window.openSeverityAlarms    = openFromSeverity;
window.openActionAlarms      = openFromActions;
window.openMsgSeverityAlarms = openFromMsgSeverity;
window.openHourlyAlarms      = openFromHourly;
