// Entry point: wires the cards together. Keep logic OUT of here.
import { $, esc } from './utils.js';
import { extractText, extractIntentions, draftIlaw, checkDraft, reviewDraft, exportDocx, getHealth } from './api.js';
import * as W from './wizard.js';
import { initLogos, getLogos } from './logos.js';
import { render, getCurrent, toggleEdit, showReview, draftToText, syncLetterhead, refreshLetterhead } from './preview.js';

const state = { mode: 'weekly', moduleText: '', confirmed: null, notes: [] };

const say = (id, msg) => { const el = $(id); el.textContent = msg || ''; el.hidden = !msg; };
async function busy(btn, label, fn, errId) {
  const old = btn.textContent; btn.disabled = true; btn.textContent = label; say(errId, '');
  try { await fn(); } catch (e) { say(errId, e.message); } finally { btn.disabled = false; btn.textContent = old; }
}

async function refreshStatus() {
  const h = await getHealth();
  $('provider-status').innerHTML = !h ? '' : Object.entries(h.providers).filter(([, v]) => v.status !== 'unconfigured').map(([n, v]) =>
    `<span class="pchip" title="${esc(n)}: ${esc(v.status)}"><span class="dot dot-${esc(v.status)}" aria-hidden="true"></span>${esc(n)}<span class="sr-only"> ${esc(v.status)}</span></span>`).join('');
}

// ---------- draft overlay ----------
const overlay = $('overlay');
let lastFocus = null;
const focusables = () => [...overlay.querySelectorAll('button:not([disabled]), [contenteditable="true"]')];

function openDraft() {
  syncLetterhead(W.readHeader());                 // school / division / region come from the header card
  say('err4', '');
  lastFocus = document.activeElement; overlay.hidden = false; document.body.classList.add('no-scroll');
  $('close-btn').focus();
}
function closeDraft() {
  overlay.hidden = true; document.body.classList.remove('no-scroll'); lastFocus?.focus?.();
}
document.addEventListener('keydown', e => {
  if (overlay.hidden) return;
  if (e.key === 'Escape') return closeDraft();
  if (e.key !== 'Tab') return;
  const f = focusables(); if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

// ---------- setup ----------
W.initCandidateEvents(); W.initAnswerEvents();
initLogos(refreshLetterhead);

// Card 2 -> 3: read the module, pull VERIFIED quotes
$('form1').addEventListener('submit', e => {
  e.preventDefault();
  busy($('read-btn'), 'Binabasa ang module...', async () => {
    const s1 = W.readStep1();
    const { textContent } = await extractText(s1.file);
    const cands = await extractIntentions(textContent);
    Object.assign(state, { mode: s1.mode, moduleText: textContent, confirmed: null });
    W.hide('card-answers'); W.renderCandidates(cands, s1.mode); W.reveal('card-confirm');   // a new module means the old confirmation no longer counts
  }, 'err1').finally(refreshStatus);
});

// Card 3 -> 4: teacher confirms
$('to-answers-btn').onclick = () => {
  try { say('err2', ''); state.confirmed = W.readConfirmed(); W.initAnswers(W.readHeader().noOfSessions); W.reveal('card-answers'); }
  catch (e) { say('err2', e.message); }
};

// Card 4 -> draft: organize, grammar, check
$('form3').addEventListener('submit', e => {
  e.preventDefault();
  busy($('draft-btn'), 'Inaayos ang draft...', async () => {
    if (!state.confirmed) throw new Error('Kumpirmahin muna ang mga sipi mula sa module (hakbang 3).');
    const answers = W.readAnswers(W.readHeader());
    const r = await draftIlaw({ confirmed: state.confirmed, answers, moduleText: state.moduleText, mode: state.mode });
    state.notes = r.notes || [];
    render(r.draft, r.check, state.notes);
    $('open-draft-btn').disabled = false; openDraft();
  }, 'err3').finally(refreshStatus);
});

// Draft tools
$('open-draft-btn').onclick = openDraft;
$('close-btn').onclick = closeDraft;
overlay.addEventListener('click', e => { if (e.target === overlay) closeDraft(); });
$('clear-btn').onclick = () => { if (confirm('Buburahin ang lahat ng nilagay mo at magsisimula muli. Ituloy?')) location.reload(); };
$('edit-btn').onclick = () => toggleEdit(async draft => {
  try { say('err4', ''); render(draft, await checkDraft({ draft, confirmed: state.confirmed, mode: state.mode, moduleText: state.moduleText }), state.notes); }
  catch (e) { say('err4', e.message); }
});
$('review-btn').onclick = () => busy($('review-btn'), 'Sinusuri...', async () => showReview(await reviewDraft(getCurrent())), 'err4');
$('print-btn').onclick = () => window.print();
$('export-docx-btn').onclick = () => busy($('export-docx-btn'), 'Gumagawa ng DOCX...', async () => exportDocx(getCurrent(), getLogos()), 'err4');
$('copy-btn').onclick = async () => {
  try { await navigator.clipboard.writeText(draftToText(getCurrent())); $('copy-btn').textContent = 'Nakopya!'; setTimeout(() => ($('copy-btn').textContent = 'Copy text'), 1500); }
  catch { say('err4', 'Hindi makopya. Piliin at kopyahin ang teksto nang mano-mano.'); }
};

refreshStatus();
