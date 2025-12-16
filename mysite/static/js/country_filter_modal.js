// ===============================
// Modal: Filtro de países whitelist (POR TENANT)
// ===============================

// Helper CSRF desde cookies (Django)
function getCookie(name) {
  var value = "; " + document.cookie;
  var parts = value.split("; " + name + "=");
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}

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
    if (c) set[String(c).trim()] = true;
  });

  var all = document.querySelectorAll("#countryModal .country-checkbox");
  all.forEach(function (cb) {
    var code = (cb.value || "").trim();
    var checked = !!set[code];
    cb.checked = checked;

    var pill = cb.closest(".country-pill");
    if (pill) pill.classList.toggle("is-selected", checked);
  });
}

// ===============================
// Cargar selección desde backend (por tenant actual)
// ===============================
function loadCountriesAjax() {
  var modal = document.getElementById("countryModal");
  if (!modal) return Promise.resolve([]);

  var loadUrl =
    modal.getAttribute("data-load-url") ||
    window.WHITELIST_GET_COUNTRIES_URL ||
    "/home/whitelist/get-countries/";

  return fetch(loadUrl, {
    method: "GET",
    headers: { "X-Requested-With": "XMLHttpRequest" }
  })
    .then(function (resp) { return resp.json(); })
    .then(function (data) {
      if (!data || !data.ok) {
        console.error("Error cargando países:", data);
        return [];
      }
      // ✅ usamos códigos
      return data.selected_codes || [];
    })
    .catch(function (err) {
      console.error("Error AJAX cargando países:", err);
      return [];
    });
}

// ===============================
// Guardado vía AJAX (sin recargar)
// ===============================
function saveCountriesAjax(codes) {
  var modal = document.getElementById("countryModal");
  if (!modal) {
    console.error("No se encontró #countryModal");
    return Promise.resolve(false);
  }

  var saveUrl =
    modal.getAttribute("data-save-url") ||
    window.WHITELIST_SAVE_COUNTRIES_URL ||
    "/home/whitelist/save-countries/";

  var csrfToken = getCookie("csrftoken") || "";

  var params = new URLSearchParams();
  params.append("countries", (codes || []).join(","));

  return fetch(saveUrl, {
    method: "POST",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "X-CSRFToken": csrfToken
    },
    body: params.toString()
  })
    .then(function (resp) { return resp.json(); })
    .then(function (data) {
      if (!data || !data.ok) {
        console.error("Error guardando países:", data);
        return false;
      }

      // ✅ aplicar lo guardado (códigos)
      applySelectedCountries(data.selected_codes || []);

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
      console.error("Error AJAX guardando países:", err);
      return false;
    });
}

// ===============================
// Mostrar / ocultar modal
// ===============================
function toggleCountryModal(show) {
  var modal = document.getElementById("countryModal");
  if (!modal) return;

  if (show) {
    modal.classList.remove("hidden");

    // ✅ cargar desde BD y marcar
    loadCountriesAjax().then(function (selectedCodes) {
      applySelectedCountries(selectedCodes);

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
