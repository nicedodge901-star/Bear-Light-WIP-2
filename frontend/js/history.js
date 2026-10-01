// Saved DLLs in localStorage. Every write is guarded (browser quota is ~5 MB).
const KEY = 'bear_light_history';

export function loadHistory() {
  try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; }
}
export function saveHistory(list) {
  try { localStorage.setItem(KEY, JSON.stringify(list)); return true; } catch { return false; }
}
export function upsert(list, dll) {
  return list.some(d => d.id === dll.id) ? list.map(d => (d.id === dll.id ? dll : d)) : [dll, ...list];
}
