// Estado global y acciones (un filtro activo a la vez)
const state = {
  severityFilter: "",
  countryFilter:  "",
  actionFilter:   "",
};

const listeners = new Set();
export function getState(){ return { ...state }; }
export function onStateChange(fn){ listeners.add(fn); return () => listeners.delete(fn); }
export function setState(patch){
  Object.assign(state, patch);
  listeners.forEach(fn => fn(getState()));
}

const norm = (s) => String(s ?? "").trim().toLowerCase();

export const actions = {
  toggleSeverity(sev){
    const s = norm(state.severityFilter) === norm(sev) ? "" : sev;
    // un solo filtro activo
    setState({ severityFilter: s, countryFilter:"", actionFilter:"" });
  },
  toggleCountry(country){
    const s = norm(state.countryFilter) === norm(country) ? "" : country;
    setState({ severityFilter:"", countryFilter: s, actionFilter:"" });
  },
  toggleAction(action){
    const s = norm(state.actionFilter) === norm(action) ? "" : action;
    setState({ severityFilter:"", countryFilter:"", actionFilter: s });
  },
  clearAll(){
    setState({ severityFilter:"", countryFilter:"", actionFilter:"" });
  }
};
