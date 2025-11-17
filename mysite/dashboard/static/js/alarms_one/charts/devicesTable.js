// static/js/alarms_one/charts/devicesTable.js
import { getState, actions } from "../state.js";
import { deviceRowsForCurrentFilter } from "../selectors.js";
import data from "../data.js";

/**
 * Conecta el botón "🗂 Ver alarmas" de la card Dispositivos recientes
 * para abrir el modal con el dispositivo actualmente seleccionado.
 */
function attachDeviceModalButton() {
  const btn = document.getElementById("btn-open-device-alarms");
  if (!btn) return;

  // Evita duplicar listeners si se re-renderiza
  btn.replaceWith(btn.cloneNode(true));
  const safeBtn = document.getElementById("btn-open-device-alarms");

  safeBtn.addEventListener("click", () => {
    const state = getState();

    // 1) intenta usar el filtro activo en el estado
    let devKey = state.deviceFilter
      ? data.canonicalDeviceKey(state.deviceFilter)
      : "";

    // 2) si no hay filtro, intenta con la fila activa en la tabla
    if (!devKey) {
      const activeRow = document.querySelector(
        "#device-table-body tr.row-device.is-active"
      );
      devKey = activeRow?.getAttribute("data-device") || "";
    }

    // 3) si aún no hay dispositivo, toma la primera fila visible
    if (!devKey) {
      const firstRow = document.querySelector("#device-table-body tr.row-device");
      devKey = firstRow?.getAttribute("data-device") || "";
    }

    if (!devKey) {
      // feedback sutil si no hay nada para abrir
      safeBtn.disabled = true;
      setTimeout(() => (safeBtn.disabled = false), 500);
      return;
    }

    const title = `Alarmas – Dispositivo: ${devKey}`;

    // API global expuesta por alarms-modal.js
    // Soporta openForFilters({ title, filters }) o open({ title, filters })
    if (window.AlarmsModal?.openForFilters) {
      window.AlarmsModal.openForFilters({
        title,
        filters: { device: devKey },
      });
    } else if (window.AlarmsModal?.open) {
      window.AlarmsModal.open({
        title,
        filters: { device: devKey },
      });
    } else {
      console.warn("[DeviceTable] AlarmsModal no está disponible en window.");
    }
  });
}

export function renderDeviceTable() {
  const tbody = document.getElementById("device-table-body");
  if (!tbody) return;

  const rows = deviceRowsForCurrentFilter(getState());
  const activeKey = data.canonicalDeviceKey(getState().deviceFilter);

  tbody.innerHTML = rows
    .map(([dev, c]) => {
      const isActive = activeKey === dev ? " is-active" : "";
      return `
        <tr class="row-device${isActive}" data-device="${dev}">
          <td><span class="cell-device">${dev}</span></td>
          <td class="is-right"><span class="pill pill-count">${c}</span></td>
        </tr>
      `;
    })
    .join("");

  // Click en fila -> setea el filtro de dispositivo
  tbody.querySelectorAll("tr.row-device").forEach((tr) => {
    tr.addEventListener("click", () => {
      const dev = tr.getAttribute("data-device");
      actions.setDevice(dev); // esto re-renderiza todo lo necesario
    });
  });

  // Conecta/actualiza el botón del modal
  attachDeviceModalButton();
}
