// ===============================
// Modal: Filtro de países whitelist (POR TENANT)
// - FIX CSRF: usar token desde DOM (hidden/meta) y fallback cookie
// - FIX fetch: credentials same-origin para sesión/cookies estables
// ===============================

// ------------------------------------------------------------
// CSRF helpers (robusto)
// Recomendado: en el template incluir:
//   <input type="hidden" id="countryCsrfToken" value="{{ csrf_token }}">
// o en base.html:
//   <meta name="csrf-token" content="{{ csrf_token }}">
// ------------------------------------------------------------

function getCookie(name) {
  var value = "; " + document.cookie;
  var parts = value.split("; " + name + "=");
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}

function getCsrfToken() {
  // 1) Hidden token en el modal
  var hidden = document.getElementById("countryCsrfToken");
  if (hidden && hidden.value) return String(hidden.value).trim();

  // 2) Meta tag global
  var meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return String(meta.content).trim();

  // 3) Fallback cookie
  var c = getCookie("csrftoken");
  return c ? String(c).trim() : "";
}

// ------------------------------------------------------------
// Modal helpers
// ------------------------------------------------------------

function getModalEl() {
  return document.getElementById("countryModal");
}

function getTenantIdFromModal() {
  var modal = getModalEl();
  if (!modal) return "";
  return (modal.getAttribute("data-tenant-id") || "").trim();
}

function getLoadUrlFromModal() {
  var modal = getModalEl();
  if (!modal) return "";
  return (
    modal.getAttribute("data-load-url") ||
    window.WHITELIST_GET_COUNTRIES_URL ||
    "/home/whitelist/get-countries/"
  );
}

function getSaveUrlFromModal() {
  var modal = getModalEl();
  if (!modal) return "";
  return (
    modal.getAttribute("data-save-url") ||
    window.WHITELIST_SAVE_COUNTRIES_URL ||
    "/home/whitelist/save-countries/"
  );
}

// ===============================
// Fetch helper: maneja 500/HTML y muestra detalle real
// - credentials same-origin (importante)
// ===============================
function fetchJsonOrThrow(url, options) {
  var finalOptions = Object.assign(
    {
      credentials: "same-origin",
      redirect: "follow"
    },
    options || {}
  );

  return fetch(url, finalOptions).then(function (resp) {
    return resp.text().then(function (text) {
      var data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch (e) {
        data = null; // puede venir HTML (debug) o texto plano
      }

      if (!resp.ok) {
        var err = new Error("HTTP " + resp.status + " " + resp.statusText);
        err.status = resp.status;
        err.bodyText = text;
        err.bodyJson = data;
        throw err;
      }

      // 200 OK, pero si no era JSON válido, igual devolvemos algo útil
      return data !== null ? data : { ok: false, message: "Respuesta no-JSON", raw: text };
    });
  });
}

// ===============================
// UI helpers
// ===============================

// Devuelve array de códigos ISO seleccionados (['CL', 'AR', ...])
function getSelectedCountryCodes() {
  var checkboxes = document.querySelectorAll("#countryModal .country-checkbox:checked");
  var selected = [];
  checkboxes.forEach(function (cb) {
    if (cb.value) selected.push(cb.value);
  });
  return selected;
}

// Aplica selección a UI (checkbox + pill) usando CÓDIGOS
function applySelectedCountries(codes) {
  var set = {};
  (codes || []).forEach(function (c) {
    if (!c) return;
    set[String(c).trim().toUpperCase()] = true;
  });

  var all = document.querySelectorAll("#countryModal .country-checkbox");
  all.forEach(function (cb) {
    var code = (cb.value || "").trim().toUpperCase();
    var checked = !!set[code];
    cb.checked = checked;

    var pill = cb.closest(".country-pill");
    if (pill) pill.classList.toggle("is-selected", checked);
  });
}

// Lee lo que ya venía renderizado en el template (fallback si falla AJAX)
function getSelectedCodesFromRenderedHTML() {
  var codes = [];
  var checked = document.querySelectorAll("#countryModal .country-checkbox:checked");
  checked.forEach(function (cb) {
    if (cb.value) codes.push(String(cb.value).trim().toUpperCase());
  });
  return codes;
}

// ===============================
// Cargar selección desde backend (por tenant actual)
// ===============================
function loadCountriesAjax() {
  var modal = getModalEl();
  if (!modal) return Promise.resolve([]);

  var baseUrl = getLoadUrlFromModal();
  var tenantId = getTenantIdFromModal();

  // anexar tenant_id como querystring (aunque el backend lo ignore si no coincide)
  var url = baseUrl;
  try {
    var u = new URL(baseUrl, window.location.origin);
    if (tenantId) u.searchParams.set("tenant_id", tenantId);
    url = u.toString();
  } catch (e) {
    if (tenantId) {
      url = baseUrl + (baseUrl.indexOf("?") >= 0 ? "&" : "?") + "tenant_id=" + encodeURIComponent(tenantId);
    }
  }

  return fetchJsonOrThrow(url, {
    method: "GET",
    headers: { "X-Requested-With": "XMLHttpRequest" }
  })
    .then(function (data) {
      if (!data || !data.ok) {
        console.error("[COUNTRY MODAL] Backend respondió ok=false en GET:", data);
        return [];
      }
      return (data.selected_codes || []).map(function (c) { return String(c).trim().toUpperCase(); });
    })
    .catch(function (err) {
      console.error("[COUNTRY MODAL] GET falló:", err);
      if (err.bodyJson) console.error("[COUNTRY MODAL] GET bodyJson:", err.bodyJson);
      if (err.bodyText) console.error("[COUNTRY MODAL] GET bodyText (primeros 1200):", String(err.bodyText).slice(0, 1200));
      return [];
    });
}

// ===============================
// Guardado vía AJAX (sin recargar)
// ===============================
function saveCountriesAjax(codes) {
  var modal = getModalEl();
  if (!modal) {
    console.error("[COUNTRY MODAL] No se encontró #countryModal");
    return Promise.resolve(false);
  }

  var saveUrl = getSaveUrlFromModal();
  var tenantId = getTenantIdFromModal();
  var csrfToken = getCsrfToken(); // FIX: token robusto

  if (!csrfToken || csrfToken.length < 10) {
    console.warn("[COUNTRY MODAL] CSRF token vacío o sospechoso. Verifica el hidden/meta csrf_token.");
  }

  var params = new URLSearchParams();
  params.append("countries", (codes || []).join(","));
  if (tenantId) params.append("tenant_id", tenantId);

  return fetchJsonOrThrow(saveUrl, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "X-CSRFToken": csrfToken
    },
    body: params.toString()
  })
    .then(function (data) {
      if (!data || !data.ok) {
        console.error("[COUNTRY MODAL] Backend respondió ok=false en POST:", data);
        return false;
      }

      applySelectedCountries((data.selected_codes || []).map(function (c) { return String(c).trim().toUpperCase(); }));

      var toast = document.getElementById("countrySaveToast");
      if (toast) {
        toast.classList.remove("hidden");
        toast.classList.add("show");
        setTimeout(function () {
          toast.classList.remove("show");
          toggleCountryModal(false);
        }, 1500);
      } else {
        toggleCountryModal(false);
      }

      return true;
    })
    .catch(function (err) {
      console.error("[COUNTRY MODAL] POST falló:", err);
      if (err.bodyJson) console.error("[COUNTRY MODAL] POST bodyJson:", err.bodyJson);
      if (err.bodyText) console.error("[COUNTRY MODAL] POST bodyText (primeros 1200):", String(err.bodyText).slice(0, 1200));
      return false;
    });
}

// ===============================
// Mostrar / ocultar modal
// ===============================
function toggleCountryModal(show) {
  var modal = getModalEl();
  if (!modal) return;

  if (show) {
    modal.classList.remove("hidden");

    // 1) Fallback inmediato: deja lo que venía renderizado
    applySelectedCountries(getSelectedCodesFromRenderedHTML());

    // 2) Luego intenta cargar desde BD
    loadCountriesAjax().then(function (selectedCodes) {
      if (selectedCodes && selectedCodes.length) {
        applySelectedCountries(selectedCodes);
      }

      var searchInput = document.getElementById("countrySearch");
      var term = "";
      if (searchInput) term = (searchInput.value || "").toLowerCase().trim();
      filterCountries(term);
    });
  } else {
    modal.classList.add("hidden");
  }
}

// Cerrar al hacer click en el fondo
function backdropClickCountry(event) {
  if (event.target && event.target.id === "countryModal") {
    toggleCountryModal(false);
  }
}

// Guardar selección
function saveCountryFilter() {
  var selected = getSelectedCountryCodes();
  saveCountriesAjax(selected);
}

// Reset selección
function resetCountryFilter() {
  var checkboxes = document.querySelectorAll("#countryModal .country-checkbox");
  checkboxes.forEach(function (cb) {
    cb.checked = false;
    var pill = cb.closest(".country-pill");
    if (pill) pill.classList.remove("is-selected");
  });

  var searchInput = document.getElementById("countrySearch");
  if (searchInput) searchInput.value = "";
  filterCountries("");

  saveCountriesAjax([]);
}

// Marcar/desmarcar pill al cambiar checkbox
document.addEventListener("change", function (event) {
  if (event.target && event.target.matches("#countryModal .country-checkbox")) {
    var cb = event.target;
    var pill = cb.closest(".country-pill");
    if (pill) pill.classList.toggle("is-selected", cb.checked);
  }
});

// ===============================
// Buscador de países
// ===============================
function filterCountries(term) {
  term = (term || "").toLowerCase().trim();
  var pills = document.querySelectorAll("#countryModal .country-pill");

  pills.forEach(function (pill) {
    var name = (pill.textContent || "").toLowerCase();
    pill.style.display = name.indexOf(term) !== -1 ? "" : "none";
  });
}

document.addEventListener("input", function (event) {
  if (event.target && event.target.id === "countrySearch") {
    filterCountries(event.target.value);
  }
});

// Exponer funciones
window.toggleCountryModal = toggleCountryModal;
window.backdropClickCountry = backdropClickCountry;
window.saveCountryFilter = saveCountryFilter;
window.resetCountryFilter = resetCountryFilter;
