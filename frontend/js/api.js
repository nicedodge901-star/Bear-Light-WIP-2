// ALL network calls live here. Backend = FastAPI (see backend/).
// Production: FastAPI serves this page too, so every call is same-origin (empty base).
// Local dev only: if the page is served by `python -m http.server 5500`, talk to the backend on :8000.
const API_BASE = location.port === '5500' ? `http://${location.hostname}:8000` : '';
const OFFLINE = 'Hindi maabot ang server. Subukan muli sa ilang sandali (maaaring ginigising pa ito).';

async function readJson(res) { return res.json().catch(() => ({})); }
function failure(res, data, fallback) {
  if (data.error) return new Error(data.error);
  if (res.status === 429) return new Error('Masyadong maraming request. Maghintay ng isang minuto at subukan muli.');
  if (res.status === 413) return new Error('Masyadong malaki ang ipinadala.');
  return new Error(fallback);
}

async function post(path, body, fallback) {
  let res;
  try { res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
  catch { throw new Error(OFFLINE); }
  const data = await readJson(res);
  if (!res.ok) throw failure(res, data, fallback);
  return data;
}

export async function extractText(file) {
  const body = new FormData(); body.append('file', file);
  let res;
  try { res = await fetch(`${API_BASE}/api/extract-text`, { method: 'POST', body }); }
  catch { throw new Error(OFFLINE); }
  const data = await readJson(res);
  if (!res.ok) throw failure(res, data, 'Hindi mabasa ang file.');
  return data; // { name, textContent }
}

export const extractIntentions = (moduleText) => post('/api/extract-intentions', { moduleText }, 'Hindi nabasa ng AI ang module.');
export const draftIlaw = (payload) => post('/api/draft', payload, 'Hindi nabuo ang draft.');      // { confirmed, answers, moduleText, mode }
export const checkDraft = (payload) => post('/api/check-draft', payload, 'Hindi gumana ang check.'); // { draft, confirmed, mode, moduleText }
export const reviewDraft = (draft) => post('/api/review-draft', { draft }, 'Hindi gumana ang AI review.');

export async function getHealth() {
  try { const r = await fetch(`${API_BASE}/api/health`); return r.ok ? await r.json() : null; } catch { return null; }
}

// `draft` = the ILAW draft; `logos` = { left, right } small data URLs kept in the browser (they never go through the AI).
export async function exportDocx(draft, logos) {
  let res;
  try { res = await fetch(`${API_BASE}/api/export-docx`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...draft, logos }) }); }
  catch { throw new Error(OFFLINE); }
  if (!res.ok) throw failure(res, await readJson(res), 'Hindi nagawa ang DOCX file.');

  const blob = await res.blob();
  const match = (res.headers.get('Content-Disposition') || '').match(/filename="?([^";]+)"?/i);
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement('a'), { href: url, download: match?.[1] || 'Bear-Light-Lesson-Plan.docx' });
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
