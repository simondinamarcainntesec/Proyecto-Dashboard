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

    const allPeriods = params.getAll("period").filter(Boolean);
    const period = (allPeriods.length ? allPeriods[allPeriods.length - 1] : (params.get("period") || "3"));

    const from = params.get("from");
    const to = params.get("to");

    urlObj.searchParams.delete("period");
    urlObj.searchParams.set("period", period);

    if (from) urlObj.searchParams.set("from", from);
    else urlObj.searchParams.delete("from");

    if (to) urlObj.searchParams.set("to", to);
    else urlObj.searchParams.delete("to");
  }


  // ===== Loader tipo "Realtime" (fila en tabla) =====
  function renderListLoading() {
    return `
      <div class="block">
        <h4>Listado</h4>
        <div class="table-wrap">
          <table class="tbl" id="tbl-anomaly-list">
            <thead>
              <tr>
                <th class="nowrap">Máquina / Monitor</th>
                <th class="nowrap">Fecha</th>
                <th class="nowrap">Hora</th>
                <th class="nowrap">Severidad</th>
              </tr>
            </thead>
            <tbody>
              <tr class="loading-row">
                <td colspan="4">
                  <div class="ao-loading">
                    <div class="ao-spinner" aria-hidden="true"></div>
                    <span>Cargando datos...</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="muted" style="padding-top:.45rem">
          * Clic en una fila para ver el detalle completo.
        </div>
      </div>
    `;
  }

  // Fecha/Hora con SEGUNDOS (HH:MM:SS)
  function splitDateTime(raw) {
    const s = String(raw || '').trim();
    // 2025-12-19T14:33:58-0300  | 2025-12-19 14:33:58  | 2025-12-19T14:33:58
    const m = s.match(/^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$/);
    if (m) return { date: m[1], time: m[2], full: s };

    // fallback si viene sin segundos: 14:33 -> 14:33:00
    const m2 = s.match(/^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$/);
    if (m2) return { date: m2[1], time: `${m2[2]}:00`, full: s };

    return { date: s || '—', time: '—', full: s || '—' };
  }

  function ensureDateTimeColumns(root) {
    const table = Q('#tbl-anomaly-list', root);
    if (!table) return;

    if (table.dataset.dtSplit === '1') return;
    table.dataset.dtSplit = '1';

    const theadRow = Q('thead tr', table);
    if (theadRow) {
      const ths = QA('th', theadRow);

      // tabla original: [Monitor, Hora, Severidad]
      if (ths.length >= 3) {
        ths[1].textContent = 'Fecha';

        const thHora = document.createElement('th');
        thHora.className = 'nowrap';
        thHora.textContent = 'Hora';
        ths[1].after(thHora);
      }
    }

    QA('tbody tr.anom-row', table).forEach(tr => {
      const tds = QA('td', tr);
      if (tds.length < 3) return;

      const tdTime = tds[1];
      const raw = tdTime.textContent.trim();
      const parts = splitDateTime(raw);

      tdTime.textContent = parts.date;
      tdTime.classList.add('mono', 'nowrap', 'td-date');
      tdTime.setAttribute('title', parts.full);

      const tdHora = document.createElement('td');
      tdHora.className = 'mono nowrap td-time';
      tdHora.textContent = parts.time;
      tdHora.setAttribute('title', parts.full);

      tdTime.after(tdHora);
    });

    // fila "sin anomalías": colspan 3 -> 4
    QA('tbody tr', table).forEach(tr => {
      if (tr.classList.contains('anom-row')) return;
      const onlyCell = Q('td[colspan="3"]', tr);
      if (onlyCell) onlyCell.setAttribute('colspan', '4');
    });
  }

  async function openListForMonitor(monitorId, monitorName) {
    if (listTitle) listTitle.textContent = `Anomalias - ${monitorName || 'Monitor'}`;

    // Loader tipo Realtime
    if (listBody) listBody.innerHTML = renderListLoading();

    listModal.open();

    const url = new URL('/anomalias/listado/', window.location.origin);
    url.searchParams.set('monitor_id', monitorId);
    if (monitorName) url.searchParams.set('monitor_name', monitorName);

    appendCurrentDateFilters(url);

    const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'fetch' } });
    const html = await res.text();

    if (listBody) listBody.innerHTML = html;

    // split Fecha/Hora (con segundos)
    ensureDateTimeColumns(listBody);

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
