// Carga filas crudas embebidas en el template
export function readJSON(id){
  const el = document.getElementById(id);
  if (!el) return null;
  try { return JSON.parse(el.textContent); }
  catch(e){ console.error("JSON inválido:", id, e); return null; }
}

let EVENTS = [];

export function loadAll(){
  EVENTS = readJSON("soar-events") || [];
  return EVENTS;
}

export function getEvents(){ return EVENTS; }
