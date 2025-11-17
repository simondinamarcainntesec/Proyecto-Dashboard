/* eslint-disable */
(function () {
  // =========================================
  // SOAR – Modal de Incidentes (listado + detalle)
  // · Botón cerrar único (esquina superior derecha)
  // · Barra de búsqueda (alineada a la izquierda, bajo el título)
  // · Filtro local en vivo sobre la lista cargada
  // · Loteo de alarm_ids para evitar 414 (URL demasiado larga)
  // =========================================

  const LIST_MODAL_ID   = "soarIncidentsModal";
  const DETAIL_MODAL_ID = "soarIncidentDetailModal";

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const TXT = (el, v) => { if (el) el.textContent = (v ?? "—"); };
  const lc  = (s) => (s ?? "").toString().toLowerCase();
  const val = (v, d = "—") => { const t = (v ?? "").toString().trim(); return t ? t : d; };

  const listModal   = $(`#${LIST_MODAL_ID}`);
  const detailModal = $(`#${DETAIL_MODAL_ID}`);

  if (!listModal) { console.warn(`[SOAR_Incidents] No existe #${LIST_MODAL_ID} en el DOM.`); return; }

  // API URLs
  const apiListURL =
    listModal.getAttribute("data-api-url") || "/soar/incidentes/api/by-alarm-ids/";
  const explicitDetailURL = detailModal?.getAttribute("data-detail-api-url");
  const apiDetailURL =
    explicitDetailURL || apiListURL.replace(/by-?alarm-ids\/?$/i, "detail-by-alarm-id/");

  // Tabla del listado (usa la que tengas en el HTML)
  const tbody =
    $("#si-tbody", listModal) ||
    $("#inc-tbody", listModal) ||
    $("#tbl-incidentes-modal tbody", listModal);

  // Detalle
  const dTitle = $("#alert-detail-title", detailModal) || $("#inc-title", detailModal);
  const dMeta  = $("#detail-meta-list", detailModal) || $("#inc-meta-list", detailModal) || $("#si-meta", detailModal);
  const dRisk  = $("#detail-risk", detailModal) || $("#inc-riesgo", detailModal);
  const dClas  = $("#detail-clasif", detailModal) || $("#inc-clasif", detailModal);
  const dAct   = $("#detail-actions", detailModal) || $("#inc-acciones", detailModal);
  const dApp   = $("#detail-app", detailModal) || $("#inc-app", detailModal);

  let ITEMS = [];
  let ROWS  = [];

  // ---------- utils ----------
  function splitDateTime(dt) {
    if (!dt) return { date: "", time: "" };
    const s = String(dt).trim();
    const m = s.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})/);
    if (m) return { date: m[1], time: m[2] };
    const p = s.split(/\s+/);
    return (p.length >= 2) ? { date: p[0], time: p[1] } : { date: s, time: "" };
  }

  function mapCommon(raw) {
    let id_alarm = raw.alarmd_id ?? raw.alarm_id ?? raw.id_alarm ?? raw.id ?? raw.alert_id ?? raw.incident_id ?? "—";
    let device   = raw.dispositivo ?? raw.device ?? raw.device_name ?? raw.appliance_name ?? raw.host ?? "—";
    let threat_type =
      raw.tipo_de_amenaza ?? raw.threat_type ?? raw.alert_type ?? raw.alert_name ??
      raw.descripcion_incidente ?? raw.description ?? "—";
    let severity = raw.nivel_de_severidad ?? raw.severity ?? raw.severity_level ?? raw.criticidad ?? "—";

    let date = raw.date || "";
    let time = raw.time || "";
    if (!date && !time) {
      const dt = raw.datetime || raw.timestamp || raw.created_at || raw.fecha_hora || "";
      const sp = splitDateTime(dt);
      date = sp.date; time = sp.time;
    }
    const datetime = [date, time].filter(Boolean).join(" ");

    return {
      _raw: raw,
      id_alarm: val(id_alarm),
      device: val(device),
      threat_type: val(threat_type),
      severity: val(severity),
      date: date || "—",
      time: time || "—",
      datetime: val(datetime),
    };
  }

  function mapDetail(raw) {
    const risk = raw.resumen_humano ?? raw.descripcion_incidente ?? raw.riego_detectado ?? raw.riesgo_detectado ?? "—";
    const classification = raw.analisis_criticidad ?? raw.clasificacion ?? raw.classification ?? "—";
    const actions = raw.medidas_correctivas ?? raw.recommended_actions ?? raw.actions ?? "—";
    const application = raw.application ?? raw.Application ?? raw.app ?? "—";
    return { risk: val(risk), classification: val(classification), actions: val(actions), application: val(application) };
  }

  function mapListItem(raw) { return { ...mapCommon(raw), ...mapDetail(raw) }; }

  // ---------- modal helpers ----------
  function open(m){ if(!m) return; m.classList.remove("hidden"); document.body.classList.add("modal-open"); }
  function close(m){ if(!m) return; m.classList.add("hidden"); document.body.classList.remove("modal-open"); }
  function wireClose(m){
    if(!m) return;
    $$(".modal-backdrop", m).forEach(n => n.addEventListener("click", ()=>close(m)));
    $$("[data-close]", m).forEach(n => n.addEventListener("click", ()=>close(m)));
  }
  wireClose(listModal); wireClose(detailModal);

  // ----- cerrar único: crea/ubica la X y elimina duplicados -----
  function ensureCloseX() {
    const header = $(`#${LIST_MODAL_ID} .modal-header`) || $(`#${LIST_MODAL_ID} .modal-card`);
    if (!header) return;

    // ¿ya hay uno en header?
    let btn = header.querySelector(".modal-close-x");

    if (!btn) {
      // ¿reusar cualquiera en el modal?
      btn = $(`#${LIST_MODAL_ID} .modal-close`) || $(`#${LIST_MODAL_ID} [data-close]`);
      if (!btn) {
        btn = document.createElement("button");
        btn.type = "button";
        btn.className = "modal-close";
        btn.setAttribute("data-close","1");
        btn.textContent = "✕";
      }
      header.appendChild(btn);
      btn.classList.add("modal-close-x");
      btn.setAttribute("aria-label","Cerrar");
      btn.addEventListener("click", () => close(listModal));
    }

    // eliminar cualquier otro botón de cierre en TODO el modal (menos el del header)
    $(`#${LIST_MODAL_ID} .modal-card`)?.querySelectorAll(".modal-close, [data-close]").forEach(el=>{
      if(el !== btn) el.remove();
    });
  }

  // ----- barra buscador bajo el título -----
  function ensureSearchBar() {
    const card = $(`#${LIST_MODAL_ID} .modal-card`);
    if (!card) return;

    let toolbar = $("#si-toolbar", card);
    if (!toolbar) {
      toolbar = document.createElement("div");
      toolbar.id = "si-toolbar";
      toolbar.className = "si-toolbar";
      // insertarlo inmediatamente después del header, si existe
      const header = $(`#${LIST_MODAL_ID} .modal-header`);
      (header && header.nextSibling)
        ? card.insertBefore(toolbar, header.nextSibling)
        : card.insertBefore(toolbar, card.firstChild);
    } else {
      toolbar.innerHTML = "";
    }

    const searchWrap = document.createElement("div");
    searchWrap.className = "si-search";

    const input = document.createElement("input");
    input.type = "search";
    input.id   = "si-q";
    input.placeholder = "Buscar (cualquier campo)…";
    input.className = "si-search-input";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.id   = "si-btn-search";
    btn.className = "si-search-btn";
    btn.textContent = "Buscar";

    searchWrap.append(input, btn);
    toolbar.appendChild(searchWrap);

    const applyLocal = () => filterRows(input.value);
    input.addEventListener("input", applyLocal);
    btn.addEventListener("click", applyLocal);
  }

  // ----- render listado -----
  function renderList(rows) {
    ITEMS = rows.map(mapListItem);
    ROWS = [];
    if (!tbody) return;

    tbody.innerHTML = "";
    ITEMS.forEach((it, i) => {
      const tr = document.createElement("tr");
      tr.className = "clickable-row";
      tr.dataset.index = String(i);

      tr.dataset.haystack = [
        it.id_alarm, it.device, it.threat_type, it.severity,
        it.date, it.time, it.datetime, it.risk, it.classification, it.actions, it.application
      ].map(x => (x ?? "").toString()).join(" | ").toLowerCase();

      const tdId  = document.createElement("td"); tdId.className = "mono nowrap"; TXT(tdId, it.id_alarm);
      const tdDev = document.createElement("td"); tdDev.className = "w-240";       TXT(tdDev, it.device);
      const tdTyp = document.createElement("td"); tdTyp.className = "w-320";       TXT(tdTyp, it.threat_type);

      const tdSev = document.createElement("td"); tdSev.className = "nowrap";
      const s = lc(it.severity);
      const sevCls =
        /critical|crítico|critico/.test(s) ? "sev-critical" :
        /high|alto/.test(s)               ? "sev-high"     :
        /medium|medio/.test(s)            ? "sev-medium"   :
        /low|bajo/.test(s)                ? "sev-low"      :
        /info/.test(s)                    ? "sev-info"     : "sev-na";
      tdSev.innerHTML = `<span class="pill ${sevCls}">${val(it.severity)}</span>`;

      const tdDate = document.createElement("td"); tdDate.className = "mono nowrap"; TXT(tdDate, it.date || "—");
      const tdTime = document.createElement("td"); tdTime.className = "mono nowrap"; TXT(tdTime, it.time || "—");

      tr.append(tdId, tdDev, tdTyp, tdSev, tdDate, tdTime);
      tr.addEventListener("click", () => openDetail(i));

      tbody.appendChild(tr);
      ROWS.push(tr);
    });

    open(listModal);
    ensureCloseX();
    ensureSearchBar();

    const q = $("#si-q");
    if (q && q.value) filterRows(q.value);
  }

  // ----- filtro local -----
  function filterRows(q) {
    const needle = lc((q || "").trim());
    ROWS.forEach(tr => {
      const hay = tr.dataset.haystack || "";
      tr.style.display = (!needle || hay.includes(needle)) ? "" : "none";
    });
  }

  // ----- detalle -----
  function paintDetail(it) {
    if (!detailModal) return;

    // 🚨 título como en la referencia: icono + severidad en negrita + dispositivo en “muted”
    if (dTitle) {
      const sev = val(it.severity);
      const dev = val(it.device);
      dTitle.innerHTML = `🚨 <strong>${sev}</strong> — <span class="muted">${dev}</span>`;
    }

    if (dMeta) {
      dMeta.innerHTML = "";
      [["ID", it.id_alarm], ["Dispositivo", it.device], ["Tipo", it.threat_type], ["Fecha/Hora", it.datetime]]
      .forEach(([k,v]) => {
        const li = document.createElement("li");
        li.innerHTML = `<strong>${k}:</strong> ${val(v)}`;
        dMeta.appendChild(li);
      });
    }
    TXT(dRisk, it.risk);
    TXT(dClas, it.classification);
    TXT(dAct, it.actions);

    if (dApp) {
      const wrap = dApp.parentElement;
      if (it.application && it.application !== "—") { dApp.textContent = it.application; if (wrap) wrap.style.display = ""; }
      else { dApp.textContent = "—"; if (wrap) wrap.style.display = "none"; }
    }
    open(detailModal);
  }

  async function fetchDetailById(alarmId) {
    const id = String(alarmId || "").trim();
    if (!id) return {};
    const url = `${apiDetailURL}${apiDetailURL.endsWith("/") ? "" : "/"}?alarm_id=${encodeURIComponent(id)}`;
    const r = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    const obj = Array.isArray(j) ? (j[0] || {}) : (j?.item || j || {});
    return { ...mapCommon(obj), ...mapDetail(obj) };
  }

  async function openDetail(index) {
    const base = ITEMS[index];
    if (!base) return;

    const hasAll =
      base.risk !== "—" || base.classification !== "—" || base.actions !== "—" ||
      (base.application && base.application !== "—");

    if (hasAll) { paintDetail(base); return; }

    try {
      const det = await fetchDetailById(base.id_alarm);
      const merged = { ...base, ...det };
      ITEMS[index] = merged;
      paintDetail(merged);
    } catch {
      paintDetail(base);
    }
  }

  // ---------- helpers de loteo ----------
  function chunk(array, size) {
    const out = [];
    for (let i = 0; i < array.length; i += size) out.push(array.slice(i, i + size));
    return out;
  }

  // ----- fetch listado por ids (con loteo y merge) -----
  async function fetchList(ids) {
    // 1) Sanitiza y quita duplicados
    const uniq = Array.from(new Set((ids || []).map(String).filter(Boolean)));
    if (!uniq.length) return [];

    // 2) Parámetros de loteo
    let CHUNK_SIZE = 100;       // Ajustable según tamaño de IDs
    const MAX_URL   = 1900;     // Umbral conservador para querystring

    // 3) Particiona en chunks iniciales
    let chunks = chunk(uniq, CHUNK_SIZE);
    const all = [];

    // 4) Recolector de cada chunk
    const fetchChunk = async (arr) => {
      const qs = new URLSearchParams({ alarm_ids: arr.join(",") }).toString();
      const urlBase = apiListURL.endsWith("/") ? apiListURL : (apiListURL + "/");
      let url = `${urlBase}${apiListURL.includes("?") ? "&" : "?"}${qs}`;

      // Si la URL sigue siendo grande, parte el chunk a la mitad recursivamente
      if (url.length > MAX_URL && arr.length > 1) {
        const mid = Math.ceil(arr.length / 2);
        const left = await fetchChunk(arr.slice(0, mid));
        const right = await fetchChunk(arr.slice(mid));
        return [...left, ...right];
      }

      const r = await fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      // Soporta array plano o {items: [...]}/{results: [...]}
      const data = Array.isArray(j) ? j : (j.items || j.results || []);
      return data;
    };

    // 5) Ejecuta en serie para no saturar (podrías paralelizar si tu backend lo tolera)
    for (const c of chunks) {
      const part = await fetchChunk(c);
      all.push(...part);
    }

    // 6) Dedup de filas por alguna key estable (id/incidente/alarm_id)
    const seen = new Map();
    for (const it of all) {
      const key =
        it.id ?? it.incident_id ?? it.alarm_id ?? it.alarmd_id ??
        it.id_alarm ?? JSON.stringify(it);
      if (!seen.has(key)) seen.set(key, it);
    }
    return Array.from(seen.values());
  }

  // ----- API pública -----
  window.SOAR_Incidents = {
    async showForAlarmIds(alarmIds = []) {
      try {
        if (!alarmIds.length) { alert("No hay alarmas para mostrar con el filtro actual."); return; }
        const rows = await fetchList(alarmIds);
        if (!rows.length) { alert("No se encontraron incidentes para esos IDs."); return; }
        renderList(rows);
      } catch (err) {
        console.error("[SOAR_Incidents] Error:", err);
        alert("No se pudieron cargar los incidentes. Intenta nuevamente.");
      }
    },
  };

  window.dispatchEvent(new Event("soar-incidents-ready"));
})();
