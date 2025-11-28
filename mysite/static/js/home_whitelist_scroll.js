// static/js/home_whitelist_scroll.js

document.addEventListener('DOMContentLoaded', function () {
  const wrapper = document.querySelector('.home-whitelist-table-wrapper');
  if (!wrapper) return;

  const tbody = wrapper.querySelector('tbody');
  const thead = wrapper.querySelector('thead');
  if (!tbody) return;

  const rows = tbody.querySelectorAll('tr');
  if (rows.length <= 20) {
    // Menos o igual a 20 filas: no limitamos alto, sin scroll interno
    return;
  }

  // Altura de una fila (aprox)
  const firstRow = rows[0];
  const rowRect = firstRow.getBoundingClientRect();
  const rowHeight = rowRect.height || 24; // fallback por si no mide bien

  // Altura del header
  let headerHeight = 0;
  if (thead) {
    const headRect = thead.getBoundingClientRect();
    headerHeight = headRect.height || 28;
  }

  // Altura para ~20 filas + header + pequeño margen
  const visibleRows = 20;
  const extraPadding = 12; // margen extra
  const maxHeight = Math.round(visibleRows * rowHeight + headerHeight + extraPadding);

  // Aplicamos estilos inline al wrapper (manda sobre el CSS externo)
  wrapper.style.maxHeight = maxHeight + 'px';
  wrapper.style.overflowY = 'auto';
  wrapper.style.overflowX = 'auto';
  wrapper.style.display = 'block';

  // Si quieres debug visual, descomenta:
  // wrapper.style.border = '1px solid red';
});
