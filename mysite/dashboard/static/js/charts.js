const trendLabels = JSON.parse(document.getElementById('trend-labels').textContent);
const trendData = JSON.parse(document.getElementById('trend-data').textContent);
const severityTrends = JSON.parse(document.getElementById('severity-trends').textContent);
const severityCounts = JSON.parse(document.getElementById('severity-counts').textContent);
const deviceCounts = JSON.parse(document.getElementById('device-counts').textContent);
const actionCounts = JSON.parse(document.getElementById('action-counts').textContent);

// Función de color
function getColorForSeverity(sev, opacity=1) {
  const mapping = {
    'Low': `rgba(46, 204, 113, ${opacity})`,
    'Medium': `rgba(241, 196, 15, ${opacity})`,
    'High': `rgba(231, 76, 60, ${opacity})`,
  };
  return mapping[sev] || `rgba(100,100,100,${opacity})`;
}

// --- Trend line ---
const trendCtx = document.getElementById('trendChart').getContext('2d');
const datasets = [{
  label: 'Total Alarmas',
  data: trendData,
  borderColor: 'blue',
  backgroundColor: 'rgba(0, 0, 255, 0.2)',
  fill: true,
  tension: 0.3,
}];

for (const [sev, obj] of Object.entries(severityTrends)) {
  datasets.push({
    label: sev,
    data: obj.data,
    borderColor: getColorForSeverity(sev),
    backgroundColor: getColorForSeverity(sev, 0.4),
    fill: true,
    tension: 0.3,
  });
}

new Chart(trendCtx, {
  type: 'line',
  data: { labels: trendLabels, datasets },
  options: { scales: { y: { beginAtZero: true } }, interaction: { mode: 'index', intersect: false } }
});

// --- Donut ---
new Chart(document.getElementById('severityDonut'), {
  type: 'doughnut',
  data: {
    labels: severityCounts.map(s => s.severity),
    datasets: [{ data: severityCounts.map(s => s.total), backgroundColor: ['#2ecc71','#f1c40f','#e74c3c'] }]
  }
});

// --- Dispositivos ---
new Chart(document.getElementById('deviceBar'), {
  type: 'bar',
  data: {
    labels: deviceCounts.map(d => d.msg_device_name),
    datasets: [{ label: 'Alarmas', data: deviceCounts.map(d => d.total), backgroundColor: 'rgba(54, 162, 235, 0.5)' }]
  },
  options: { indexAxis: 'y', scales: { x: { beginAtZero: true } } }
});

// --- Acciones ---
new Chart(document.getElementById('actionBar'), {
  type: 'bar',
  data: {
    labels: actionCounts.map(a => a.action),
    datasets: [{ label: 'Frecuencia', data: actionCounts.map(a => a.total), backgroundColor: 'rgba(153, 102, 255, 0.5)' }]
  },
  options: { scales: { y: { beginAtZero: true } } }
});
