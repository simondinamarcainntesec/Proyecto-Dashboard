// static/js/soar/incidents_embed.js
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  let INCIDENTS = [];

  // =========================
  // Helpers seguridad (XSS)
  // =========================
  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // Para atributos HTML, el mismo escape (incluye comillas)
  function escapeAttr(s) {
    return escapeHtml(s);
  }

  function asText(v) {
    return (v == null || v === "") ? "—" : String(v);
  }

  function sevClass(sev) {
    const s = String(sev || "").toLowerCase();
    if (["critical", "crítico", "critico"].includes(s)) return "sev-critical";
    if (["high", "alto"].includes(s)) return "sev-high";
    if (["medium", "medio"].includes(s)) return "sev-medium";
    if (["low", "bajo"].includes(s)) return "sev-low";
    if (s === "info") return "sev-info";
    return "sev-na";
  }

  // =========================
  // Data load
  // =========================
  function loadIncidents() {
    const el = $("#soar-incidents");
    try {
      INCIDENTS = el ? (JSON.parse(el.textContent || "[]") || []) : [];
      if (!Array.isArray(INCIDENTS)) INCIDENTS = [];
    } catch (e) {
      console.error("[incidents_embed] JSON inválido en #soar-incidents", e);
      INCIDENTS = [];
    }
  }

  // =========================
  // DOM builders (sin innerHTML con datos)
  // =========================
  function clearNode(node) {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function tdText(text, className, title) {
    const td = document.createElement("td");
    if (className) td.className = className;
    td.textContent = asText(text);
    if (title != null && title !== "") td.title = asText(title);
    return td;
  }

  function buildRow(it) {
    const tr = document.createElement("tr");

    // dataset (atributos) - aquí NO ejecuta JS, pero igual sanitizamos (por higiene)
    tr.dataset.id = String(it.alarmd_id || "");
    tr.dataset.dispositivo = String(it.dispositivo || "");
    tr.dataset.tipo = String(it.tipo_de_amenaza || "");
    tr.dataset.sev = String(it.nivel_de_severidad || "");
    tr.dataset.date = String(it.date || "");
    tr.dataset.time = String(it.time || "");
    tr.dataset.descripcion = String(it.descripcion_incidente || "");
    tr.dataset.analisis = String(it.analisis_criticidad || "");
    tr.dataset.acciones = String(it.medidas_correctivas || "");
    tr.dataset.resumen = String(it.resumen_humano || "");
    tr.dataset.riesgo = String(it.riego_detectado || "");
    tr.dataset.app = String(it.application || "");

    // Celdas
    tr.appendChild(tdText(it.alarmd_id, "mono nowrap"));
    tr.appendChild(tdText(it.dispositivo, "w-240", it.dispositivo));
    tr.appendChild(tdText(it.tipo_de_amenaza, "w-320", it.tipo_de_amenaza));

    const tdSev = document.createElement("td");
    tdSev.className = "nowrap";
    const pill = document.createElement("span");
    pill.className = `pill ${sevClass(it.nivel_de_severidad)}`;
    pill.textContent = asText(it.nivel_de_severidad);
    tdSev.appendChild(pill);
    tr.appendChild(tdSev);

    tr.appendChild(tdText(it.date, "mono nowrap"));
    tr.appendChild(tdText(it.time, "mono nowrap"));

    return tr;
  }

  // =========================
  // Tabla embebida
  // =========================
  function renderEmbeddedTable(list) {
    const tbody = $("#tbl-incidentes-embed tbody");
    if (!tbody) return;

    clearNode(tbody);

    const safeList = Array.isArray(list) ? list : [];
    for (const it of safeList) {
      const tr = buildRow(it);
      tbody.appendChild(tr);
    }

    tbody.onclick = (ev) => {
      const tr = ev.target.closest("tr");
      if (!tr) return;
      openDetailFromRow(tr);
    };
  }

  // =========================
  // Modal LISTA
  // =========================
  function bindModalBasics(modal) {
    if (!modal) return;

    // Evita duplicar listeners
    if (modal.dataset.bound === "1") return;
    modal.dataset.bound = "1";

    modal.querySelector(".modal-backdrop")?.addEventListener("click", () => closeModal(modal));
    modal.querySelector("[data-close]")?.addEventListener("click", () => closeModal(modal));
    modal.querySelector(".modal-card")?.addEventListener("click", (e) => e.stopPropagation());
  }

  function closeModal(m) {
    if (!m) return;
    m.classList.add("hidden");
    m.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

  function openListModal(list, caption = "") {
    const modal = $("#incidentsListModal");
    if (!modal) return;

    const tbody = $("#tbl-incidentes-modal tbody");
    const cap = $("#inc-list-caption");

    if (cap) cap.textContent = caption || "";

    if (tbody) {
      clearNode(tbody);
      const safeList = Array.isArray(list) ? list : [];
      for (const it of safeList) {
        tbody.appendChild(buildRow(it));
      }

      tbody.onclick = (ev) => {
        const tr = ev.target.closest("tr");
        if (!tr) return;
        openDetailFromRow(tr);
      };
    }

    bindModalBasics(modal);

    // ESC para cerrar (solo una vez por apertura)
    document.addEventListener(
      "keydown",
      (e) => {
        if (e.key === "Escape") closeModal(modal);
      },
      { once: true }
    );

    document.body.classList.add("modal-open");
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
  }

  // =========================
  // Detalle (blindado con textContent)
  // =========================
  function setText(sel, txt) {
    const el = $(sel);
    if (el) el.textContent = asText(txt);
  }

  function setMetaList(items) {
    const ul = $("#inc-meta-list");
    if (!ul) return;
    clearNode(ul);

    for (const it of items) {
      const li = document.createElement("li");
      // it puede ser {label, value, mono?}
      if (it.mono) {
        const span = document.createElement("span");
        span.className = "mono";
        span.textContent = it.label;
        li.appendChild(span);
        li.appendChild(document.createTextNode(" " + asText(it.value)));
      } else {
        const strong = document.createElement("strong");
        strong.textContent = it.label;
        li.appendChild(strong);
        li.appendChild(document.createTextNode(" " + asText(it.value)));
      }
      ul.appendChild(li);
    }
  }

  function setTitle(sev, dev) {
    const title = $("#inc-title");
    if (!title) return;

    // layout fijo con HTML, contenido escapado
    const sevSafe = escapeHtml(asText(sev || "N/A"));
    const devSafe = escapeHtml(asText(dev || "—"));
    title.innerHTML = `🚨 <strong>${sevSafe}</strong> — <span class="muted">${devSafe}</span>`;
  }

  function openDetailFromRow(tr) {
    const modal = $("#incidentModal");
    if (!modal) return;

    const id = tr.dataset.id || "—";
    const dev = tr.dataset.dispositivo || "—";
    const tipo = tr.dataset.tipo || "—";
    const sev = tr.dataset.sev || "N/A";
    const date = tr.dataset.date || "—";
    const time = tr.dataset.time || "—";

    setTitle(sev, dev);

    setMetaList([
      { label: "ID:", value: id, mono: true },
      { label: "Dispositivo:", value: dev },
      { label: "Tipo:", value: tipo },
      { label: "Fecha/Hora:", value: `${date} ${time}` },
    ]);

    // Ojo: aquí tú usabas descripcion o riesgo. Mantengo tu lógica.
    setText("#inc-riesgo", tr.dataset.descripcion || tr.dataset.riesgo || "—");
    setText("#inc-clasif", tr.dataset.analisis || "—");
    setText("#inc-acciones", tr.dataset.acciones || "—");
    setText("#inc-resumen", tr.dataset.resumen || "—");

    const app = tr.dataset.app || "";
    const wrap = $("#inc-app-wrap");
    if (wrap) {
      if (app) {
        setText("#inc-app", app);
        wrap.style.display = "";
      } else {
        wrap.style.display = "none";
      }
    }

    bindModalBasics(modal);

    document.addEventListener(
      "keydown",
      (e) => {
        if (e.key === "Escape") closeModal(modal);
      },
      { once: true }
    );

    document.body.classList.add("modal-open");
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
  }

  // =========================
  // Filtro por alarm ids
  // =========================
  function findByAlarmIds(ids) {
    const set = new Set((ids || []).map((x) => String(x || "").trim()).filter(Boolean));
    return set.size
      ? INCIDENTS.filter((i) => set.has(String(i.alarmd_id || "").trim()))
      : [];
  }

  // =========================
  // Init + API global
  // =========================
  function init() {
    loadIncidents();
    renderEmbeddedTable(INCIDENTS.slice(0, 50));

    const btnGlobal = $("#btn-ver-alarmas-global");
    if (btnGlobal) {
      btnGlobal.addEventListener("click", () => {
        openListModal(INCIDENTS, `Se muestran ${INCIDENTS.length} incidentes disponibles.`);
      });
    }
  }

  window.SOAR_Incidents = {
    showForAlarmIds: function (alarmIds, caption) {
      loadIncidents();
      const list = findByAlarmIds(alarmIds);
      renderEmbeddedTable(list);
      openListModal(list, caption || `Coincidencias: ${list.length}`);
    },
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
