// subtype-modal-hook.js
// No modifica state ni gráficos. Solo añade el botón "Ver alarmas" al card Subtype.
// Lógica: si hay una barra seleccionada (tu filtro clásico), abre solo ese subtype.
// Si no, abre TODOS los subtypes visibles en el chart.

(() => {
  const BTN_ID = "btn-open-subtype-alarms";
  const MAX_TRIES = 60;
  let tries = 0;

  function getChart() {
    const cv = document.getElementById("subtypeBar");
    return (cv && window.Chart && Chart.getChart) ? Chart.getChart(cv) : null;
  }

  function getSelectedSubtypeFromState() {
    try { if (typeof window.getState === "function") {
      const st = window.getState() || {};
      const s = String(st.subtypeFilter || "").trim();
      if (s) return s;
    }} catch {}
    try { const s2 = String(window.__APP_STATE?.subtypeFilter || "").trim(); if (s2) return s2; } catch {}
    return "";
  }

  function getVisibleSubtypes() {
    const ch = getChart();
    if (!ch) return [];
    const labels = ch.data?.labels || [];
    const data = ch.data?.datasets?.[0]?.data || [];
    const out = [];
    for (let i = 0; i < labels.length; i++) {
      const v = Number(data[i] || 0);
      if (v > 0) out.push(String(labels[i]));
    }
    return out;
  }

  function attach() {
    const btn = document.getElementById(BTN_ID);
    if (!btn || btn.dataset.attached === "1") return !!btn;

    btn.addEventListener("click", () => {
      const selected = getSelectedSubtypeFromState();
      if (selected && typeof window.openSubtypeAlarms === "function") {
        window.openSubtypeAlarms(selected);
        return;
      }
      const subs = getVisibleSubtypes();
      if (typeof window.openAlarmsForSubtypes === "function") {
        window.openAlarmsForSubtypes(subs);
      }
    });

    btn.dataset.attached = "1";
    return true;
  }

  if (attach()) return;
  const iv = setInterval(() => {
    tries++;
    if (attach() || tries >= MAX_TRIES) clearInterval(iv);
  }, 120);

  window.addEventListener("alarms-modal-ready", () => { attach(); }, { once: true });
})();
