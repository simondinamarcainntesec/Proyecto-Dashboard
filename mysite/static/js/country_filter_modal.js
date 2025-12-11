// ===============================
// Modal: Filtro de países whitelist
// ===============================

// Mostrar / ocultar modal de países
function toggleCountryModal(show) {
  var modal = document.getElementById('countryModal');
  if (!modal) return;

  if (show) {
    modal.classList.remove('hidden');

    // Sincronizar estado de checkboxes en base a URL/localStorage
    initCountryModalFromState();

    // Aplicar filtro actual del buscador (si hubiera texto escrito)
    var searchInput = document.getElementById('countrySearch');
    var term = '';
    if (searchInput) {
      term = (searchInput.value || '').toLowerCase().trim();
    }
    filterCountries(term);
  } else {
    modal.classList.add('hidden');
  }
}

// Cerrar al hacer click en el fondo (pero no dentro de la tarjeta)
function backdropClickCountry(event) {
  if (event.target && event.target.id === 'countryModal') {
    toggleCountryModal(false);
  }
}

// Leer países actuales desde querystring o localStorage
function getCurrentCountries() {
  try {
    var url = new URL(window.location.href);
    var qsValue = url.searchParams.get('countries');
    if (qsValue) {
      return qsValue
        .split(',')
        .map(function (p) { return p.trim(); })
        .filter(function (p) { return p.length > 0; });
    }
  } catch (e) {
    console.warn('URL API no disponible, usando solo localStorage', e);
  }

  // fallback opcional a localStorage
  try {
    var stored = localStorage.getItem('whitelistCountries');
    if (stored) {
      var parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch (e) {
    console.warn('Error leyendo whitelistCountries desde localStorage', e);
  }

  return [];
}

// Inicializa checkboxes cuando se abre el modal
function initCountryModalFromState() {
  var selected = new Set(getCurrentCountries());
  var checkboxes = document.querySelectorAll('#countryModal .country-checkbox');

  checkboxes.forEach(function (cb) {
    var value = cb.value;
    cb.checked = selected.has(value);

    var pill = cb.closest('.country-pill');
    if (pill) {
      pill.classList.toggle('is-selected', cb.checked);
    }
  });
}

// Guardar selección (URL + localStorage) y recargar whitelist
function saveCountryFilter() {
  var checkboxes = document.querySelectorAll('#countryModal .country-checkbox');
  var selected = [];

  checkboxes.forEach(function (cb) {
    if (cb.checked) {
      selected.push(cb.value);
    }
  });

  // Guardamos en localStorage (opcional)
  try {
    localStorage.setItem('whitelistCountries', JSON.stringify(selected));
  } catch (e) {
    console.warn('Error guardando whitelistCountries en localStorage', e);
  }

  var url;
  try {
    url = new URL(window.location.href);
  } catch (e) {
    console.error('No se pudo construir URL', e);
    return;
  }

  if (selected.length > 0) {
    // Hay países seleccionados: countries=CL,AR,...
    url.searchParams.set('countries', selected.join(','));
  } else {
    // Sin países seleccionados: enviamos countries= (vacío)
    // para que el backend limpie la preferencia en la base de datos
    url.searchParams.set('countries', '');
  }

  // Toast de feedback
  var toast = document.getElementById('countrySaveToast');
  if (toast) {
    toast.classList.remove('hidden');
    toast.classList.add('show');

    // pequeño delay para que se vea el toast
    setTimeout(function () {
      toast.classList.remove('show');
      window.location.href = url.toString();
    }, 400);
  } else {
    window.location.href = url.toString();
  }
}

// Limpiar checkboxes y quitar filtro
function resetCountryFilter() {
  var checkboxes = document.querySelectorAll('#countryModal .country-checkbox');
  checkboxes.forEach(function (cb) {
    cb.checked = false;
    var pill = cb.closest('.country-pill');
    if (pill) {
      pill.classList.remove('is-selected');
    }
  });

  // Limpiar buscador visualmente y mostrar todos los países
  var searchInput = document.getElementById('countrySearch');
  if (searchInput) {
    searchInput.value = '';
  }
  filterCountries('');

  try {
    localStorage.removeItem('whitelistCountries');
  } catch (e) {
    console.warn('Error limpiando whitelistCountries en localStorage', e);
  }

  var url;
  try {
    url = new URL(window.location.href);
  } catch (e) {
    console.error('No se pudo construir URL', e);
    return;
  }

  // Muy importante: mandamos countries= vacío para que el backend
  // borre la preferencia guardada en agent.whitelist_country_preference
  url.searchParams.set('countries', '');

  window.location.href = url.toString();
}

// Marcar / desmarcar pill visualmente al cambiar checkbox
document.addEventListener('change', function (event) {
  if (event.target && event.target.matches('#countryModal .country-checkbox')) {
    var cb = event.target;
    var pill = cb.closest('.country-pill');
    if (pill) {
      pill.classList.toggle('is-selected', cb.checked);
    }
  }
});

// ===============================
// Buscador de países en el modal
// ===============================

// Función helper para aplicar el filtro a los pills
function filterCountries(term) {
  term = (term || '').toLowerCase().trim();
  var pills = document.querySelectorAll('#countryModal .country-pill');

  pills.forEach(function (pill) {
    var name = (pill.textContent || '').toLowerCase();
    // Mostrar solo los que contengan el término
    pill.style.display = name.indexOf(term) !== -1 ? '' : 'none';
  });
}

// Escuchar cambios de texto en el input de búsqueda
document.addEventListener('input', function (event) {
  if (event.target && event.target.id === 'countrySearch') {
    var term = event.target.value;
    filterCountries(term);
  }
});
