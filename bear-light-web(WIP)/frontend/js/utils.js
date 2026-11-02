export const $ = (id) => document.getElementById(id);

// Always escape text before putting it in innerHTML (AI output is untrusted).
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

// setPath(obj, 'procedures.a_review', 'text') / getPath(obj, 'header.schoolName')
export function getPath(obj, path) { return path.split('.').reduce((o, k) => o?.[k], obj); }
export function setPath(obj, path, value) {
  const keys = path.split('.'); const last = keys.pop();
  keys.reduce((o, k) => (o[k] ??= {}), obj)[last] = value;
}
