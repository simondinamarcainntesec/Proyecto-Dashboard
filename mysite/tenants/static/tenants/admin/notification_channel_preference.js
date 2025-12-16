(function () {
  function qs(sel, root = document) { return root.querySelector(sel); }

  function computeBaseMetaUrl() {
    // /admin/tenants/notificationchannelpreference/add/
    // /admin/tenants/notificationchannelpreference/<id>/change/
    const p = window.location.pathname;
    const base = p.replace(/(add\/|(\d+)\/change\/)$/, "");
    return base + "user-meta/";
  }

  async function loadUserMeta(userId) {
    if (!userId) return null;
    const url = computeBaseMetaUrl() + encodeURIComponent(userId) + "/";
    const resp = await fetch(url, { credentials: "same-origin" });
    if (!resp.ok) return null;
    const data = await resp.json();
    return (data && data.ok) ? data : null;
  }

  function setDisplay(fullName, username, tenant) {
    const nameEl = qs("#id_display_full_name");
    const userEl = qs("#id_display_username");
    const tenEl  = qs("#id_display_tenant");
    if (nameEl) nameEl.value = fullName || "—";
    if (userEl) userEl.value = username || "—";
    if (tenEl)  tenEl.value  = tenant || "—";
  }

  document.addEventListener("DOMContentLoaded", async function () {
    const userSel = qs("#id_user");
    if (!userSel) return;

    async function refresh() {
      const userId = userSel.value;
      if (!userId) {
        setDisplay("—", "—", "—");
        return;
      }
      const meta = await loadUserMeta(userId);
      if (!meta) {
        setDisplay("—", "—", "—");
        return;
      }
      setDisplay(meta.full_name, meta.username, meta.tenant);
    }

    userSel.addEventListener("change", refresh);

    // por si llega con valor precargado
    await refresh();
  });
})();
