(function () {
  const Q = (sel, root = document) => root.querySelector(sel);
  const QA = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function escapeHtml(s) {
    return String(s ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function sevClassFromText(sevText) {
    const s = String(sevText || '').toLowerCase();
    if (s.includes('confirm')) return 'sev-critical';
    if (s.includes('prob') || s.includes('likely')) return 'sev-medium';
    if (s.includes('info')) return 'sev-low';
    return 'sev-na';
  }

  function createModal(modalSelector) {
    const modal = Q(modalSelector);
    if (!modal) return null;

    function open() {
      document.body.classList.add('modal-open');
      modal.classList.remove('hidden');
      modal.setAttribute('aria-hidden', 'false');
    }

    function close() {
      modal.classList.add('hidden');
      modal.setAttribute('aria-hidden', 'true');

      const anyOpen = QA('.modal').some(m => !m.classList.contains('hidden'));
      if (!anyOpen) document.body.classList.remove('modal-open');
    }

    QA('[data-close]', modal).forEach(el => el.addEventListener('click', close));

    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });

    Q('.modal-card', modal)?.addEventListener('click', (e) => e.stopPropagation());

    return { modal, open, close };
  }

  const listModal = createModal('#anomalyListModal');
  const detailModal = createModal('#anomalyDetailModal');
  if (!listModal || !detailModal) return;

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!detailModal.modal.classList.contains('hidden')) detailModal.close();
    else if (!listModal.modal.classList.contains('hidden')) listModal.close();
  });

  const listBody = Q('#anomaly-list-body');
  const detailBody = Q('#anomaly-detail-body');
  const listTitle = Q('#anom-list-title');
  const detTitle = Q('#anom-detail-title');

  let lastPayload = [];

  function normalizeArrayPayload(parsed) {
    if (Array.isArray(parsed)) return parsed;
    if (parsed && Array.isArray(parsed.anomalies)) return parsed.anomalies;
    return [];
  }

  function renderDetail(anom) {
    if (!anom || typeof anom !== 'object') {
      if (detailBody) detailBody.innerHTML = `<div class="block"><p class="muted">No se pudo cargar el detalle.</p></div>`;
      return;
    }

    const sev = anom?.severity || '-';
    const sevClass = sevClassFromText(sev);

    const name = anom?.display_name || '-';
    const time = anom?.time_human || '-';
    const type = anom?.monitor_type || '-';
    const comments = Array.isArray(anom?.comments) ? anom.comments : [];

    if (detTitle) detTitle.textContent = `${sev} - ${name}`;

    let html = `
      <div class="block">
        <h4>Encabezado</h4>
        <ul class="stacked">
          <li><strong>Monitor:</strong> ${escapeHtml(name)}</li>
          <li><strong>Tipo:</strong> ${escapeHtml(type)}</li>
          <li><strong>Hora:</strong> <span class="mono">${escapeHtml(time)}</span></li>
          <li><strong>Severidad:</strong> <span class="pill ${sevClass}">${escapeHtml(sev)}</span></li>
        </ul>
      </div>
    `;

    if (comments.length > 0) {
      html += comments.map(c => {
        const attr = c.display_attr || c.formatted_attribute || c.attribute_name || 'Atributo';
        const loc = c.location_name ? ` (${escapeHtml(c.location_name)})` : '';
        const commentHtml = c.anomaly_comment || '<span class="muted">Sin detalle.</span>';

        return `
          <div class="block">
            <h4>${escapeHtml(attr)}${loc}</h4>
            <div class="muted" style="line-height:1.55;">
              ${commentHtml}
            </div>
          </div>
        `;
      }).join('');
    } else {
      html += `
        <div class="block">
          <h4>Detalle</h4>
          <p class="muted">Sin comentarios detallados para esta anomalia.</p>
        </div>
      `;
    }

    if (detailBody) detailBody.innerHTML = html;
  }

  function appendCurrentDateFilters(urlObj) {
    const params = new URLSearchParams(window.location.search);

    const period = params.get('period') || '3';
    const from = params.get('from');
    const to = params.get('to');

    urlObj.searchParams.set('period', period);

    if (from) urlObj.searchParams.set('from', from);
    else urlObj.searchParams.delete('from');

    if (to) urlObj.searchParams.set('to', to);
    else urlObj.searchParams.delete('to');
  }

  async function openListForMonitor(monitorId, monitorName) {
    if (listTitle) listTitle.textContent = `Anomalias - ${monitorName || 'Monitor'}`;
    if (listBody) listBody.innerHTML = `<div class="block"><p class="muted">Cargando</p></div>`;

    listModal.open();

    const url = new URL('/anomalias/listado/', window.location.origin);
    url.searchParams.set('monitor_id', monitorId);
    if (monitorName) url.searchParams.set('monitor_name', monitorName);

    appendCurrentDateFilters(url);

    const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'fetch' } });
    const html = await res.text();
    if (listBody) listBody.innerHTML = html;

    const script = Q('#anomaly-json', listBody);

    let parsed = [];
    try {
      parsed = script ? JSON.parse(script.textContent || '[]') : [];
    } catch {
      parsed = [];
    }

    lastPayload = normalizeArrayPayload(parsed);

    const table = Q('#tbl-anomaly-list', listBody);
    if (!table) return;

    QA('tbody tr.anom-row', table).forEach(tr => {
      tr.addEventListener('click', () => {
        const idx = Number(tr.dataset.idx);
        const anom = lastPayload.find(x => Number(x?.idx) === idx);
        renderDetail(anom);
        detailModal.open();
      });
    });
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-anom-open');
    if (!btn) return;

    const monitorId = btn.getAttribute('data-monitor-id')
      || btn.closest('tr')?.getAttribute('data-monitor-id')
      || btn.closest('tr')?.dataset?.monitorId;

    const monitorName = btn.getAttribute('data-monitor-name')
      || btn.closest('tr')?.getAttribute('data-monitor-name')
      || btn.closest('tr')?.dataset?.monitorName
      || '';

    if (!monitorId) return;

    openListForMonitor(monitorId, monitorName).catch(() => {
      if (listBody) listBody.innerHTML = `
        <div class="block">
          <h4>Error</h4>
          <p class="muted">No se pudo cargar el listado de anomalias.</p>
        </div>
      `;
    });
  });
})();
