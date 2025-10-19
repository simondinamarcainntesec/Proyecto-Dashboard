(function(){
  // ===== Helpers =====
  const $ = (sel) => document.querySelector(sel);
  function readJSON(id){
    const el = document.getElementById(id);
    try { return el ? JSON.parse(el.textContent) : null; }
    catch(e){ console.error("JSON inválido en", id, e); return null; }
  }
  const norm = (s) => String(s ?? 'N/A').trim().toLowerCase();

  // ----- Alias ACCIONES (0/1, booleanos y sinónimos) -> etiquetas bonitas
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

  // NUEVOS datasets
  const trendByActionRaw  = readJSON('trend-by-action') || {};
  const deviceByActionRaw = readJSON('device-counts-by-action') || {};

  // Normalizar claves de acción para mapear contra actionFilter (que usa norm())
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

  // Acciones (totales y por severidad) normalizadas
  const actionCounts      = normalizeMapValues(actionCountsRaw);
  const actionBySev       = {};
  for (const [sev, m] of Object.entries(actionBySevRaw || {})){
    actionBySev[sev] = normalizeMapValues(m || {});
  }

  // Severidades
  function normalizeSeverityCounts(raw){
    if (!raw) return {};
    if (Array.isArray(raw)){
      const out = {};
      raw.forEach(x => { if (x && x.name != null) out[String(x.name).trim()] = Number(x.value || 0); });
      return out;
    }
    if (typeof raw === 'object'){
      return Object.fromEntries(Object.entries(raw).map(([k,v]) => [String(k).trim(), Number(v||0)]));
    }
    return {};
  }
  let severityCounts = normalizeSeverityCounts(severityCountsRaw);
  if (!severityCounts || Object.keys(severityCounts).length === 0){
    const derived = {};
    Object.keys(severityTrendsMap).forEach(sev => {
      const arr = (severityTrendsMap[sev] && severityTrendsMap[sev].data) || [];
      derived[String(sev).trim()] = arr.reduce((a,b)=>a+(Number(b)||0), 0);
    });
    severityCounts = derived;
  }

  // ===== Filtros =====
  let severityFilter = "";
  let deviceFilter   = "";
  let actionFilter   = ""; // normalizado: "blocked", "open", ...

  // ===== THEME OSCURO (ALTO CONTRASTE) =====
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

  // Paleta (Okabe–Ito adaptada)
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

  // ===== Derivados =====
  function severityCountsForDevice(device){
    const out = {};
    const bySev = readJSON('device-counts-by-severity') || {};
    Object.keys(bySev).forEach(sev => {
      const m = bySev[sev] || {};
      out[String(sev).trim()] = Number(m[device] || 0);
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

  function calcKpis(){
    let counts = severityCounts;
    if (deviceFilter) counts = severityCountsForDevice(deviceFilter);
    if (actionFilter) counts = severityCountsForAction(actionFilter);
    const total = Object.values(counts).reduce((a,b)=>a+(Number(b)||0),0);
    const high  = (counts['high']||0) + (counts['critical']||0);
    const devices = deviceFilter ? 1 : Object.keys(deviceCountsAll).length;
    return { total, high, devices };
  }

  function calcDonut(){
    let counts = severityCounts;
    if (deviceFilter) counts = severityCountsForDevice(deviceFilter);
    if (actionFilter) counts = severityCountsForAction(actionFilter);
    const labels = Object.keys(counts);
    const data   = labels.map(k => Number(counts[k]||0));
    const colors = labels.map(k => !severityFilter || k===severityFilter ? colorFor(k) : 'rgba(255,255,255,0.18)');
    return {labels, data, colors};
  }

  // === TENDENCIAS: ahora soporta actionFilter y deviceFilter ===
  function trendDataForCurrentFilter(){
    // 1) Por DISPOSITIVO (si hay)
    if (deviceFilter && trendByDevice[deviceFilter]){
      return {
        labels: trendLabels,
        datasets: [{
          label: deviceFilter,
          data: trendByDevice[deviceFilter],
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

    // 2) Por ACCIÓN (nuevo)
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
          pointBackgroundColor: '#8B5CF6',
          pointBorderColor: '#8B5CF6',
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35
        }]
      };
    }

    // 3) Por SEVERIDAD (default)
    const datasets = Object.keys(severityTrendsMap).map(sev => {
      const sevKey = String(sev).trim();
      const hidden = (severityFilter && sevKey !== severityFilter);
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

  // === TABLA: ahora soporta actionFilter con deviceByAction ===
  function deviceRowsForCurrentFilter(){
    if (actionFilter && deviceByAction[actionFilter]){
      const m = deviceByAction[actionFilter];
      return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,10);
    }
    const bySev = readJSON('device-counts-by-severity') || {};
    if (severityFilter && bySev[severityFilter]){
      const m = bySev[severityFilter];
      return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,10);
    }
    return Object.entries(deviceCountsAll).sort((a,b)=>b[1]-a[1]).slice(0,10);
  }

  // Acciones visibles con alias
  function actionDataForCurrentFilter(){
    let m = actionCounts;
    if (severityFilter && actionBySev[severityFilter]) m = actionBySev[severityFilter];
    const keys   = Object.keys(m);                 // normalizadas
    const labels = keys.map(k => prettyActionLabel(k)); // visibles
    const data   = keys.map(k => Number(m[k]||0));
    return {labels, data, keys};
  }

  // ===== Render =====
  let trendChart, donutChart, actionBarChart;

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
      animation: { duration: 240 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: TXT },
          onClick: (e, item) => {
            const sev = String(item.text).trim();
            deviceFilter = ""; actionFilter = "";
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
    const {labels, data, colors} = calcDonut();
    const opts = {
      cutout: '62%',
      plugins: { legend: { position: 'top', labels: { color: TXT } }, tooltip: { enabled: true } }
    };
    if (!window.donutChart){
      window.donutChart = new Chart(ctx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data, backgroundColor: colors, borderColor: '#e5e7eb', borderWidth: 2, hoverOffset: 8 }] },
        options: opts
      });
      ctx.canvas.onclick = (evt)=>{
        const el = window.donutChart.getElementsAtEventForMode(evt,'nearest',{intersect:true},true);
        if (!el.length) return;
        const idx = el[0].index;
        const sev = String(labels[idx]).trim();
        deviceFilter = ""; actionFilter = "";
        severityFilter = (severityFilter === sev) ? "" : sev;
        updateAll();
      };
    } else {
      window.donutChart.data.labels = labels;
      window.donutChart.data.datasets[0].data = data;
      window.donutChart.data.datasets[0].backgroundColor = colors;
      window.donutChart.options = opts;
      window.donutChart.update();
    }
  }

  function renderDeviceTable(){
    const tbody = document.getElementById('device-table-body');
    const rows = deviceRowsForCurrentFilter();
    tbody.innerHTML = rows.map(([dev, c])=>{
      const active = (deviceFilter === dev) ? ' is-active' : '';
      return `
        <tr class="row-device${active}" data-device="${dev}">
          <td><span class="cell-device">${dev}</span></td>
          <td class="is-right"><span class="pill pill-count">${c}</span></td>
        </tr>
      `;
    }).join('');
    tbody.querySelectorAll('tr').forEach(tr=>{
      tr.addEventListener('click', () => {
        const dev = tr.getAttribute('data-device');
        deviceFilter = (deviceFilter === dev) ? "" : dev;
        severityFilter = ""; actionFilter = "";
        updateAll();
      });
    });
  }

  function renderActionBar(){
    const ctx = document.getElementById('actionBar').getContext('2d');
    const {labels, data, keys} = actionDataForCurrentFilter();
    const opts = {
      indexAxis: 'y',
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
        const key = keys[idx]; // normalizada
        actionFilter = (actionFilter === key) ? "" : key;
        severityFilter = ""; deviceFilter = "";
        updateAll();
      };
    } else {
      actionBarChart.data.labels = labels;
      actionBarChart.data.datasets[0].data = data;
      actionBarChart.options = opts;
      actionBarChart.update();
    }
  }

  function updateAll(){
    renderKPIs();
    renderTrend();
    renderDonut();
    renderDeviceTable();
    renderActionBar();
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
