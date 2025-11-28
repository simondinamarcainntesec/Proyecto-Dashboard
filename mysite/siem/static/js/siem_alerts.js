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

  const repValueEl = document.getElementById("siem-meta-rep-value");
  const repPointer = document.getElementById("siem-rep-pointer");

  const rawContainer = document.getElementById("siem-raw-container");

  // Aseguramos que el valor de reputation quede DENTRO de la barra
  // para poder posicionarlo justo debajo del triángulo.
  const repBar = modal.querySelector(".rep-widget-header .rep-bar");
  if (repBar && repValueEl && repValueEl.parentElement !== repBar) {
    repBar.appendChild(repValueEl);
  }

  // ==========================
  // Helpers para Threat Rep.
  // ==========================
  function getRepBand(num) {
    if (isNaN(num)) return null;
    if (num >= 1 && num <= 20) return 1;   // rojo
    if (num >= 21 && num <= 40) return 2;  // naranjo
    if (num >= 41 && num <= 60) return 3;  // amarillo
    if (num >= 61 && num <= 80) return 4;  // verde claro
    if (num >= 81 && num <= 100) return 5; // verde
    return null;
  }

  function decorateThreatRepCells() {
    const repCells = document.querySelectorAll(".threat-rep-cell");
    repCells.forEach((cell) => {
      const raw = cell.dataset.rep || "";
      const num = parseInt(raw, 10);
      if (isNaN(num)) {
        cell.textContent = "—";
        return;
      }
      const band = getRepBand(num);
      const span = document.createElement("span");
      span.classList.add("pill");
      if (band === 1) span.classList.add("rep-band-1");
      else if (band === 2) span.classList.add("rep-band-2");
      else if (band === 3) span.classList.add("rep-band-3");
      else if (band === 4) span.classList.add("rep-band-4");
      else if (band === 5) span.classList.add("rep-band-5");
      else span.classList.add("rep-band-na");

      span.textContent = String(num);
      cell.textContent = "";
      cell.appendChild(span);
    });
  }

  // ==========================
  // Construir tabla detalles
  // ==========================
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

  // ==========================
  // Abrir / cerrar modal
  // ==========================
  function openModalFromRow(row) {
    const time = row.dataset.time || "";
    const sev = row.dataset.severity || "";
    const profile = row.dataset.profile || "";
    const srcip = row.dataset.srcip || "";
    const dstip = row.dataset.dstip || "";
    const action = row.dataset.action || "";
    const service = row.dataset.service || "";
    const device = row.dataset.device || "";
    const rawJson = row.dataset.raw || "";
    const repRaw = row.dataset.threatrep || "";

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

    // === Threat Reputation: triángulo + número debajo del triángulo ===
    let repNum = parseInt(repRaw, 10);
    if (Number.isNaN(repNum)) {
      // Sin valor válido
      if (repValueEl) {
        repValueEl.textContent = "—";
        repValueEl.style.left = "50%";
      }
      if (repPointer) {
        repPointer.style.display = "none";
      }
    } else {
      // clamp 0–100
      if (repNum < 0) repNum = 0;
      if (repNum > 100) repNum = 100;

      // Posición lineal 0–100% sobre la barra
      const pos = repNum;

      if (repPointer) {
        repPointer.style.left = pos + "%";
        repPointer.style.display = "block";
      }
      if (repValueEl) {
        repValueEl.textContent = String(repNum);
        repValueEl.style.left = pos + "%"; // mismo left que el triángulo
      }
    }

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

  // Decorar columna de Threat Reputation en la tabla
  decorateThreatRepCells();
});
