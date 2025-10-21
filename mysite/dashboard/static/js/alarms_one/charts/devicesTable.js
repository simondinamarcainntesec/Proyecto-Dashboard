// charts/devicesTable.js
import { getState, actions } from "../state.js";
import { deviceRowsForCurrentFilter } from "../selectors.js";
import data from "../data.js";

export function renderDeviceTable() {
  const tbody = document.getElementById("device-table-body");
  const rows = deviceRowsForCurrentFilter(getState());
  tbody.innerHTML = rows.map(([dev, c]) => {
    const active = data.canonicalDeviceKey(getState().deviceFilter) === dev ? " is-active" : "";
    return `
      <tr class="row-device${active}" data-device="${dev}">
        <td><span class="cell-device">${dev}</span></td>
        <td class="is-right"><span class="pill pill-count">${c}</span></td>
      </tr>
    `;
  }).join("");
  tbody.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => {
      const dev = tr.getAttribute("data-device");
      actions.setDevice(dev);
    });
  });
}
