// ALL network calls live here. Backend = FastAPI (see backend/).
// Same-origin when FastAPI serves the page (port 8000); otherwise talk to localhost:8000.
const API_BASE = location.port === '8000' ? '' : 'http://localhost:8000';

async function post(path, body, fallback) {
  let res;
  try { res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
  catch { throw new Error('Hindi maabot ang backend. Siguraduhing tumatakbo ang FastAPI sa ' + (API_BASE || location.origin)); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || fallback);
  return data;
}

export async function extractText(file) {
  const body = new FormData(); body.append('file', file);
  let res;
  try { res = await fetch(`${API_BASE}/api/extract-text`, { method: 'POST', body }); }
  catch { throw new Error('Hindi maabot ang backend. Siguraduhing tumatakbo ang FastAPI.'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Hindi mabasa ang file.');
  return data; // { name, textContent }
}

export const extractIntentions = (moduleText) => post('/api/extract-intentions', { moduleText }, 'Hindi nabasa ng AI ang module.');
export const draftIlaw = (payload) => post('/api/draft', payload, 'Hindi nabuo ang draft.');      // { confirmed, answers, moduleText, mode }
export const checkDraft = (payload) => post('/api/check-draft', payload, 'Hindi gumana ang check.'); // { draft, confirmed, mode, moduleText }
export const reviewDraft = (draft) => post('/api/review-draft', { draft }, 'Hindi gumana ang AI review.');

export async function getHealth() {
  try { const r = await fetch(`${API_BASE}/api/health`); return r.ok ? await r.json() : null; } catch { return null; }
}

export async function exportDocx(draft) {
  let res;

  try {
    res = await fetch(`${API_BASE}/api/export-docx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draft)
    });
  } catch {
    throw new Error('Hindi maabot ang backend. Siguraduhing tumatakbo ang FastAPI.');
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || 'Hindi nagawa ang DOCX file.');
  }

  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] || 'Bear-Light-Lesson-Plan.docx';

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
}