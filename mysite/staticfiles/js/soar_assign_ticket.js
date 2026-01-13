// static/js/soar_assign_ticket.js
// (FINAL - estable + PageLoader + sin multi-click + hydrate assigned)
(function () {
  const VER = "2026-01-06 FINAL v2 (hydrate assigned)";

  // Evitar doble carga (si tu template lo incluye 2 veces, se vuelve loco)
  if (window.__SOAR_ASSIGN_TICKET_READY__) {
    console.warn("[SOAR_ASSIGN]", VER, "ya estaba inicializado (revisa doble include / caché).");
    return;
  }
  window.__SOAR_ASSIGN_TICKET_READY__ = true;

  const Q = (s, r = document) => r.querySelector(s);

  const table = Q("#tbl-incidentes");
  const ctxMenu = Q("#soarCtxMenu");
  const assignModal = Q("#assignTicketModal");

  if (!table || !ctxMenu || !assignModal) {
    console.error("[SOAR_ASSIGN] Faltan nodos:", {
      "#tbl-incidentes": !!table,
      "#soarCtxMenu": !!ctxMenu,
      "#assignTicketModal": !!assignModal,
    });
    return;
  }

  const assignBackdrop = Q("[data-assign-backdrop]", assignModal);
  const assignClose = Q("[data-assign-close]", assignModal);
  const assignCancel = Q("#assign-cancel", assignModal);

  const elEventTitle = Q("#assign-event-title", assignModal);
  const elEventId = Q("#assign-event-id", assignModal);

  const tenantStatic = Q("#assign-tenant-static", assignModal);
  const selUser = Q("#assign-user", assignModal);
  const selDuration = Q("#assign-duration", assignModal);
  const customWrap = Q("#assign-custom-date-wrap", assignModal);
  const inpCustomDate = Q("#assign-custom-date", assignModal);
  const dueText = Q("#assign-due-text", assignModal);
  const inpInitialNotes = Q("#assign-initial-notes", assignModal);

  let selectedRow = null;
  let currentDueISO = "";
  let openingAt = 0;
  let busy = false;
  let lastSubmitAt = 0;

  // ===== PageLoader (overlay global) =====
  function PL_show(msg) {
    try { window.PageLoader?.show?.(msg || "Cargando…"); } catch {}
  }
  function PL_hide() {
    try { window.PageLoader?.hide?.(); } catch {}
  }

  // ===== Focus / aria =====
  function safeBlur() {
    try { document.activeElement?.blur?.(); } catch {}
  }
  function setInert(el, on) {
    if (!el) return;
    try { on ? el.setAttribute("inert", "") : el.removeAttribute("inert"); } catch {}
  }
  function showEl(el) {
    if (!el) return;
    el.classList.remove("hidden");
    el.setAttribute("aria-hidden", "false");
    setInert(el, false);
  }
  function hideEl(el) {
    if (!el) return;
    if (el.contains(document.activeElement)) safeBlur();
    el.classList.add("hidden");
    el.setAttribute("aria-hidden", "true");
    setInert(el, true);
  }

  // ===== Scroll lock estable (evita “saltito”) =====
  function lockScroll() {
    const sbw = window.innerWidth - document.documentElement.clientWidth;
    document.body.style.setProperty("--sbw", sbw > 0 ? `${sbw}px` : "0px");
    document.body.classList.add("modal-open");
  }
  function unlockScrollIfNoModals() {
    const anyOpen = Array.from(document.querySelectorAll(".modal"))
      .some(m => !m.classList.contains("hidden"));
    if (!anyOpen) {
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("--sbw");
    }
  }

  // ===== CSRF =====
  function _stripQuotes(s) {
    s = String(s || "").trim();
    if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) s = s.slice(1, -1).trim();
    return s;
  }
  function _isValidCsrfToken(t) {
    t = _stripQuotes(t);
    return !!t && (t.length === 32 || t.length === 64);
  }
  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]+)"));
    return m ? decodeURIComponent(m[1]) : "";
  }
  function getCSRFToken() {
    const c = _stripQuotes(getCookie("csrftoken"));
    if (_isValidCsrfToken(c)) return c;

    const inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const v = _stripQuotes(inp?.value || "");
    if (_isValidCsrfToken(v)) return v;

    const meta =
      document.querySelector('meta[name="csrf-token"]') ||
      document.querySelector('meta[name="csrfmiddlewaretoken"]');
    const mv = _stripQuotes(meta?.getAttribute("content") || "");
    if (_isValidCsrfToken(mv)) return mv;

    const dv = _stripQuotes(document.body?.dataset?.csrfToken || "");
    if (_isValidCsrfToken(dv)) return dv;

    return "";
  }

  // ===== Info modal reutilizable =====
  function ensureInfoModal() {
    let m = Q("#ticketCreatedModal");
    if (m) return m;

    m = document.createElement("div");
    m.id = "ticketCreatedModal";
    m.className = "modal hidden";
    m.setAttribute("aria-hidden", "true");
    m.innerHTML = `
      <div class="modal-backdrop" data-info-backdrop></div>
      <div class="modal-card created-info-card" role="dialog" aria-modal="true" aria-labelledby="ticketCreatedTitle">
        <div class="modal-header">
          <h3 id="ticketCreatedTitle">Información</h3>
          <button class="modal-close" type="button" aria-label="Cerrar" data-info-x>&times;</button>
        </div>
        <div class="modal-body">
          <p class="created-info-text"></p>
          <div class="created-info-actions">
            <button type="button" class="btn primary" data-info-ok>OK</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(m);

    const close = () => {
      hideEl(m);
      unlockScrollIfNoModals();
    };

    Q("[data-info-backdrop]", m)?.addEventListener("click", close);
    Q("[data-info-ok]", m)?.addEventListener("click", close);
    Q("[data-info-x]", m)?.addEventListener("click", close);
    m.querySelector(".created-info-card")?.addEventListener("click", (e) => e.stopPropagation());

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !m.classList.contains("hidden")) close();
    });

    return m;
  }

  function openInfoModal(title, msg) {
    const m = ensureInfoModal();
    Q("#ticketCreatedTitle", m).textContent = title || "Información";
    m.querySelector(".created-info-text").textContent = msg || "";
    lockScroll();
    showEl(m);
    setTimeout(() => Q("[data-info-ok]", m)?.focus?.(), 30);
  }

  // ===== Helpers UI =====
  function isRowAssigned(tr) {
    const v = String(tr?.dataset?.assigned || "").trim().toLowerCase();
    return v === "1" || v === "true" || v === "yes";
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

  function ensureAssignedCellRendered(tr) {
    if (!tr) return;
    const cell = tr.querySelector("[data-assigned-cell]");
    if (!cell) return;
    cell.innerHTML = renderAssignedCell(isRowAssigned(tr));
  }

  // pinta toda la tabla al cargar (y lo dejamos disponible para refrescar luego)
  function hydrateAssignedCells() {
    try {
      table.querySelectorAll("tr.soar-row").forEach((tr) => ensureAssignedCellRendered(tr));
    } catch (e) {
      console.warn("[SOAR_ASSIGN] hydrateAssignedCells warn:", e);
    }
  }
  window.SOAR_assign_refreshAssigned = hydrateAssignedCells;

  function markRowAssigned(tr, assignedName) {
    if (!tr) return;
    tr.dataset.assigned = "1";

    const nm = (assignedName || "").trim();
    if (nm) {
      tr.dataset.assignedName = nm;
      tr.dataset.assigned_name = nm;
      tr.dataset.ticketName = nm;
      tr.dataset.ticket_name = nm;
      tr.dataset.ticketAssignedToName = nm;
    }

    ensureAssignedCellRendered(tr);
  }

  function getSelectedAssignedName() {
    const opt = selUser?.selectedOptions?.[0];
    if (!opt) return "";
    const txt = (opt.textContent || "").trim();
    if (!txt) return "";
    return txt.split("—")[0].trim();
  }

  // ===== Context menu =====
  function clampMenuToViewport(x, y) {
    ctxMenu.style.left = "0px";
    ctxMenu.style.top = "0px";
    showEl(ctxMenu);

    const rect = ctxMenu.getBoundingClientRect();
    const pad = 8;

    const maxX = window.innerWidth - rect.width - pad;
    const maxY = window.innerHeight - rect.height - pad;

    return {
      x: Math.max(pad, Math.min(x, maxX)),
      y: Math.max(pad, Math.min(y, maxY)),
    };
  }

  function showCtxMenu(x, y) {
    const pos = clampMenuToViewport(x, y);
    ctxMenu.style.left = `${pos.x}px`;
    ctxMenu.style.top = `${pos.y}px`;
  }

  function hideCtxMenu() {
    hideEl(ctxMenu);
  }

  // ===== Due date =====
  function addDays(dateObj, days) {
    const d = new Date(dateObj);
    d.setDate(d.getDate() + days);
    return d;
  }

  function toISODate(d) {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }

  function formatLongCL(iso) {
    try {
      const [y, m, d] = iso.split("-").map(Number);
      return new Date(y, m - 1, d).toLocaleDateString("es-CL", { day: "numeric", month: "long", year: "numeric" });
    } catch {
      return iso;
    }
  }

  function computeDueDate() {
    const today = new Date();
    const dur = selDuration ? selDuration.value : "7";

    if (dur === "custom") {
      currentDueISO = (inpCustomDate?.value || "").trim();
      customWrap && customWrap.classList.remove("hidden");
    } else {
      const n = parseInt(dur, 10);
      currentDueISO = toISODate(addDays(today, isNaN(n) ? 7 : n));
      customWrap && customWrap.classList.add("hidden");
    }

    if (dueText) {
      dueText.textContent = currentDueISO
        ? `Fecha de vencimiento: ${formatLongCL(currentDueISO)}`
        : "Fecha de vencimiento: —";
    }

    updateSubmitVisualState();
  }

  // NO usamos disabled (para poder mostrar mensajes al click)
  function setSubmitState(enabled, busyState) {
    const btn = Q("#assign-submit", assignModal);
    if (!btn) return;

    if (busyState) {
      btn.classList.add("is-busy");
      btn.setAttribute("aria-disabled", "true");
      btn.classList.remove("is-disabled");
      return;
    }

    btn.classList.remove("is-busy");

    if (!enabled) {
      btn.classList.add("is-disabled");
      btn.setAttribute("aria-disabled", "true");
    } else {
      btn.classList.remove("is-disabled");
      btn.removeAttribute("aria-disabled");
    }
  }

  function updateSubmitVisualState() {
    const userOk = !!(selUser?.value || "").trim();
    const notesOk = !!(inpInitialNotes?.value || "").trim();
    const dur = selDuration?.value || "7";
    const dueOk = (dur !== "custom") || !!(inpCustomDate?.value || "").trim();
    setSubmitState(userOk && notesOk && dueOk && !!currentDueISO, false);
  }

  // ===== Users =====
  async function loadUsersForTenant(tenantId) {
    if (!selUser) return;

    selUser.disabled = true;
    selUser.innerHTML = `<option value="">Cargando usuarios…</option>`;

    const endpoint = (document.body?.dataset?.soarTenantUsersUrl || "").trim();
    if (!endpoint) {
      selUser.innerHTML = `<option value="">(Falta data-soar-tenant-users-url)</option>`;
      selUser.disabled = false;
      updateSubmitVisualState();
      return;
    }

    const csrf = getCSRFToken();
    if (!_isValidCsrfToken(csrf)) {
      selUser.innerHTML = `<option value="">Error: CSRF no disponible</option>`;
      selUser.disabled = false;
      updateSubmitVisualState();
      openInfoModal("Sesión / CSRF no disponible", "No se pudo obtener el token CSRF. Recarga la página e intenta nuevamente.");
      return;
    }

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf,
        },
        credentials: "same-origin",
        body: JSON.stringify({ tenant_id: tenantId || null }),
      });

      const data = await res.json().catch(() => ({}));
      const items = Array.isArray(data) ? data : (data.users || []);

      selUser.innerHTML = `<option value="">Selecciona un usuario…</option>`;

      if (!items.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No hay usuarios activos en este tenant";
        selUser.appendChild(opt);
      } else {
        items.forEach(u => {
          const opt = document.createElement("option");
          opt.value = String(u.id);

          const label = (u.full_name || u.username || `User ${u.id}`).trim();
          const email = u.email ? ` — ${u.email}` : "";

          opt.dataset.fullName = label;
          opt.textContent = `${label}${email}`;
          selUser.appendChild(opt);
        });
      }

      selUser.disabled = false;
      updateSubmitVisualState();
    } catch (e) {
      console.error(e);
      selUser.innerHTML = `<option value="">Error cargando usuarios</option>`;
      selUser.disabled = false;
      updateSubmitVisualState();
    }
  }

  // ===== Modal =====
  function openAssignModalForRow(tr) {
    if (!tr) return;

    // por si la tabla viene “cruda”, pintamos asignado antes de decidir
    ensureAssignedCellRendered(tr);

    if (isRowAssigned(tr)) {
      openInfoModal("Ticket ya asignado", "Este evento ya cuenta con un ticket asignado.");
      return;
    }

    selectedRow = tr;

    const id = tr.dataset.id || "—";
    const tipo = tr.dataset.tipo || "—";
    const dev = tr.dataset.dispositivo || "—";

    if (elEventTitle) elEventTitle.textContent = `${tipo} (${dev})`;
    if (elEventId) elEventId.textContent = id;

    if (selUser) selUser.value = "";
    if (selDuration) selDuration.value = "7";
    if (customWrap) customWrap.classList.add("hidden");
    if (inpCustomDate) inpCustomDate.value = "";
    if (inpInitialNotes) inpInitialNotes.value = "";

    computeDueDate();

    openingAt = Date.now();
    lockScroll();
    showEl(assignModal);

    const tenantId = (tenantStatic?.dataset?.tenantId || "").trim();
    loadUsersForTenant(tenantId);

    updateSubmitVisualState();
    setTimeout(() => selUser?.focus?.(), 80);
  }

  function closeAssignModal() {
    hideEl(assignModal);
    unlockScrollIfNoModals();
  }

  function shouldIgnoreBackdropNow() {
    return Date.now() - openingAt < 250; // evita “primer click” raro al abrir
  }

  // ===== Submit =====
  async function submitCreateTicket(ev) {
    ev?.preventDefault?.();
    ev?.stopPropagation?.();

    // anti multi-click (doble listener, click fantasma, etc.)
    const now = Date.now();
    if (now - lastSubmitAt < 450) return;
    lastSubmitAt = now;

    if (busy) return;

    if (!selectedRow) {
      openInfoModal("Error", "No se detectó el evento seleccionado. Haz click derecho nuevamente e intenta.");
      return;
    }

    if (isRowAssigned(selectedRow)) {
      closeAssignModal();
      openInfoModal("Ticket ya asignado", "Este evento ya cuenta con un ticket asignado.");
      return;
    }

    const assignedTo = (selUser?.value || "").trim();
    const assignedName = getSelectedAssignedName();
    const initialNotes = (inpInitialNotes?.value || "").trim();

    // Mensajes solicitados
    if (!assignedTo) {
      openInfoModal("Usuario requerido", "Debes seleccionar un usuario para crear el ticket.");
      setTimeout(() => selUser?.focus?.(), 80);
      return;
    }

    if (!initialNotes) {
      openInfoModal("Comentario inicial requerido", "Debes ingresar un comentario inicial para crear el ticket.");
      setTimeout(() => inpInitialNotes?.focus?.(), 80);
      return;
    }

    if (!currentDueISO) {
      openInfoModal("Fecha requerida", "Debes definir una fecha de vencimiento válida.");
      return;
    }

    const endpoint = (document.body?.dataset?.soarTicketCreateUrl || "").trim();
    if (!endpoint) {
      openInfoModal("Configuración faltante", "Falta data-soar-ticket-create-url en <body>.");
      return;
    }

    const csrf = getCSRFToken();
    if (!_isValidCsrfToken(csrf)) {
      openInfoModal("CSRF no disponible", "No se pudo obtener un token CSRF válido. Recarga la página e intenta nuevamente.");
      return;
    }

    const payload = {
      alarm_id: (selectedRow.dataset.id || "").trim(),
      dispositivo: selectedRow.dataset.dispositivo || "",
      tipo_de_amenaza: selectedRow.dataset.tipo || "",
      nivel_de_severidad: selectedRow.dataset.sev || "",
      event_date: (selectedRow.dataset.date || "").trim() || null,
      event_time: (selectedRow.dataset.time || "").trim() || null,
      descripcion_incidente: selectedRow.dataset.descripcion || "",
      analisis_criticidad: selectedRow.dataset.analisis || "",
      medidas_correctivas: selectedRow.dataset.acciones || "",
      resumen_humano: selectedRow.dataset.resumen || "",
      riesgo_detectado: selectedRow.dataset.riesgo || "",
      application: selectedRow.dataset.app || "",
      assigned_to: assignedTo,
      due_date: currentDueISO,
      initial_notes: initialNotes,
    };

    try {
      busy = true;
      setSubmitState(false, true);
      PL_show("Creando ticket…");

      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf,
        },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      });

      const out = await res.json().catch(() => ({}));

      if (res.status === 409 || out.code === "ALREADY_EXISTS") {
        markRowAssigned(selectedRow, selectedRow.dataset.assignedName || assignedName);
        closeAssignModal();
        PL_hide();
        openInfoModal("Ticket ya asignado", "Este evento ya cuenta con un ticket asignado.");
        return;
      }

      if (!res.ok || !out.ok) {
        throw new Error(out.error || `HTTP ${res.status}`);
      }

      const backendName = (out.assigned_to_name || out.assigned_name || "").trim();
      markRowAssigned(selectedRow, backendName || assignedName);

      closeAssignModal();
      PL_hide();
      openInfoModal("Ticket creado", "Ticket creado con éxito, puedes revisar el detalle en el módulo de tickets.");
    } catch (e) {
      PL_hide();
      openInfoModal("Error", `No se pudo crear el ticket: ${e.message || e}`);
    } finally {
      busy = false;
      setSubmitState(true, false);
      updateSubmitVisualState();
      PL_hide();
    }
  }

  // ==========================================================
  // BINDINGS (delegación => no se rompe si cambia el DOM)
  // ==========================================================

  // Estado inicial oculto/inert
  hideEl(ctxMenu);
  hideEl(assignModal);

  // 1) Pintar “Asignado” para TODAS las filas al cargar
  hydrateAssignedCells();

  // Click derecho sobre fila
  table.addEventListener("contextmenu", (ev) => {
    const tr = ev.target.closest("tr.soar-row");
    if (!tr) return;

    ev.preventDefault();
    selectedRow = tr;

    // por si después se pierde selectedRow
    ctxMenu.dataset.alarmId = (tr.dataset.id || "").trim();

    showCtxMenu(ev.clientX, ev.clientY);
  });

  // Cerrar ctxMenu al click fuera
  document.addEventListener("click", (ev) => {
    if (!ctxMenu.classList.contains("hidden") && !ev.target.closest("#soarCtxMenu")) {
      hideCtxMenu();
    }
  }, true);

  window.addEventListener("scroll", hideCtxMenu, { passive: true });
  window.addEventListener("resize", hideCtxMenu);

  // Click en “Asignar Ticket” (delegado)
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest("#ctxAssignTicketBtn");
    if (!btn) return;

    ev.preventDefault();
    ev.stopPropagation();

    hideCtxMenu();

    // abrir en next tick para evitar “se mueve y no pasa nada”
    setTimeout(() => {
      if (!selectedRow) {
        const aid = (ctxMenu.dataset.alarmId || "").trim();
        if (aid) {
          try {
            selectedRow = table.querySelector(`tr.soar-row[data-id="${CSS.escape(aid)}"]`);
          } catch {
            selectedRow = table.querySelector(`tr.soar-row[data-id="${aid}"]`);
          }
        }
      }

      if (!selectedRow) {
        openInfoModal("Error", "No se detectó la fila seleccionada. Haz click derecho nuevamente.");
        return;
      }

      openAssignModalForRow(selectedRow);
    }, 0);
  }, true);

  // Cerrar modal por backdrop / close / cancel
  assignBackdrop?.addEventListener("click", (ev) => {
    if (shouldIgnoreBackdropNow()) {
      ev.preventDefault();
      ev.stopPropagation();
      return;
    }
    closeAssignModal();
  }, true);

  assignClose?.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    closeAssignModal();
  }, true);

  assignCancel?.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    closeAssignModal();
  }, true);

  // Evitar que click dentro de la card cierre por bubbling raro
  assignModal.querySelector(".modal-card")?.addEventListener("click", (e) => e.stopPropagation(), true);

  // ESC
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    hideCtxMenu();
    if (!assignModal.classList.contains("hidden")) closeAssignModal();
  });

  // Actualizar estado “habilitado visual”
  selDuration?.addEventListener("change", computeDueDate);
  inpCustomDate?.addEventListener("change", computeDueDate);
  selUser?.addEventListener("change", updateSubmitVisualState);
  inpInitialNotes?.addEventListener("input", updateSubmitVisualState);

  // Click en “Crear/Asignar ticket” (delegado)
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest("#assign-submit");
    if (!btn) return;
    submitCreateTicket(ev);
  }, true);

  // Si tu botón está dentro de un <form>, capturamos submit también (por Enter)
  assignModal.addEventListener("submit", (ev) => {
    if (ev.target?.closest?.("#assignTicketModal")) {
      submitCreateTicket(ev);
    }
  }, true);

  //  si otro script re-renderiza filas, que nos avise
  window.addEventListener("soar-incidents-rendered", () => {
    hydrateAssignedCells();
  });

  computeDueDate();

  console.log("[SOAR_ASSIGN]", VER, "✅ listo");
})();
