/* eslint-disable */
(function () {
  // =========================================
  // SOAR – Modal de Incidentes (listado + detalle)
  // Integrado con asignación de tickets (soar_assign_ticket.js)
  // Ticket inline en HEADER del detalle (como foto 2)
  // Auto-hydrate ticket para dashboard_soar (si el objeto base no trae assigned)
  // =========================================

  const LIST_MODAL_ID = "soarIncidentsModal";
  const DETAIL_MODAL_ID = "soarIncidentDetailModal";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const TXT = (el, v) => { if (el) el.textContent = (v ?? "—"); };
  const lc = (s) => (s ?? "").toString().toLowerCase();
  const val = (v, d = "—") => { const t = (v ?? "").toString().trim(); return t ? t : d; };

  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // pills de asignación (NO mete contenido usuario en HTML)
  function renderAssignedCell(isYes) {
    if (isYes) {
      return `
        <span class="assign-pill is-yes">
          <svg class="assign-ico" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle>
            <path d="M8 12l2.5 2.5L16 9" fill="none" stroke="currentColor" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
          Sí
        </span>
      `;
    }
    return `
      <span class="assign-pill is-no">
        <svg class="assign-ico" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle>
        </svg>
        No
      </span>
    `;
  }

  const listModal = $(`#${LIST_MODAL_ID}`);
  const detailModal = $(`#${DETAIL_MODAL_ID}`);

  if (!listModal) {
    console.warn(`[SOAR_Incidents] No existe #${LIST_MODAL_ID} en el DOM.`);
    return;
  }

  // API URLs
  const apiListURL =
    listModal.getAttribute("data-api-url") || "/soar/incidentes/api/by-alarm-ids/";
  const explicitDetailURL = detailModal?.getAttribute("data-detail-api-url");
  const apiDetailURL =
    explicitDetailURL || apiListURL.replace(/by-?alarm-ids\/?$/i, "detail-by-alarm-id/");

  // tbody del listado (tu HTML usa #si-tbody)
  const tbody =
    $("#si-tbody", listModal) ||
    $("#inc-tbody", listModal) ||
    $("#tbl-incidentes-modal tbody", listModal) ||
    $("#tbl-incidentes tbody", listModal);

  // Detalle
  const dMeta = $("#detail-meta-list", detailModal) || $("#inc-meta-list", detailModal) || $("#si-meta", detailModal);
  const dRisk = $("#detail-risk", detailModal) || $("#inc-riesgo", detailModal);
  const dClas = $("#detail-clasif", detailModal) || $("#inc-clasif", detailModal);
  const dAct = $("#detail-actions", detailModal) || $("#inc-acciones", detailModal);
  const dApp = $("#detail-app", detailModal) || $("#inc-app", detailModal);

  // HEADER NUEVO (como foto 2)
  const dSev = $("#inc-sev", detailModal);
  const dDev = $("#inc-dev", detailModal);
  const dTicketStatus = $("#inc-ticket-status", detailModal);
  const dTicketUser = $("#inc-ticket-user", detailModal);
  const dTicketAssigneeWrap = $("#inc-ticket-assignee-wrap", detailModal);

  let ITEMS = [];
  let ROWS = [];

  // ---------- modal helpers (FIX multi-modal) ----------
  function anyModalOpen() {
    return Array.from(document.querySelectorAll(".modal"))
      .some(m => !m.classList.contains("hidden"));
  }

  function open(m) {
    if (!m) return;
    m.classList.remove("hidden");
    document.body.classList.add("modal-open");
  }

  function close(m) {
    if (!m) return;
    m.classList.add("hidden");
    if (!anyModalOpen()) {
      document.body.classList.remove("modal-open");
    }
  }

  function wireClose(m) {
    if (!m) return;
    $$(".modal-backdrop", m).forEach(n => n.addEventListener("click", () => close(m)));
    $$("[data-close]", m).forEach(n => n.addEventListener("click", () => close(m)));
  }

  wireClose(listModal);
  wireClose(detailModal);

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
    let device = raw.dispositivo ?? raw.device ?? raw.device_name ?? raw.appliance_name ?? raw.host ?? "—";
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

    // asignación
    const hasTicketRaw =
      raw.has_ticket ?? raw.hasTicket ?? raw.assigned ?? raw.ticket_exists ?? raw.ticketExists ?? 0;

    const assigned =
      hasTicketRaw === true || hasTicketRaw === 1 || String(hasTicketRaw) === "1" ||
      String(raw.assigned || "").toLowerCase() === "true";

    const assigned_name =
      raw.ticket_assigned_to_name ?? raw.assigned_to_name ?? raw.assigned_name ?? raw.assignedName ??
      raw.ticket_name ?? raw.ticketName ?? "";

    return {
      _raw: raw,

      id_alarm: val(id_alarm),
      device: val(device),
      threat_type: val(threat_type),
      severity: val(severity),
      date: date || "—",
      time: time || "—",
      datetime: val(datetime),

      assigned: !!assigned,
      assigned_name: (assigned_name || "").toString().trim(),
    };
  }

  function mapDetail(raw) {
    const risk =
      raw.resumen_humano ?? raw.descripcion_incidente ?? raw.riego_detectado ?? raw.riesgo_detectado ?? "—";
    const classification =
      raw.analisis_criticidad ?? raw.clasificacion ?? raw.classification ?? "—";
    const actions =
      raw.medidas_correctivas ?? raw.recommended_actions ?? raw.actions ?? "—";
    const application =
      raw.application ?? raw.Application ?? raw.app ?? "—";

    const descripcion_incidente =
      raw.descripcion_incidente ?? raw.description ?? "";
    const analisis_criticidad =
      raw.analisis_criticidad ?? raw.clasificacion ?? raw.classification ?? "";
    const medidas_correctivas =
      raw.medidas_correctivas ?? raw.recommended_actions ?? raw.actions ?? "";
    const resumen_humano =
      raw.resumen_humano ?? "";
    const riesgo_detectado =
      raw.riego_detectado ?? raw.riesgo_detectado ?? "";

    return {
      risk: val(risk),
      classification: val(classification),
      actions: val(actions),
      application: val(application),

      descripcion_incidente: String(descripcion_incidente || ""),
      analisis_criticidad: String(analisis_criticidad || ""),
      medidas_correctivas: String(medidas_correctivas || ""),
      resumen_humano: String(resumen_humano || ""),
      riesgo_detectado: String(riesgo_detectado || ""),
    };
  }

  function mapListItem(raw) {
    const common = mapCommon(raw);
    const detail = mapDetail(raw);
    return { ...common, ...detail };
  }

  // ---------- Ticket header helpers ----------
  function setTicketHeader(assignedBool, assignedName) {
    const assigned = !!assignedBool;
    const nm = (assignedName || "").toString().trim();

    if (dTicketStatus) dTicketStatus.innerHTML = renderAssignedCell(assigned);

    if (dTicketAssigneeWrap) {
      if (assigned && nm) {
        dTicketAssigneeWrap.classList.remove("hidden");
        if (dTicketUser) dTicketUser.textContent = nm;
      } else {
        dTicketAssigneeWrap.classList.add("hidden");
        if (dTicketUser) dTicketUser.textContent = "—";
      }
    } else {
      // fallback si no existe wrap, igual setea nombre
      if (dTicketUser) dTicketUser.textContent = (assigned && nm) ? nm : "—";
    }
  }

  // Exponer para que otros scripts (dashboardsoar.js / soar_assign_ticket.js) lo puedan usar
  window.SOAR_setTicketHeader = setTicketHeader;

  function extractAlarmIdFromMeta() {
    if (!dMeta) return "";
    const items = Array.from(dMeta.querySelectorAll("li"));
    for (const li of items) {
      const strong = li.querySelector("strong");
      const key = (strong?.textContent || "").trim().toLowerCase();
      if (key.startsWith("id")) {
        // li.textContent: "ID: 20459_...."
        const txt = (li.textContent || "").trim();
        const parts = txt.split(":");
        return (parts.length >= 2 ? parts.slice(1).join(":") : txt).trim();
      }
    }
    return "";
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

  // Auto-hydrate para dashboard_soar:
  // cuando se abre el modal de detalle, si no tenemos ticketHydratedFor, buscamos el alarmId y consultamos detalle.
  async function hydrateTicketOnOpenIfNeeded() {
    if (!detailModal || detailModal.classList.contains("hidden")) return;

    const alarmId = (detailModal.dataset.alarmId || "").trim() || extractAlarmIdFromMeta();
    if (!alarmId) return;

    if (detailModal.dataset.ticketHydratedFor === alarmId) return;

    try {
      const det = await fetchDetailById(alarmId);
      detailModal.dataset.alarmId = alarmId;
      detailModal.dataset.ticketHydratedFor = alarmId;
      setTicketHeader(!!det.assigned, det.assigned_name || "");
    } catch (e) {
      // si falla, al menos dejamos No
      detailModal.dataset.ticketHydratedFor = alarmId;
      setTicketHeader(false, "");
    }
  }

  if (detailModal) {
    const obs = new MutationObserver(() => {
      if (!detailModal.classList.contains("hidden")) {
        // next tick para dar tiempo a que el otro JS pinte el meta
        setTimeout(hydrateTicketOnOpenIfNeeded, 0);
      }
    });
    obs.observe(detailModal, { attributes: true, attributeFilter: ["class"] });
  }

  // Loader dentro del tbody (modal listado)
  function renderListLoading() {
    return `
      <tr class="loading-row">
        <td colspan="7">
          <div class="ao-loading">
            <div class="ao-spinner" aria-hidden="true"></div>
            <span>Cargando datos...</span>
          </div>
        </td>
      </tr>
    `;
  }

  function setListLoading(isOn) {
    if (!tbody) return;
    if (isOn) {
      tbody.innerHTML = renderListLoading();

      const empty = $("#si-empty", listModal);
      if (empty) empty.style.display = "none";

      open(listModal);
      ensureSearchBar();
      return;
    }
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
    input.id = "si-q";
    input.placeholder = "Buscar (cualquier campo)…";
    input.className = "si-search-input";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "si-btn-search";
    btn.className = "si-search-btn";
    btn.textContent = "Buscar";

    searchWrap.append(input, btn);
    toolbar.appendChild(searchWrap);

    const applyLocal = () => filterRows(input.value);
    input.addEventListener("input", applyLocal);
    btn.addEventListener("click", applyLocal);
  }

  // ----- filtro local -----
  function filterRows(q) {
    const needle = lc((q || "").trim());
    ROWS.forEach(tr => {
      const hay = tr.dataset.haystack || "";
      tr.style.display = (!needle || hay.includes(needle)) ? "" : "none";
    });
  }

  // ----- render listado -----
  function renderList(rows) {
    ITEMS = (rows || []).map(mapListItem);
    ROWS = [];

    if (!tbody) return;
    tbody.innerHTML = "";

    ITEMS.forEach((it, i) => {
      const tr = document.createElement("tr");
      tr.className = "soar-row";
      tr.dataset.index = String(i);

      // datasets para soar_assign_ticket.js
      tr.dataset.id = String(it.id_alarm || "");
      tr.dataset.dispositivo = String(it.device || "");
      tr.dataset.tipo = String(it.threat_type || "");
      tr.dataset.sev = String(it.severity || "");
      tr.dataset.date = String(it.date || "");
      tr.dataset.time = String(it.time || "");

      tr.dataset.descripcion = String(it.descripcion_incidente || "");
      tr.dataset.analisis = String(it.analisis_criticidad || "");
      tr.dataset.acciones = String(it.medidas_correctivas || "");
      tr.dataset.resumen = String(it.resumen_humano || "");
      tr.dataset.riesgo = String(it.riesgo_detectado || "");
      tr.dataset.app = String(it.application || "");

      tr.dataset.assigned = it.assigned ? "1" : "0";
      tr.dataset.assignedName = it.assigned_name || "";
      tr.dataset.assigned_name = it.assigned_name || "";

      tr.dataset.haystack = [
        it.id_alarm, it.device, it.threat_type, it.severity,
        it.date, it.time, it.datetime, it.risk, it.classification, it.actions, it.application,
        it.assigned ? "asignado" : "no asignado",
        it.assigned_name
      ].map(x => (x ?? "").toString()).join(" | ").toLowerCase();

      // celdas
      const tdId = document.createElement("td");
      tdId.className = "mono nowrap";
      TXT(tdId, it.id_alarm);

      const tdAsg = document.createElement("td");
      tdAsg.className = "nowrap";
      tdAsg.setAttribute("data-assigned-cell", "");
      tdAsg.innerHTML = renderAssignedCell(!!it.assigned);

      const tdDev = document.createElement("td");
      tdDev.className = "w-240";
      TXT(tdDev, it.device);

      const tdTyp = document.createElement("td");
      tdTyp.className = "w-320";
      TXT(tdTyp, it.threat_type);

      const tdSev = document.createElement("td");
      tdSev.className = "nowrap";
      const s = lc(it.severity);
      const sevCls =
        /critical|crítico|critico/.test(s) ? "sev-critical" :
        /high|alto/.test(s) ? "sev-high" :
        /medium|medio/.test(s) ? "sev-medium" :
        /low|bajo/.test(s) ? "sev-low" :
        /info/.test(s) ? "sev-info" : "sev-na";
      tdSev.innerHTML = `<span class="pill ${sevCls}">${escapeHtml(val(it.severity))}</span>`;

      const tdDate = document.createElement("td");
      tdDate.className = "mono nowrap";
      TXT(tdDate, it.date || "—");

      const tdTime = document.createElement("td");
      tdTime.className = "mono nowrap";
      TXT(tdTime, it.time || "—");

      tr.append(tdId, tdAsg, tdDev, tdTyp, tdSev, tdDate, tdTime);

      tr.addEventListener("click", () => openDetail(i));

      tbody.appendChild(tr);
      ROWS.push(tr);
    });

    open(listModal);
    ensureSearchBar();

    // Forzar hydrate del otro JS si está
    try { window.SOAR_assign_refreshAssigned?.(); } catch {}
    try { window.dispatchEvent(new Event("soar-incidents-rendered")); } catch {}

    const q = $("#si-q");
    if (q && q.value) filterRows(q.value);
  }

  // ----- detalle -----
  function paintDetail(it) {
    if (!detailModal) return;

    // Guardar alarmId en el modal (sirve para auto-update)
    detailModal.dataset.alarmId = String(it.id_alarm || "").trim();
    // resetea el flag para que si abrimos otra alarma, vuelva a hidratar
    if (detailModal.dataset.ticketHydratedFor !== detailModal.dataset.alarmId) {
      detailModal.dataset.ticketHydratedFor = "";
    }

    // HEADER (sin pisar innerHTML)
    TXT(dSev, val(it.severity));
    TXT(dDev, val(it.device));

    // ticket inline header
    setTicketHeader(!!it.assigned, it.assigned_name || "");

    if (dMeta) {
      dMeta.innerHTML = "";
      [
        ["ID", it.id_alarm],
        ["Dispositivo", it.device],
        ["Tipo", it.threat_type],
        ["Fecha/Hora", it.datetime]
      ].forEach(([k, v]) => {
        const li = document.createElement("li");
        li.innerHTML = `<strong>${escapeHtml(k)}:</strong> ${escapeHtml(val(v))}`;
        dMeta.appendChild(li);
      });
    }

    TXT(dRisk, it.risk);
    TXT(dClas, it.classification);
    TXT(dAct, it.actions);

    if (dApp) {
      const wrap = dApp.parentElement;
      if (it.application && it.application !== "—") {
        dApp.textContent = it.application;
        if (wrap) wrap.style.display = "";
      } else {
        dApp.textContent = "—";
        if (wrap) wrap.style.display = "none";
      }
    }

    open(detailModal);

    // Por si el dashboard abrió el modal con info incompleta:
    // intenta hidratar ticket desde API cuando ya esté visible
    setTimeout(hydrateTicketOnOpenIfNeeded, 0);
  }

  async function openDetail(index) {
    const base = ITEMS[index];
    if (!base) return;

    const hasAll =
      base.risk !== "—" ||
      base.classification !== "—" ||
      base.actions !== "—" ||
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
    const uniq = Array.from(new Set((ids || []).map(String).filter(Boolean)));
    if (!uniq.length) return [];

    let CHUNK_SIZE = 100;
    const MAX_URL = 1900;

    let chunks = chunk(uniq, CHUNK_SIZE);
    const all = [];

    const fetchChunk = async (arr) => {
      const qs = new URLSearchParams({ alarm_ids: arr.join(",") }).toString();
      const urlBase = apiListURL.endsWith("/") ? apiListURL : (apiListURL + "/");
      let url = `${urlBase}${apiListURL.includes("?") ? "&" : "?"}${qs}`;

      if (url.length > MAX_URL && arr.length > 1) {
        const mid = Math.ceil(arr.length / 2);
        const left = await fetchChunk(arr.slice(0, mid));
        const right = await fetchChunk(arr.slice(mid));
        return [...left, ...right];
      }

      const r = await fetch(url, {
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin"
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);

      const j = await r.json();
      const data = Array.isArray(j) ? j : (j.items || j.results || []);
      return data;
    };

    for (const c of chunks) {
      const part = await fetchChunk(c);
      all.push(...part);
    }

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
      if (!alarmIds.length) {
        alert("No hay alarmas para mostrar con el filtro actual.");
        return;
      }

      setListLoading(true);

      try {
        const rows = await fetchList(alarmIds);
        if (!rows.length) {
          if (tbody) tbody.innerHTML = "";
          const empty = $("#si-empty", listModal);
          if (empty) empty.style.display = "";
          return;
        }
        renderList(rows);
      } catch (err) {
        console.error("[SOAR_Incidents] Error:", err);
        alert("No se pudieron cargar los incidentes. Intenta nuevamente.");
      }
    },
  };

  window.dispatchEvent(new Event("soar-incidents-ready"));
})();
