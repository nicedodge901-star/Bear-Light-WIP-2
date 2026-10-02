// Entry point: wires the modules together. Keep logic OUT of here.
import { $, esc } from './utils.js';
import { SAMPLE_DLL } from './data.js';
import { initForm } from './form.js';
import { generateDLL } from './api.js';
import { render, getCurrent, toggleEdit, asPlainText, showReview } from './preview.js';
import { exportDocx, getHealth, reviewDll } from './api.js';
import { loadHistory, saveHistory, upsert } from './history.js';

let saved = loadHistory();

function renderHistory() {
  const q = $('history-search').value.toLowerCase();
  const items = saved.filter(d => `${d.title} ${d.header.learningArea} ${d.header.gradeLevel}`.toLowerCase().includes(q));
  $('history-count').textContent = saved.length;
  $('history-list').innerHTML = items.length
    ? items.map(d => `<li data-id="${esc(d.id)}"><span><strong>${esc(d.title)}</strong><br><small>${esc(d.header.gradeLevel)} · ${esc(d.dateCreated)}</small></span><button type="button" class="btn btn-ghost danger" data-del="${esc(d.id)}">Burahin</button></li>`).join('')
    : '<li>Walang naitabing DLL.</li>';
}

function persist() { if (!saveHistory(saved)) alert('Puno na ang storage ng browser. Burahin ang ilang lumang DLL.'); renderHistory(); }

async function refreshStatus() {
  const h = await getHealth(), el = $('provider-status');
  el.innerHTML = !h ? '' : Object.entries(h.providers).filter(([, v]) => v.status !== 'unconfigured').map(([n, v]) =>
    `<span class="pchip" title="${esc(n)}: ${esc(v.status)}${v.flags.length ? ' (' + esc(v.flags.join(', ')) + ')' : ''}"><span class="dot dot-${esc(v.status)}" aria-hidden="true"></span>${esc(n)}<span class="sr-only"> ${esc(v.status)}</span></span>`).join('');
}

initForm(async (formData) => {
  try {
    render(await generateDLL(formData));
    $('dll-output-container').scrollIntoView({ behavior: 'smooth' });
  } finally { refreshStatus(); }
});

$('edit-btn').onclick = toggleEdit;
$('docx-btn').onclick = async () => { const d = getCurrent(); if (!d) return; try { await exportDocx(d); } catch (e) { alert(e.message); } };
$('review-btn').onclick = async () => {
  const d = getCurrent(); if (!d) return;
  const b = $('review-btn'); b.disabled = true; b.textContent = 'Sinusuri...';
  try { showReview(await reviewDll(d)); } catch (e) { alert(e.message); }
  finally { b.disabled = false; b.textContent = 'AI review'; }
};
$('print-btn').onclick = () => window.print();
$('copy-btn').onclick = async () => { await navigator.clipboard.writeText(asPlainText()); $('copy-btn').textContent = 'Nakopya!'; setTimeout(() => ($('copy-btn').textContent = 'Copy text'), 1500); };
// Logos are dropped from saved history: base64 would blow the ~5MB localStorage quota.
$('save-btn').onclick = () => { const d = getCurrent(); if (d) { saved = upsert(saved, { ...d, header: { ...d.header, leftLogoUrl: '', rightLogoUrl: '' } }); persist(); } };

$('history-btn').onclick = () => { $('history-drawer').hidden = false; renderHistory(); };
$('history-close').onclick = () => ($('history-drawer').hidden = true);
$('history-search').oninput = renderHistory;
$('history-clear').onclick = () => { if (confirm('Burahin ang lahat ng naitabing DLL?')) { saved = []; persist(); } };
$('history-list').onclick = (e) => {
  const del = e.target.dataset.del;
  if (del) { saved = saved.filter(d => d.id !== del); persist(); return; }
  const li = e.target.closest('li[data-id]');
  if (li) { render(saved.find(d => d.id === li.dataset.id)); $('history-drawer').hidden = true; }
};

render(SAMPLE_DLL);
renderHistory();
refreshStatus();
