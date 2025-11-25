// static/js/siem_alerts.js
document.addEventListener("DOMContentLoaded", function () {
  const rows = document.querySelectorAll(".alert-row");
  const modal = document.getElementById("siemModal");
  if (!modal) return;

  const backdrop = modal.querySelector(".modal-backdrop");
  const closeBtn = modal.querySelector("[data-close]");

  const titleEl = document.getElementById("siem-title");
  const subtitleEl = document.getElementById("siem-subtitle");
  const msgEl = document.getElementById("siem-message");

  const metaTime = document.getElementById("siem-meta-time");
  const metaProfile = document.getElementById("siem-meta-profile");
  const metaSrc = document.getElementById("siem-meta-src");
  const metaDst = document.getElementById("siem-meta-dst");
  const metaAction = document.getElementById("siem-meta-action");
  const metaService = document.getElementById("siem-meta-service");

  const chipSev = document.getElementById("siem-chip-sev");
  const chipSrcIp = document.getElementById("siem-chip-srcip");
  const chipDstIp = document.getElementById("siem-chip-dstip");
  const chipAction = document.getElementById("siem-chip-action");

  function openModalFromRow(row) {
    const time = row.dataset.time || "";
    const sev = row.dataset.severity || "";
    const profile = row.dataset.profile || "";
    const srcip = row.dataset.srcip || "";
    const dstip = row.dataset.dstip || "";
    const action = row.dataset.action || "";
    const service = row.dataset.service || "";
    const message = row.dataset.message || "";
    const logsrc = row.dataset.logsrc || "";

    if (titleEl) {
      titleEl.textContent = sev ? `Alerta – ${sev}` : "Detalle de alerta";
    }
    if (subtitleEl) {
      const parts = [];
      if (time) parts.push(time);
      if (profile) parts.push(`Perfil: ${profile}`);
      if (logsrc) parts.push(`Log Source: ${logsrc}`);
      subtitleEl.textContent = parts.join(" · ");
    }

    if (metaTime) metaTime.textContent = time || "—";
    if (metaProfile) metaProfile.textContent = profile || "—";
    if (metaSrc) metaSrc.textContent = srcip || "—";
    if (metaDst) metaDst.textContent = dstip || "—";
    if (metaAction) metaAction.textContent = action || "—";
    if (metaService) metaService.textContent = service || "—";

    if (chipSev) chipSev.textContent = sev || "—";
    if (chipSrcIp) chipSrcIp.textContent = srcip || "—";
    if (chipDstIp) chipDstIp.textContent = dstip || "—";
    if (chipAction) chipAction.textContent = action || "—";

    if (msgEl) {
      msgEl.textContent = message || "";
    }

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
