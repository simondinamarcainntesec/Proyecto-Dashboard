import { getState, actions } from "/static/js/soar/state.js";
import { deviceRowsForCurrentFilter } from "/static/js/soar/selectors.js";

const norm = (s) => String(s ?? "").trim().toLowerCase();

export function renderDeviceTable(){
  const tbody = document.getElementById("device-table-body");
  if (!tbody) return;

  const st = getState();
  const rows = deviceRowsForCurrentFilter();

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

  // click → activa filtro (un único filtro global a la vez)
  tbody.querySelectorAll("tr.row-device").forEach((tr) => {
    tr.addEventListener("click", () => {
      const dev = tr.getAttribute("data-device");
      actions.toggleDevice(dev);
    });
  });
}
