// static/js/soar/state.js
const state = {
  severityFilter: "",
  countryFilter: "",
  actionFilter: "",
  deviceFilter: "",
  serviceFilter: "",
  protoFilter: "",
  applicationFilter: "",   // ← NUEVO
  // filtros de IP/hora/fecha si ya los tienes
  srcIPFilter: "",
  dstIPFilter: "",
  hourFilter: "",
  dateFrom: "",
  dateTo: "",
};

const listeners = new Set();
export function getState(){ return { ...state }; }
export function setState(patch){ Object.assign(state, patch); listeners.forEach(l=>l(getState())); }
export function onStateChange(fn){ listeners.add(fn); return () => listeners.delete(fn); }

// un solo filtro activo a la vez (de lo principal)
function only(patch){
  setState({
    severityFilter:"", countryFilter:"", actionFilter:"",
    deviceFilter:"", serviceFilter:"", protoFilter:"",
    applicationFilter:"", srcIPFilter:"", dstIPFilter:"",
    // no tocamos hour/date aquí
    ...patch
  });
}

export const actions = {
  toggleSeverity(sev){
    const s = String(sev ?? "").trim();
    only({ severityFilter: (state.severityFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleCountry(cty){
    const s = String(cty ?? "").trim();
    only({ countryFilter: (state.countryFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleAction(act){
    const s = String(act ?? "").trim();
    only({ actionFilter: (state.actionFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleDevice(dev){
    const s = String(dev ?? "").trim();
    only({ deviceFilter: (state.deviceFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleService(svc){
    const s = String(svc ?? "").trim();
    only({ serviceFilter: (state.serviceFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleProto(proto){
    const s = String(proto ?? "").trim();
    only({ protoFilter: (state.protoFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  // ← NUEVO
  toggleApplication(app){
    const s = String(app ?? "").trim();
    only({ applicationFilter: (state.applicationFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },

  // IPs / hora / fechas (si ya los usas)
  toggleSrcIP(ip){
    const s = String(ip ?? "").trim();
    only({ srcIPFilter: (state.srcIPFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleDstIP(ip){
    const s = String(ip ?? "").trim();
    only({ dstIPFilter: (state.dstIPFilter.toLowerCase() === s.toLowerCase()) ? "" : s });
  },
  toggleHour(hh){
    const s = String(hh ?? "").trim().slice(0,2).padStart(2,"0");
    setState({ hourFilter: (state.hourFilter === s) ? "" : s });
  },
  clearDateRange(){ setState({ dateFrom:"", dateTo:"" }); },
  setExactDay(day){ setState({ dateFrom:day, dateTo:day }); },
};
