// /static/js/soar/charts/devices-table.js
import { getState, actions } from "/static/js/soar/state.js";
import { deviceRowsForCurrentFilter } from "/static/js/soar/selectors.js";
import { ensureHeaderButton, collectAlarmIdsForCurrentFilter, showAlarms } from "/static/js/soar/helpers/alarms-helper.js";

const norm = (s) => String(s ?? "").trim().toLowerCase();

export function renderDeviceTable() {
  const tbody = document.getElementById("device-table-body");
  if (!tbody) return;

  const st   = getState();
  const rows = deviceRowsForCurrentFilter(); // [[device, count], ...]

  // === Pintar filas ===
  const activeKey = norm(st.deviceFilter || "");
  const html = rows.map(([dev, c]) => {
    const isActive = activeKey && norm(dev) === activeKey ? " is-active" : "";
    return `
      <tr class="row-device${isActive}" data-device="${dev}">
        <td><span class="cell-device">${dev}</span></td>
        <td class="is-right"><span class="pill pill-count">${c}</span></td>
      </tr>
    `;
  }).join("");
  tbody.innerHTML = html;

  // Toggle de filtro por fila
  tbody.querySelectorAll("tr.row-device").forEach((tr) => {
    tr.addEventListener("click", () => {
      const dev = tr.getAttribute("data-device");
      actions.toggleDevice(dev);
    });
  });

  // === Botón "Ver alarmas" (mismo helper que el resto) ===
  const cardBody = tbody.closest(".card-body") || tbody;
  ensureHeaderButton(cardBody, "btn-see-alarms-devices", () => {
    // Si NO hay deviceFilter activo, limitamos a los dispositivos visibles de la tabla.
    const visibleDevices = new Set((rows || []).map(([d]) => String(d ?? "").trim()));

    const ids = collectAlarmIdsForCurrentFilter((r) => {
      // Si ya hay deviceFilter, el helper lo respeta y este predicate no limita.
      if (activeKey) return true;
      const raw = String(r?.device ?? "").trim();
      return visibleDevices.has(raw);
    });

    showAlarms(ids);
  });
}
