import { setupChartJSDefaults } from "/static/js/soar/theme.js";
import { loadAll } from "/static/js/soar/data.js";
import { onStateChange } from "/static/js/soar/state.js";
import { renderCountries } from "/static/js/soar/charts/countries.js";
import { renderSecAction } from "/static/js/soar/charts/secaction.js";
import { renderSeverity } from "/static/js/soar/charts/severity.js";

function showOverlay(){ document.getElementById("loading-overlay")?.classList.add("is-active"); }
function hideOverlay(){ document.getElementById("loading-overlay")?.classList.remove("is-active"); }

window.addEventListener("DOMContentLoaded", () => {
  setupChartJSDefaults(Chart);

  showOverlay();
  try {
    loadAll(); // si es síncrono/embedded, no hace falta await
    renderCountries();
    renderSecAction();
    renderSeverity();
  } catch (e) {
    console.error("Error inicializando SOAR:", e);
  } finally {
    hideOverlay();
  }

  onStateChange(() => {
    try {
      renderCountries();
      renderSecAction();
      renderSeverity();
    } catch(e){
      console.error("Error re-render:", e);
    }
  });
});
