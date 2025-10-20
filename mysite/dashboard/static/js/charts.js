(function(){
  // ===== Helpers =====
  const $ = (sel) => document.querySelector(sel);
  function readJSON(id){
    const el = document.getElementById(id);
    try { return el ? JSON.parse(el.textContent) : null; }
    catch(e){ console.error("JSON inválido en", id, e); return null; }
  }
  const norm = (s) => String(s ?? 'N/A').trim().toLowerCase();

  // Etiqueta segura para mostrar en UI
  const safeLabel = (s) => {
    const t = (s ?? '').toString().trim();
    return t ? t : 'N/A';
  };

  // Normaliza objeto de conteos para colapsar claves vacías en 'N/A'
  function normalizeCountsLabels(counts){
    const out = {};
    Object.entries(counts || {}).forEach(([k,v])=>{
      const kk = safeLabel(k);
      out[kk] = (out[kk] || 0) + Number(v || 0);
    });
    return out;
  }

  // === NUEVO: buscar clave case-insensitive y devolver la real ===
  function findKeyCI(obj, target){
    if (!obj) return null;
    const t = String(target ?? '').trim().toLowerCase();
    if (!t) return null;
    for (const k of Object.keys(obj)){
      if (String(k).trim().toLowerCase() === t) return k;
    }
    return null;
  }

  // ----- Alias ACCIONES -----
  const ACTION_ALIASES = {
    '0':'Open','1':'Blocked','false':'Open','true':'Blocked',
    'allow':'Open','allowed':'Open','deny':'Blocked','denied':'Blocked',
    'block':'Blocked','blocked':'Blocked','resolved':'Resolved','closed':'Resolved','2':'Resolved'
  };
  const prettyActionLabel = (value)=>{
    const k = norm(value);
    if (ACTION_ALIASES[k]) return ACTION_ALIASES[k];
    const raw = String(value ?? '').trim();
    return raw ? raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase() : 'N/A';
  };

  const normalizeMapValues = (obj)=>{
    const map = {};
    if (obj && typeof obj === 'object'){
      for (const [k,v] of Object.entries(obj)) map[norm(k)] = Number(v || 0);
    }
    return map;
  };

  // ===== Datos del template =====
  const trendLabels       = readJSON('trend-labels') || [];
  const severityTrendsMap = readJSON('severity-trends') || {};
  const trendByDevice     = readJSON('trend-by-device') || {};
  const severityCountsRaw = readJSON('severity-counts') || {};
  const deviceCountsAll   = readJSON('device-counts') || {};
  const actionCountsRaw   = readJSON('action-counts') || {};
  const actionBySevRaw    = readJSON('action-counts-by-severity') || {};
  const actionByDevRaw    = readJSON('action-counts-by-device') || {};

  const trendByActionRaw  = readJSON('trend-by-action') || {};
  const deviceByActionRaw = readJSON('device-counts-by-action') || {};

  // === Datos por hora (rango general) ===
  const hourLabels             = readJSON('hour-labels') || [];      // ["00".."23"]
  const hourData               = readJSON('hour-data') || [];
  const sevByHourRaw           = readJSON('severity-counts-by-hour') || {};
  const devByHourRaw           = readJSON('device-counts-by-hour') || {};
  const actByHourRaw           = readJSON('action-counts-by-hour') || {};
  const trendLabelsHour        = readJSON('trend-labels-hour') || []; // días
  const trendByHourRaw         = readJSON('trend-by-hour') || {};     // { "00": [...] }

  // === msg_severity datasets (tal cual del server/BD) ===
  const msgSeverityCountsRaw           = readJSON('msg-severity-counts') || {};
  const deviceByMsgSeverityRaw         = readJSON('device-counts-by-msg-severity') || {};
  const actionByMsgSeverityRaw         = readJSON('action-counts-by-msg-severity') || {};
  const severityByMsgSeverityRaw       = readJSON('severity-counts-by-msg-severity') || {};
  const msgSeverityByHourRaw           = readJSON('msg-severity-counts-by-hour') || {};
  const trendByMsgSeverityRaw          = readJSON('trend-by-msg-severity') || {};

  // === Mapa completo por severidad->device (sin top_n) ===
  const deviceBySevFullRaw = readJSON('device-counts-by-severity-full') || {};

  // Normalizaciones
  const trendByAction = {};
  Object.entries(trendByActionRaw).forEach(([k, arr])=>{
    trendByAction[norm(k)] = Array.isArray(arr) ? arr : [];
  });

  const deviceByAction = {};
  Object.entries(deviceByActionRaw).forEach(([k, m])=>{
    const inner = {};
    Object.entries(m || {}).forEach(([dev, val])=> inner[dev] = Number(val||0));
    deviceByAction[norm(k)] = inner;
  });

  const actionBySev = {};
  for (const [sev, m] of Object.entries(actionBySevRaw || {})){
    actionBySev[sev] = normalizeMapValues(m || {});
  }
  const actionByDev = {};
  for (const [dev, m] of Object.entries(actionByDevRaw || {})){
    actionByDev[dev] = normalizeMapValues(m || {});
  }

  const actByHourNorm = {};
  for (const [h, map] of Object.entries(actByHourRaw)){
    actByHourNorm[h] = normalizeMapValues(map || {});
  }

  // Canonicalización de nombres de dispositivo (case/espacios)
  const deviceKeys = Object.keys(deviceCountsAll || {});
  function canonicalDeviceKey(input){
    if (!input) return input;
    const needle = String(input).trim().toLowerCase();
    for (const k of deviceKeys){ if (k === input) return k; }
    for (const k of deviceKeys){ if (String(k).trim().toLowerCase() === needle) return k; }
    for (const sev of Object.keys(deviceBySevFullRaw||{})){
      for (const dk of Object.keys(deviceBySevFullRaw[sev]||{})){
        if (String(dk).trim().toLowerCase() === needle) return dk;
      }
    }
    return input; // fallback
  }

  let severityCounts = (() => {
    if (!severityCountsRaw) return {};
    if (Array.isArray(severityCountsRaw)){
      const out = {};
      severityCountsRaw.forEach(x => {
        if (x && x.name != null) out[String(x.name).trim()] = Number(x.value || 0);
      });
      return out;
    }
    if (typeof severityCountsRaw === 'object'){
      return Object.fromEntries(Object.entries(severityCountsRaw).map(([k,v]) => [String(k).trim(), Number(v||0)]));
    }
    return {};
  })();

  // ===== Filtros globales =====
  let severityFilter = "";
  let deviceFilter   = "";
  let actionFilter   = ""; // normalizado
  let hourFilter     = ""; // "00".."23"
  let msgSeverityFilter = ""; // clave tal cual BD (sin normalizar)

  // ===== THEME =====
  const TXT  = '#E5E7EB';
  const GRID = 'rgba(229,231,235,0.14)';
  const AXIS = TXT;
  const EMPH = '#FFFFFF';

  const fontFamily = "'Inter', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
  Chart.defaults.font.family = fontFamily;
  Chart.defaults.color = TXT;
  Chart.defaults.font.size = 15;
  Chart.defaults.font.weight = '700';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
  Chart.defaults.plugins.legend.labels.font = { size: 15, weight: '700' };
  Chart.defaults.plugins.legend.labels.color = TXT;
  Chart.defaults.plugins.tooltip.titleFont = { size: 15, family: fontFamily, weight: '700' };
  Chart.defaults.plugins.tooltip.bodyFont  = { size: 15, family: fontFamily, weight: '700' };
  Chart.defaults.plugins.tooltip.titleColor = EMPH;
  Chart.defaults.plugins.tooltip.bodyColor  = EMPH;
  Chart.defaults.scales = {
    ...Chart.defaults.scales,
    linear:   { ticks: { color: AXIS, font: { size: 14, weight: '700' } }, grid: { color: GRID } },
    category: { ticks: { color: AXIS, font: { size: 14, weight: '700' } }, grid: { color: GRID } }
  };
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.devicePixelRatio = Math.max(1.5, window.devicePixelRatio || 1);

  // Paleta general (para severity clásica)
  const palette = {
    critical: '#FF6B6B',
    high:     '#F59E0B',
    medium:   '#F0E442',
    low:      '#10B981',
    info:     '#60A5FA',
    warning:  '#CC79A7',
    'n/a':    '#A0A3A8',
    default:  '#8B5CF6'
  };
  const colorFor = (sev) => palette[(String(sev||'').toLowerCase())] || palette.default;

  // Paleta específica para msg_severity bar
  function colorForMsgSeverity(label){
    const k = String(label || '').trim().toLowerCase();
    if (k === 'critical') return '#FF6B6B'; // rojo
    if (k === 'high')     return '#F59E0B'; // naranja
    if (k === 'medium')   return '#F0E442'; // amarillo
    if (k === 'n/a')      return '#A0A3A8'; // gris
    return '#8B5CF6'; // default
  }

  // ===== Derivados para recalcular datasets con filtros =====
  function severityCountsForDevice(device){
    const dev = canonicalDeviceKey(device);
    const out = {};
    const bySevFull = deviceBySevFullRaw || {};
    Object.keys(bySevFull).forEach(sev => {
      const m = bySevFull[sev] || {};
      out[String(sev).trim()] = Number(m[dev] || 0);
    });
    return out;
  }
  function severityCountsForAction(actionKey){
    const out = {};
    Object.keys(actionBySev).forEach(sev => {
      const m = actionBySev[sev] || {};
      out[String(sev).trim()] = Number(m[actionKey] || 0);
    });
    return out;
  }
  function severityCountsForHour(hour){
    const m = sevByHourRaw && sevByHourRaw[hour] ? sevByHourRaw[hour] : {};
    const out = {};
    Object.keys(m).forEach(sev => out[String(sev).trim()] = Number(m[sev] || 0));
    return out;
  }
  function severityCountsForMsgSeverity(msg){
    const m = severityByMsgSeverityRaw && severityByMsgSeverityRaw[msg] ? severityByMsgSeverityRaw[msg] : {};
    const out = {};
    Object.keys(m).forEach(sev => out[String(sev).trim()] = Number(m[sev] || 0));
    return out;
  }

  // === Centralización de conteos ===
  function applySeveritySlice(counts){
    if (!severityFilter) return counts;
    // << NUEVO: usa búsqueda case-insensitive para encontrar la clave real
    const realKey = findKeyCI(counts, severityFilter) || severityFilter;
    const v = Number(counts[realKey] || 0);
    return { [realKey]: v };
  }

  function getActiveCounts() {
    let base =
      (msgSeverityFilter && severityCountsForMsgSeverity(msgSeverityFilter)) ||
      (deviceFilter       && severityCountsForDevice(deviceFilter))         ||
      (actionFilter       && severityCountsForAction(actionFilter))         ||
      (hourFilter         && severityCountsForHour(hourFilter))             ||
      severityCounts;

    base = normalizeCountsLabels(base);
    base = applySeveritySlice(base);

    if (!base || Object.keys(base).length === 0){
      return { 'N/A': 0 };
    }
    return base;
  }

  // === KPI y Donut ===
  function calcKpis(){
    const counts = getActiveCounts();
    let total = Object.values(counts).reduce((a,b)=>a+(Number(b)||0),0);

    if (deviceFilter && !severityFilter) {
      const dk = canonicalDeviceKey(deviceFilter);
      if (deviceCountsAll && Object.prototype.hasOwnProperty.call(deviceCountsAll, dk)) {
        total = Number(deviceCountsAll[dk] || 0);
      }
    }
    const high  = (counts['high']||0) + (counts['critical']||0);
    const devices = deviceFilter ? 1 : Object.keys(deviceCountsAll).length;
    return { total, high, devices };
  }

  // Donut “a prueba de 0”
  function calcDonut(){
    const counts = getActiveCounts();
    const labels = Object.keys(counts);
    const data   = labels.map(k => Number(counts[k]||0));
    const colors = labels.map(k => (!severityFilter || String(k).trim().toLowerCase()===String(severityFilter).trim().toLowerCase())
      ? colorFor(k) : 'rgba(255,255,255,0.18)');

    const total = data.reduce((a,b)=>a+(Number(b)||0),0);
    if (labels.length === 0 || total === 0){
      return {
        labels,
        data,
        colors,
        displayLabels: ['N/A'],
        displayData:   [1],
        displayColors: ['#A0A3A8'],
        isZeroSafemode: true
      };
    }
    return {
      labels,
      data,
      colors,
      displayLabels: labels,
      displayData:   data,
      displayColors: colors,
      isZeroSafemode: false
    };
  }

  // === TENDENCIAS (izquierda) ===
  function trendDataForCurrentFilter(){
    if (deviceFilter && trendByDevice[canonicalDeviceKey(deviceFilter)]){
      const dk = canonicalDeviceKey(deviceFilter);
      return {
        labels: trendLabels,
        datasets: [{
          label: dk,
          data: trendByDevice[dk],
          borderColor: '#60A5FA',
          backgroundColor: 'rgba(96,165,250,0.18)',
          borderWidth: 3,
          pointRadius: 3,
          pointBackgroundColor: '#60A5FA',
          pointBorderColor: '#60A5FA',
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35
        }]
      };
    }
    if (actionFilter && trendByAction[actionFilter]){
      return {
        labels: trendLabels,
        datasets: [{
          label: `Acción: ${prettyActionLabel(actionFilter)}`,
          data: trendByAction[actionFilter],
          borderColor: '#8B5CF6',
          backgroundColor: 'rgba(139,92,246,0.20)',
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35
        }]
      };
    }
    if (msgSeverityFilter && trendByMsgSeverityRaw[msgSeverityFilter]){
      return {
        labels: trendLabels,
        datasets: [{
          label: `Msg severity: ${msgSeverityFilter}`,
          data: trendByMsgSeverityRaw[msgSeverityFilter],
          borderColor: '#F43F5E',
          backgroundColor: 'rgba(244,63,94,0.20)',
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35
        }]
      };
    }
    if (hourFilter && trendByHourRaw[hourFilter]){
      return {
        labels: trendLabelsHour,
        datasets: [{
          label: `Hora ${hourFilter}:00`,
          data: trendByHourRaw[hourFilter],
          borderColor: '#22C55E',
          backgroundColor: 'rgba(34,197,94,0.20)',
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35
        }]
      };
    }
    const datasets = Object.keys(severityTrendsMap).map(sev => {
      const sevKey = String(sev).trim();
      const hidden = (severityFilter && sevKey.toLowerCase() !== String(severityFilter).trim().toLowerCase());
      const base   = colorFor(sevKey);
      return {
        label: sevKey,
        data: (severityTrendsMap[sev] && severityTrendsMap[sev].data) || new Array(trendLabels.length).fill(0),
        borderColor: base,
        backgroundColor: base + '33',
        pointBackgroundColor: base,
        pointBorderColor: base,
        borderWidth: 3,
        pointRadius: hidden ? 0 : 3,
        pointHoverRadius: hidden ? 0 : 5,
        fill: true,
        tension: 0.35,
        hidden,
      };
    });
    return { labels: trendLabels, datasets };
  }

  // Tabla de dispositivos (abajo)
  function deviceRowsForCurrentFilter(){
    if (hourFilter && devByHourRaw[hourFilter]){
      const m = devByHourRaw[hourFilter];
      return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,10);
    }
    if (msgSeverityFilter && deviceByMsgSeverityRaw[msgSeverityFilter]){
      const m = deviceByMsgSeverityRaw[msgSeverityFilter] || {};
      return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,10);
    }
    const bySev = readJSON('device-counts-by-severity') || {};
    if (severityFilter && bySev[severityFilter]){
      const m = bySev[severityFilter];
      return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,10);
    }
    return Object.entries(deviceCountsAll).sort((a,b)=>b[1]-a[1]).slice(0,10);
  }

  // Barra de acciones (derecha)
  function actionDataForCurrentFilter(){
    if (deviceFilter && actionByDev[canonicalDeviceKey(deviceFilter)]){
      const m = actionByDev[canonicalDeviceKey(deviceFilter)];
      const keys   = Object.keys(m);
      const labels = keys.map(k => prettyActionLabel(k));
      const data   = keys.map(k => Number(m[k]||0));
      return {labels, data, keys};
    }
    if (severityFilter){
      // << NUEVO: resolver la clave real por case-insensitive
      const sevKey = findKeyCI(actionBySev, severityFilter);
      if (sevKey && actionBySev[sevKey]){
        const m = actionBySev[sevKey];
        const keys   = Object.keys(m);
        const labels = keys.map(k => prettyActionLabel(k));
        const data   = keys.map(k => Number(m[k]||0));
        return {labels, data, keys};
      }
    }
    if (msgSeverityFilter && actionByMsgSeverityRaw[msgSeverityFilter]){
      const m = actionByMsgSeverityRaw[msgSeverityFilter];
      const keys   = Object.keys(m);
      const labels = keys.map(k => prettyActionLabel(k));
      const data   = keys.map(k => Number(m[k]||0));
      return {labels, data, keys};
    }
    if (hourFilter && actByHourNorm[hourFilter]){
      const m = actByHourNorm[hourFilter];
      const keys   = Object.keys(m);
      const labels = keys.map(k => prettyActionLabel(k));
      const data   = keys.map(k => Number(m[k]||0));
      return {labels, data, keys};
    }
    const m = normalizeMapValues(actionCountsRaw);
    const keys   = Object.keys(m);
    const labels = keys.map(k => prettyActionLabel(k));
    const data   = keys.map(k => Number(m[k]||0));
    return {labels, data, keys};
  }

  // === Datos para barra de msg_severity (Severity Alarm) ===
  function msgSeverityDataForCurrentFilter(){
    if (deviceFilter && deviceByMsgSeverityRaw){
      const devKey = canonicalDeviceKey(deviceFilter);
      const map = {};
      Object.entries(deviceByMsgSeverityRaw).forEach(([msg, perDev])=>{
        map[msg] = Number((perDev || {})[devKey] || 0);
      });
      const keys = Object.keys(map);
      const labels = keys;
      const data = keys.map(k => map[k]);
      const colors = keys.map(colorForMsgSeverity);
      return {labels, data, keys, colors};
    }
    if (severityFilter && severityByMsgSeverityRaw){
      const map = {};
      // intentar resolver la severidad real por case-insensitive
      const sevKey = findKeyCI(severityByMsgSeverityRaw[Object.keys(severityByMsgSeverityRaw)[0]] ? {} : {}, severityFilter) || severityFilter;
      Object.entries(severityByMsgSeverityRaw).forEach(([msg, perSev])=>{
        const k = findKeyCI(perSev, severityFilter) || severityFilter;
        map[msg] = Number((perSev || {})[k] || 0);
      });
      const keys = Object.keys(map);
      const labels = keys;
      const data = keys.map(k => map[k]);
      const colors = keys.map(colorForMsgSeverity);
      return {labels, data, keys, colors};
    }
    if (actionFilter && actionByMsgSeverityRaw){
      const map = {};
      Object.entries(actionByMsgSeverityRaw).forEach(([msg, perAct])=>{
        map[msg] = Number((perAct || {})[actionFilter] || 0);
      });
      const keys = Object.keys(map);
      const labels = keys;
      const data = keys.map(k => map[k]);
      const colors = keys.map(colorForMsgSeverity);
      return {labels, data, keys, colors};
    }
    if (hourFilter && msgSeverityByHourRaw && msgSeverityByHourRaw[hourFilter]){
      const m = msgSeverityByHourRaw[hourFilter] || {};
      const keys = Object.keys(m);
      const labels = keys;
      const data = keys.map(k => Number(m[k] || 0));
      const colors = keys.map(colorForMsgSeverity);
      return {labels, data, keys, colors};
    }
    const m = normalizeMapValues(msgSeverityCountsRaw);
    const keys   = Object.keys(m);
    const labels = keys;
    const data   = keys.map(k => Number(m[k]||0));
    const colors = keys.map(colorForMsgSeverity);
    return {labels, data, keys, colors};
  }

  // ===== Render =====
  let trendChart, donutChart, actionBarChart, hourlyChart, msgSeverityBarChart;

  function renderKPIs(){
    const { total, high, devices } = calcKpis();
    $('#kpi-total').textContent   = total;
    $('#kpi-high').textContent    = high;
    $('#kpi-devices').textContent = devices;
  }

  function renderTrend(){
    const ctx = document.getElementById('trendChart').getContext('2d');
    const conf = trendDataForCurrentFilter();
    const commonOpts = {
      animation: { duration: 600, easing: 'easeOutQuart' },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: TXT },
          onClick: (e, item) => {
            const sev = String(item.text).trim();
            deviceFilter = ""; actionFilter = ""; hourFilter = ""; msgSeverityFilter = "";
            severityFilter = (severityFilter === sev) ? "" : sev;
            updateAll();
          }
        },
        tooltip: { enabled: true }
      },
      scales: {
        x: { ticks: { color: AXIS }, grid: { color: GRID } },
        y: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } }
      }
    };
    if (!trendChart){
      trendChart = new Chart(ctx, { type: 'line', data: conf, options: commonOpts });
    } else {
      trendChart.data = conf;
      trendChart.options = commonOpts;
      trendChart.update();
    }
  }

  function renderDonut(){
    const ctx = document.getElementById('severityDonut').getContext('2d');
    const d = calcDonut();

    const chartData = {
      labels: d.displayLabels,
      datasets: [{
        data: d.displayData,
        backgroundColor: d.displayColors,
        borderColor: '#e5e7eb',
        borderWidth: 2,
        hoverOffset: 8
      }]
    };

    const opts = {
      cutout: '62%',
      animation: { duration: 600, easing: 'easeOutQuart' },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#E5E7EB',
            generateLabels: (chart) => {
              const items = Chart.defaults.plugins.legend.labels.generateLabels(chart);
              if (!d.isZeroSafemode) {
                return items.map(it => ({ ...it, text: safeLabel(it.text) }));
              }
              return items.map(it => ({ ...it, text: 'N/A (0)' }));
            }
          }
        },
        tooltip: {
          enabled: true,
          callbacks: {
            label: (ctx) => {
              if (d.isZeroSafemode) return 'N/A: 0';
              const label = safeLabel(ctx.label);
              const value = d.data[ctx.dataIndex] ?? 0;
              return `${label}: ${value}`;
            }
          }
        }
      }
    };

    if (!window.donutChart){
      window.donutChart = new Chart(ctx, { type: 'doughnut', data: chartData, options: opts });
      ctx.canvas.onclick = (evt)=>{
        const el = window.donutChart.getElementsAtEventForMode(evt,'nearest',{intersect:true},true);
        if (!el.length) return;
        if (d.isZeroSafemode) return;

        const idx = el[0].index;
        const sev = safeLabel(d.labels[idx]);
        deviceFilter = ""; actionFilter = ""; hourFilter = ""; msgSeverityFilter = "";
        severityFilter = (String(severityFilter).trim().toLowerCase() === String(sev).trim().toLowerCase()) ? "" : sev;
        updateAll();
      };
    } else {
      window.donutChart.data = chartData;
      window.donutChart.options = opts;
      window.donutChart.update();
    }
  }

  function renderDeviceTable(){
    const tbody = document.getElementById('device-table-body');
    const rows = deviceRowsForCurrentFilter();
    tbody.innerHTML = rows.map(([dev, c])=>{
      const active = (canonicalDeviceKey(deviceFilter) === dev) ? ' is-active' : '';
      return `
        <tr class="row-device${active}" data-device="${dev}">
          <td><span class="cell-device">${dev}</span></td>
          <td class="is-right"><span class="pill pill-count">${c}</span></td>
        </tr>
      `;
    }).join('');
    tbody.querySelectorAll('tr').forEach(tr=>{
      tr.addEventListener('click', () => {
        const raw = tr.getAttribute('data-device');
        const dev = canonicalDeviceKey(raw);
        deviceFilter = (canonicalDeviceKey(deviceFilter) === dev) ? "" : dev;
        severityFilter = ""; actionFilter = ""; hourFilter = ""; msgSeverityFilter = "";
        updateAll();
      });
    });
  }

  function renderActionBar(){
    const ctx = document.getElementById('actionBar').getContext('2d');
    const {labels, data, keys} = actionDataForCurrentFilter();
    const opts = {
      indexAxis: 'y',
      animation: { duration: 600, easing: 'easeOutQuart' },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: (items)=> items.map(i=>labels[i.dataIndex]) } }
      },
      scales: {
        x: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
        y: { ticks: { color: AXIS, callback: (v,i)=>labels[i] }, grid: { color: GRID } }
      }
    };
    if (!actionBarChart){
      actionBarChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label:'Acciones', data, borderWidth: 2, backgroundColor: '#8B5CF6', borderColor: '#e5e7eb' }] },
        options: opts
      });
      ctx.canvas.onclick = (evt)=>{
        const el = actionBarChart.getElementsAtEventForMode(evt,'nearest',{intersect:true},true);
        if (!el.length) return;
        const idx = el[0].index;
        const key = keys[idx];
        actionFilter = (actionFilter === key) ? "" : key;
        severityFilter = ""; deviceFilter = ""; hourFilter = ""; msgSeverityFilter = "";
        updateAll();
      };
    } else {
      actionBarChart.data.labels = labels;
      actionBarChart.data.datasets[0].data = data;
      actionBarChart.options = opts;
      actionBarChart.update();
    }
  }

  // === Barra msg_severity (Severity Alarm) con filtro cruzado + colores por etiqueta ===
  function renderMsgSeverityBar(){
    const el = document.getElementById('msgSeverityBar');
    if (!el) return;
    const ctx = el.getContext('2d');

    const {labels, data, keys, colors} = msgSeverityDataForCurrentFilter();

    const backgroundColors = labels.map(label => {
      if (msgSeverityFilter && label !== msgSeverityFilter)
        return 'rgba(255,255,255,0.18)';
      return colorForMsgSeverity(label);
    });

    const dataConf = {
      labels,
      datasets: [{
        label: 'Severity Alarm',
        data,
        borderWidth: 2,
        backgroundColor: backgroundColors,
        borderColor: '#e5e7eb'
      }]
    };

    const opts = {
      indexAxis: 'y',
      animation: { duration: 600, easing: 'easeOutQuart' },
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      scales: {
        x: { beginAtZero: true, ticks: { color: '#E5E7EB' }, grid: { color: 'rgba(229,231,235,0.14)' } },
        y: {
          type: 'category',
          ticks: { color: '#E5E7EB', callback: (v, i) => labels[i] },
          grid: { color: 'rgba(229,231,235,0.14)' }
        }
      }
    };

    if (!msgSeverityBarChart){
      msgSeverityBarChart = new Chart(ctx, { type: 'bar', data: dataConf, options: opts });
      ctx.canvas.onclick = (evt)=>{
        const elp = msgSeverityBarChart.getElementsAtEventForMode(evt,'nearest',{intersect:true},true);
        if (!elp.length) return;
        const idx = elp[0].index;
        const key = keys[idx];
        msgSeverityFilter = (msgSeverityFilter === key) ? "" : key;
        severityFilter = ""; deviceFilter = ""; actionFilter = ""; hourFilter = "";
        updateAll();
      };
    } else {
      msgSeverityBarChart.data = dataConf;
      msgSeverityBarChart.options = opts;
      msgSeverityBarChart.update();
    }
  }

  // === Gráfico por hora ===
  function renderHourly(){
    const el = document.getElementById('hourlyChart');
    if (!el) return;
    const ctx = el.getContext('2d');

    let series = hourData.slice();
    let label  = 'Alarmas (por hora, rango actual)';

    if (deviceFilter) {
      const dk = canonicalDeviceKey(deviceFilter);
      series = hourLabels.map(h => {
        const m = devByHourRaw[h] || {};
        return Number(m[dk] || 0);
      });
      label = `Alarmas por hora — Dispositivo: ${dk}`;
    } else if (severityFilter) {
      series = hourLabels.map(h => {
        const m = sevByHourRaw[h] || {};
        // resolver clave real case-insensitive para hour maps
        const hk = findKeyCI(m, severityFilter) || severityFilter;
        return Number((m[hk] || 0));
      });
      label = `Alarmas por hora — Severidad: ${severityFilter}`;
    } else if (actionFilter) {
      series = hourLabels.map(h => {
        const m = actByHourNorm[h] || {};
        return Number((m[actionFilter] || 0));
      });
      label = `Alarmas por hora — Acción: ${prettyActionLabel(actionFilter)}`;
    } else if (msgSeverityFilter) {
      series = hourLabels.map(h => {
        const m = msgSeverityByHourRaw[h] || {};
        return Number((m[msgSeverityFilter] || 0));
      });
      label = `Alarmas por hora — Msg Severity: ${msgSeverityFilter}`;
    }

    const data = {
      labels: hourLabels.map(h => `${h}:00`),
      datasets: [{
        label,
        data: series,
        borderWidth: 2,
        backgroundColor: '#22C55E',
        borderColor: '#e5e7eb'
      }]
    };

    const opts = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600, easing: 'easeOutQuart' },
      plugins: {
        legend: { display: false },
        tooltip: { enabled: true }
      },
      scales: {
        x: {
          ticks: { color: '#E5E7EB', autoSkip: false, maxRotation: 0, minRotation: 0 },
          grid: { color: 'rgba(229,231,235,0.14)' }
        },
        y: { beginAtZero: true, ticks: { color: '#E5E7EB' }, grid: { color: 'rgba(229,231,235,0.14)' } }
      }
    };

    if (!hourlyChart){
      hourlyChart = new Chart(ctx, { type: 'bar', data, options: opts });
      ctx.canvas.onclick = (evt)=>{
        const points = hourlyChart.getElementsAtEventForMode(evt,'nearest',{intersect:true},true);
        if (!points.length) return;
        const idx = points[0].index;
        const h = hourLabels[idx];
        hourFilter = (hourFilter === h) ? "" : h;
        severityFilter = ""; deviceFilter = ""; actionFilter = ""; msgSeverityFilter = "";
        updateAll();
      };
    } else {
      hourlyChart.data = data;
      hourlyChart.options = opts;
      hourlyChart.update();
    }
  }

  function updateAll(){
    renderKPIs();
    renderTrend();
    renderDonut();
    renderDeviceTable();
    renderActionBar();
    renderMsgSeverityBar();
    renderHourly();
  }

  // UX fechas + sort tabla
  function wireDateFilter(){
    const form = $('#date-filter'); if (!form) return;
    const from = form.querySelector('input[name="from"]');
    const to   = form.querySelector('input[name="to"]');
    if (from && to){
      from.addEventListener('change', ()=> { to.min = from.value || ''; });
      to.addEventListener('change',   ()=> { from.max = to.value || ''; });
      to.min = from.value || ''; from.max = to.value || '';
    }
  }
  function wireTableSort(){
    const table = document.getElementById('device-table'); if (!table) return;
    const tbody = table.querySelector('tbody');
    const ths   = table.querySelectorAll('thead th');
    ths.forEach((th, idx)=>{
      th.addEventListener('click', ()=>{
        const type = th.getAttribute('data-sort') || 'text';
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const asc  = !th.classList.contains('sort-asc');
        ths.forEach(t=>t.classList.remove('sort-asc','sort-desc'));
        th.classList.add(asc ? 'sort-asc' : 'sort-desc');
        rows.sort((a,b)=>{
          const av = a.children[idx].innerText.trim();
          const bv = b.children[idx].innerText.trim();
          if (type === 'number') return asc ? (Number(av)-Number(bv)) : (Number(bv)-Number(av));
          return asc ? av.localeCompare(bv) : bv.localeCompare(av);
        });
        tbody.innerHTML = ''; rows.forEach(r=>tbody.appendChild(r));
      });
    });
  }

  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', () => { wireDateFilter(); wireTableSort(); updateAll(); });
  } else {
    wireDateFilter(); wireTableSort(); updateAll();
  }
})();
