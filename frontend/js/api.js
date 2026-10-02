// ALL network calls live here. Backend = FastAPI (see backend/ in the repo).
// Same-origin when FastAPI serves the page (port 8000); otherwise talk to localhost:8000.
const API_BASE = location.port === '8000' ? '' : 'http://localhost:8000';

export async function generateDLL(formData) {
  let res;
  try {
    res = await fetch(`${API_BASE}/api/generate-dll`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData),
    });
  } catch {
    throw new Error('Hindi maabot ang backend. Siguraduhing tumatakbo ang FastAPI sa ' + API_BASE);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Hindi matagumpay ang pagbuo ng DLL.');
  return data; // DLLData
}

export async function extractText(file) {
  const body = new FormData(); body.append('file', file);
  const res = await fetch(`${API_BASE}/api/extract-text`, { method: 'POST', body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Hindi mabasa ang file.');
  return data; // { name, textContent }
}

export async function exportDocx(dll) {
  const res = await fetch(`${API_BASE}/api/export-docx`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dll) });
  if (!res.ok) throw new Error('Hindi ma-export ang DOCX.');
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: `${dll.title.replace(/[^\w-]+/g, '_')}.docx` });
  a.click(); URL.revokeObjectURL(url);
}

export async function getHealth() {
  try { const r = await fetch(`${API_BASE}/api/health`); return r.ok ? await r.json() : null; } catch { return null; }
}

export async function checkCompliance(dll) {
  try {
    const r = await fetch(`${API_BASE}/api/check-compliance`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dll) });
    return r.ok ? await r.json() : null;
  } catch { return null; }
}