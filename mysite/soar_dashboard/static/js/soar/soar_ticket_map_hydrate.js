/* eslint-disable */
// Hydrata dataset.assigned desde el JSON #soarTicketMap
(function () {
  const VER = "2026-01-06 ticket_map_hydrate v1";

  if (window.__SOAR_TICKET_MAP_HYDRATE_READY__) return;
  window.__SOAR_TICKET_MAP_HYDRATE_READY__ = true;

  const Q = (s, r = document) => r.querySelector(s);

  function readTicketMap() {
    const el = Q("#soarTicketMap");
    if (!el) return {};
    try {
      const obj = JSON.parse(el.textContent || "{}");
      return obj && typeof obj === "object" ? obj : {};
    } catch {
      return {};
    }
  }

  function isTruthyAssigned(v) {
    const s = String(v ?? "").trim().toLowerCase();
    return s === "1" || s === "true" || s === "yes";
  }

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

  function hydrateRow(tr, map) {
    if (!tr) return;

    const id = String(tr.dataset.id || tr.dataset.alarmId || "").trim();
    if (!id) return;

    const info = map[id];
    if (!info) return;

    const assigned = !!info.assigned;
    const name = String(info.assigned_name || info.assignedName || "").trim();

    tr.dataset.assigned = assigned ? "1" : "0";
    if (name) {
      tr.dataset.assignedName = name;
      tr.dataset.assigned_name = name;
    }

    const cell = tr.querySelector("[data-assigned-cell]");
    if (cell) {
      cell.innerHTML = renderAssignedCell(assigned);
    }
  }

  function hydrateAll() {
    const map = readTicketMap();

    // Tabla del modal de incidentes relacionados (dashboard_soar)
    const table = Q("#tbl-incidentes");
    if (table) {
      table.querySelectorAll("tr.soar-row").forEach((tr) => hydrateRow(tr, map));
    }

    // Si el detalle está abierto, refresca su estado también (si existe)
    const detailStatus = Q("#inc-ticket-status");
    const detailUser = Q("#inc-ticket-user");
    const detailModal = Q("#soarIncidentDetailModal");

    if (detailModal && !detailModal.classList.contains("hidden")) {
      // intenta tomar el alarm_id desde el meta list (primera línea suele ser ID)
      // si no, no rompe nada.
      try {
        const meta = Q("#inc-meta-list");
        const first = meta?.querySelector("li");
        const txt = (first?.textContent || "").trim();
        // espera "ID: 20459_..."
        const m = txt.match(/ID:\s*([A-Za-z0-9_:-]+)/i);
        const alarmId = m ? m[1] : "";
        const info = alarmId ? map[alarmId] : null;

        if (info && detailStatus) detailStatus.innerHTML = renderAssignedCell(!!info.assigned);
        if (info && detailUser) detailUser.textContent = (info.assigned_name || "—");
      } catch {}
    }

    // Si existe el refresher del otro JS, úsalo (no obligatorio)
    try { window.SOAR_assign_refreshAssigned?.(); } catch {}
  }

  // 1) al cargar
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hydrateAll);
  } else {
    hydrateAll();
  }

  // 2) cada vez que se renderiza el listado del modal (incidents_modal.js ya dispara este evento)
  window.addEventListener("soar-incidents-rendered", hydrateAll);

  console.log("[SOAR_TICKET_MAP_HYDRATE]", VER, "✅ listo");
})();
