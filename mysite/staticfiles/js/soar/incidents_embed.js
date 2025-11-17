// static/js/soar/incidents_embed.js
(function(){
  const $  = (s,r=document)=>r.querySelector(s);
  const $$ = (s,r=document)=>Array.from(r.querySelectorAll(s));

  let INCIDENTS = [];

  function loadIncidents(){
    const el = $("#soar-incidents");
    try { INCIDENTS = el ? (JSON.parse(el.textContent || "[]") || []) : []; }
    catch(e){ console.error("[incidents_embed] JSON inválido en #soar-incidents", e); INCIDENTS = []; }
  }

  function asText(v){ return (v==null || v==="") ? "—" : String(v); }
  function sevClass(sev){
    const s = String(sev||"").toLowerCase();
    if (["critical","crítico","critico"].includes(s)) return "sev-critical";
    if (["high","alto"].includes(s)) return "sev-high";
    if (["medium","medio"].includes(s)) return "sev-medium";
    if (["low","bajo"].includes(s)) return "sev-low";
    if (s==="info") return "sev-info";
    return "sev-na";
  }

  function escapeAttr(t){ return String(t||"").replaceAll(`"`,`&quot;`); }

  // ---------- Tabla embebida en la card ----------
  function renderEmbeddedTable(list){
    const tbody = $("#tbl-incidentes-embed tbody");
    if (!tbody) return;
    tbody.innerHTML = (list||[]).map(it=>`
      <tr
        data-id="${it.alarmd_id||""}"
        data-dispositivo="${escapeAttr(it.dispositivo)}"
        data-tipo="${escapeAttr(it.tipo_de_amenaza)}"
        data-sev="${escapeAttr(it.nivel_de_severidad)}"
        data-date="${it.date||""}"
        data-time="${it.time||""}"
        data-descripcion="${escapeAttr(it.descripcion_incidente)}"
        data-analisis="${escapeAttr(it.analisis_criticidad)}"
        data-acciones="${escapeAttr(it.medidas_correctivas)}"
        data-resumen="${escapeAttr(it.resumen_humano)}"
        data-riesgo="${escapeAttr(it.riego_detectado)}"
        data-app="${escapeAttr(it.application)}"
      >
        <td class="mono nowrap">${asText(it.alarmd_id)}</td>
        <td class="w-240" title="${asText(it.dispositivo)}">${asText(it.dispositivo)}</td>
        <td class="w-320" title="${asText(it.tipo_de_amenaza)}">${asText(it.tipo_de_amenaza)}</td>
        <td class="nowrap">
          <span class="pill ${sevClass(it.nivel_de_severidad)}">${asText(it.nivel_de_severidad)}</span>
        </td>
        <td class="mono nowrap">${asText(it.date)}</td>
        <td class="mono nowrap">${asText(it.time)}</td>
      </tr>
    `).join("");

    tbody.onclick = (ev)=>{
      const tr = ev.target.closest("tr"); if (!tr) return;
      openDetailFromRow(tr);
    };
  }

  // ---------- Modal de LISTA ----------
  function openListModal(list, caption=""){
    const modal = $("#incidentsListModal");
    if (!modal) return;
    const tbody = $("#tbl-incidentes-modal tbody");
    const cap   = $("#inc-list-caption");
    const fmt = (s)=> (s==null||s==="") ? "—" : String(s);

    tbody.innerHTML = (list||[]).map(it=>`
      <tr
        data-id="${it.alarmd_id||""}"
        data-dispositivo="${escapeAttr(it.dispositivo)}"
        data-tipo="${escapeAttr(it.tipo_de_amenaza)}"
        data-sev="${escapeAttr(it.nivel_de_severidad)}"
        data-date="${it.date||""}"
        data-time="${it.time||""}"
        data-descripcion="${escapeAttr(it.descripcion_incidente)}"
        data-analisis="${escapeAttr(it.analisis_criticidad)}"
        data-acciones="${escapeAttr(it.medidas_correctivas)}"
        data-resumen="${escapeAttr(it.resumen_humano)}"
        data-riesgo="${escapeAttr(it.riego_detectado)}"
        data-app="${escapeAttr(it.application)}"
      >
        <td class="mono nowrap">${fmt(it.alarmd_id)}</td>
        <td class="w-240" title="${fmt(it.dispositivo)}">${fmt(it.dispositivo)}</td>
        <td class="w-320" title="${fmt(it.tipo_de_amenaza)}">${fmt(it.tipo_de_amenaza)}</td>
        <td class="nowrap"><span class="pill ${sevClass(it.nivel_de_severidad)}">${fmt(it.nivel_de_severidad)}</span></td>
        <td class="mono nowrap">${fmt(it.date)}</td>
        <td class="mono nowrap">${fmt(it.time)}</td>
      </tr>
    `).join("");

    if (cap) cap.textContent = caption || "";

    tbody.onclick = (ev)=>{
      const tr = ev.target.closest("tr"); if (!tr) return;
      openDetailFromRow(tr);
    };

    bindModalBasics(modal);
    document.body.classList.add("modal-open");
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden","false");
  }

  function bindModalBasics(modal){
    modal.querySelector(".modal-backdrop")?.addEventListener("click", ()=>closeModal(modal));
    modal.querySelector("[data-close]")?.addEventListener("click", ()=>closeModal(modal));
    modal.querySelector(".modal-card")?.addEventListener("click", e=>e.stopPropagation());
    document.addEventListener("keydown", (e)=>{ if (e.key==="Escape") closeModal(modal); }, { once:true });
  }
  function closeModal(m){ if (!m) return; m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); document.body.classList.remove("modal-open"); }

  // ---------- Detalle (mismo que en list.js) ----------
  function openDetailFromRow(tr){
    const modal  = $("#incidentModal"); if (!modal) return;
    const id   = tr.dataset.id || "—";
    const dev  = tr.dataset.dispositivo || "—";
    const tipo = tr.dataset.tipo || "—";
    const sev  = tr.dataset.sev || "N/A";
    const date = tr.dataset.date || "—";
    const time = tr.dataset.time || "—";

    const title = $("#inc-title");
    if (title) title.innerHTML = `🚨 <strong>${sev || "N/A"}</strong> — <span class="muted">${dev}</span>`;

    const meta = $("#inc-meta-list");
    if (meta){
      meta.innerHTML = [
        `<li><span class="mono">ID:</span> ${id}</li>`,
        `<li><strong>Dispositivo:</strong> ${dev}</li>`,
        `<li><strong>Tipo:</strong> ${tipo}</li>`,
        `<li><strong>Fecha/Hora:</strong> ${date} ${time}</li>`,
      ].join("");
    }

    setText("#inc-riesgo",   tr.dataset.descripcion || tr.dataset.riesgo || "—");
    setText("#inc-clasif",   tr.dataset.analisis || "—");
    setText("#inc-acciones", tr.dataset.acciones || "—");
    setText("#inc-resumen",  tr.dataset.resumen || "—");

    const app = tr.dataset.app || "";
    const wrap = $("#inc-app-wrap");
    if (wrap) {
      if (app){ setText("#inc-app", app); wrap.style.display=""; }
      else { wrap.style.display="none"; }
    }

    bindModalBasics(modal);
    document.body.classList.add("modal-open");
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden","false");
  }
  function setText(sel, txt){ const el = $(sel); if (el) el.textContent = txt; }

  // ---------- API global para que los gráficos invoquen ----------
  function findByAlarmIds(ids){
    const set = new Set((ids||[]).map(x=>String(x||"").trim()).filter(Boolean));
    return set.size ? INCIDENTS.filter(i => set.has(String(i.alarmd_id||"").trim())) : [];
  }

  function init(){
    loadIncidents();
    renderEmbeddedTable(INCIDENTS.slice(0, 50)); // muestra algo inicial

    const btnGlobal = $("#btn-ver-alarmas-global");
    if (btnGlobal){
      btnGlobal.addEventListener("click", ()=>{
        openListModal(INCIDENTS, `Se muestran ${INCIDENTS.length} incidentes disponibles.`);
      });
    }
  }

  window.SOAR_Incidents = {
    showForAlarmIds: function(alarmIds, caption){
      loadIncidents();
      const list = findByAlarmIds(alarmIds);
      renderEmbeddedTable(list);
      openListModal(list, caption || `Coincidencias: ${list.length}`);
    }
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
