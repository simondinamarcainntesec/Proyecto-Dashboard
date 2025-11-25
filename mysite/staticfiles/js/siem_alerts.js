// static/js/siem_alerts.js
document.addEventListener("DOMContentLoaded", function () {
  const rows = document.querySelectorAll(".alert-row");
  const modal = document.getElementById("siemModal");
  if (!modal) return;

  const backdrop = modal.querySelector(".modal-backdrop");
  const closeBtn = modal.querySelector("[data-close]");

  const titleEl = document.getElementById("siem-title");

  const metaTime = document.getElementById("siem-meta-time");
  const metaProfile = document.getElementById("siem-meta-profile");
  const metaSrc = document.getElementById("siem-meta-src");
  const metaDst = document.getElementById("siem-meta-dst");
  const metaAction = document.getElementById("siem-meta-action");
  const metaService = document.getElementById("siem-meta-service");
  const metaDevice = document.getElementById("siem-meta-device");

  const rawContainer = document.getElementById("siem-raw-container");

  function buildKeyValueTableFromJson(rawJson) {
    if (!rawContainer) return;

    rawContainer.innerHTML = "";

    if (!rawJson) {
      rawContainer.textContent = "(sin datos)";
      return;
    }

    let obj = null;

    // Intentamos parsear el JSON tal cual
    try {
      obj = JSON.parse(rawJson);
    } catch (e1) {
      // Si viene con escapes raros, intentamos limpiar algunos (\u000a, etc.)
      try {
        const fixed = rawJson
          .replace(/\\u000a/gi, "\n")
          .replace(/\\u000d/gi, "\r")
          .replace(/\\u0009/gi, "\t");
        obj = JSON.parse(fixed);
      } catch (e2) {
        console.warn("No se pudo parsear JSON de alerta, se muestra crudo", e2);
        const pre = document.createElement("pre");
        pre.textContent = rawJson;
        rawContainer.appendChild(pre);
        return;
      }
    }

    if (!obj || typeof obj !== "object") {
      const pre = document.createElement("pre");
      pre.textContent = rawJson;
      rawContainer.appendChild(pre);
      return;
    }

    const table = document.createElement("table");
    table.className = "tbl tbl-raw-json";

    Object.keys(obj)
      .sort()
      .forEach((key) => {
        // No mostrar el campo Message
        if (key === "Message") return;

        const tr = document.createElement("tr");

        const th = document.createElement("th");
        th.textContent = key;

        const td = document.createElement("td");
        const value = obj[key];

        if (value === null || value === undefined || value === "") {
          td.textContent = "—";
        } else if (typeof value === "object") {
          td.textContent = JSON.stringify(value, null, 2);
        } else {
          td.textContent = String(value);
        }

        tr.appendChild(th);
        tr.appendChild(td);
        table.appendChild(tr);
      });

    rawContainer.appendChild(table);
  }

  function openModalFromRow(row) {
    const time = row.dataset.time || "";
    const sev = row.dataset.severity || "";
    const profile = row.dataset.profile || "";
    const srcip = row.dataset.srcip || "";
    const dstip = row.dataset.dstip || "";
    const action = row.dataset.action || "";
    const service = row.dataset.service || "";
    const logsrc = row.dataset.logsrc || "";
    const device = row.dataset.device || "";
    const rawJson = row.dataset.raw || "";

    if (titleEl) {
      titleEl.textContent = sev ? `Alerta – ${sev}` : "Detalle de alerta";
    }

    if (metaTime) metaTime.textContent = time || "—";
    if (metaProfile) metaProfile.textContent = profile || "—";
    if (metaSrc) metaSrc.textContent = srcip || "—";
    if (metaDst) metaDst.textContent = dstip || "—";
    if (metaAction) metaAction.textContent = action || "—";
    if (metaService) metaService.textContent = service || "—";
    if (metaDevice) metaDevice.textContent = device || "—";

    // Construimos tabla key/value con el JSON completo (sin Message)
    buildKeyValueTableFromJson(rawJson);

    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
  }

  function closeModal() {
    modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
  }

  rows.forEach((row) => {
    row.addEventListener("click", () => openModalFromRow(row));
  });

  if (backdrop) {
    backdrop.addEventListener("click", closeModal);
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", closeModal);
  }

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      closeModal();
    }
  });
});
