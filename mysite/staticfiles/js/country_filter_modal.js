// ===============================
// Modal: Filtro de países whitelist
// ===============================

// Helper CSRF desde cookies (Django)
function getCookie(name) {
  var value = "; " + document.cookie;
  var parts = value.split("; " + name + "=");
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return null;
}

// Mostrar / ocultar modal de países
function toggleCountryModal(show) {
  var modal = document.getElementById("countryModal");
  if (!modal) return;

  if (show) {
    modal.classList.remove("hidden");

    // Estado inicial viene desde el backend (selected_paises).

    // Aplicar filtro actual del buscador (si hubiera texto escrito)
    var searchInput = document.getElementById("countrySearch");
    var term = "";
    if (searchInput) {
      term = (searchInput.value || "").toLowerCase().trim();
    }
    filterCountries(term);
  } else {
    modal.classList.add("hidden");
  }
}

// Cerrar al hacer click en el fondo (pero no dentro de la tarjeta)
function backdropClickCountry(event) {
  if (event.target && event.target.id === "countryModal") {
    toggleCountryModal(false);
  }
}

// ===============================
// Guardado vía AJAX (sin recargar)
// ===============================

// Devuelve array de códigos ISO seleccionados (['CL', 'AR', ...])
function getSelectedCountryCodes() {
  var checkboxes = document.querySelectorAll(
    "#countryModal .country-checkbox:checked"
  );
  var selected = [];
  checkboxes.forEach(function (cb) {
    if (cb.value) {
      selected.push(cb.value);
    }
  });
  return selected;
}

// Llamada AJAX al backend para guardar países
function saveCountriesAjax(codes) {
  var modal = document.getElementById("countryModal");
  if (!modal) {
    console.error("No se encontró #countryModal");
    return Promise.resolve(false);
  }

  // URL de guardado: data-save-url en el modal o variable global de respaldo
  var saveUrl =
    modal.getAttribute("data-save-url") ||
    window.WHITELIST_SAVE_COUNTRIES_URL || // opcional
    "/home/whitelist/save-countries/"; // fallback por si acaso

  var csrfToken = getCookie("csrftoken") || "";

  var params = new URLSearchParams();
  // backend recibirá "countries=CL,AR,US"
  params.append("countries", codes.join(","));

  return fetch(saveUrl, {
    method: "POST",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "X-CSRFToken": csrfToken
    },
    body: params.toString()
  })
    .then(function (resp) {
      return resp.json();
    })
    .then(function (data) {
      if (!data.ok) {
        console.error("Error guardando países:", data);
        // Podrías mostrar un mensaje de error en la propia modal si quieres
        return false;
      }

      console.log(
        "Preferencias de países guardadas en servidor:",
        data.selected_paises
      );

      // Mostrar mensaje dentro de la modal ANTES de cerrarla
      var toast = document.getElementById("countrySaveToast");
      if (toast) {
        toast.classList.remove("hidden");
        toast.classList.add("show");

        // Dejamos visible el mensaje un momento y luego cerramos la modal
        setTimeout(function () {
          toast.classList.remove("show");
          toggleCountryModal(false);
        }, 1500); // ajusta el tiempo a gusto
      } else {
        // Si no hay toast, cerramos directamente
        toggleCountryModal(false);
      }

      return true;
    })
    .catch(function (err) {
      console.error("Error AJAX guardando países:", err);
      return false;
    });
}

// Guardar selección (solo AJAX, sin recargar)
function saveCountryFilter() {
  var selected = getSelectedCountryCodes();
  // Ahora el cierre de la modal se maneja dentro de saveCountriesAjax,
  // después de mostrar el mensaje.
  saveCountriesAjax(selected);
}

// Limpiar checkboxes y quitar filtro (en servidor también)
function resetCountryFilter() {
  var checkboxes = document.querySelectorAll(
    "#countryModal .country-checkbox"
  );

  checkboxes.forEach(function (cb) {
    cb.checked = false;
    var pill = cb.closest(".country-pill");
    if (pill) {
      pill.classList.remove("is-selected");
    }
  });

  // Limpiar buscador visualmente y mostrar todos los países
  var searchInput = document.getElementById("countrySearch");
  if (searchInput) {
    searchInput.value = "";
  }
  filterCountries("");

  // Persistir en servidor lista vacía (sin países seleccionados)
  // Puedes decidir si aquí también quieres mostrar un mensaje y cerrar,
  // o solo dejar la modal abierta. En este ejemplo solo guardamos en backend.
  saveCountriesAjax([]);
}

// Marcar / desmarcar pill visualmente al cambiar checkbox
document.addEventListener("change", function (event) {
  if (event.target && event.target.matches("#countryModal .country-checkbox")) {
    var cb = event.target;
    var pill = cb.closest(".country-pill");
    if (pill) {
      pill.classList.toggle("is-selected", cb.checked);
    }
  }
});

// ===============================
// Buscador de países en el modal
// ===============================

// Función helper para aplicar el filtro a los pills
function filterCountries(term) {
  term = (term || "").toLowerCase().trim();
  var pills = document.querySelectorAll("#countryModal .country-pill");

  pills.forEach(function (pill) {
    var name = (pill.textContent || "").toLowerCase();
    // Mostrar solo los que contengan el término
    pill.style.display = name.indexOf(term) !== -1 ? "" : "none";
  });
}

// Escuchar cambios de texto en el input de búsqueda
document.addEventListener("input", function (event) {
  if (event.target && event.target.id === "countrySearch") {
    var term = event.target.value;
    filterCountries(term);
  }
});

// Exponer funciones al ámbito global para que el HTML las pueda usar
window.toggleCountryModal     = toggleCountryModal;
window.backdropClickCountry   = backdropClickCountry;
window.saveCountryFilter      = saveCountryFilter;
window.resetCountryFilter     = resetCountryFilter;
