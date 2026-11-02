// Entry point: wires the steps together. Keep logic OUT of here.
import { $, esc } from './utils.js';
import { extractText, extractIntentions, draftIlaw, checkDraft, reviewDraft, exportDocx, getHealth } from './api.js';
import * as W from './wizard.js';
import { render, getCurrent, toggleEdit, showReview, draftToText } from './preview.js';

const state = { mode: 'weekly', header: {}, moduleText: '', confirmed: null, notes: [] };

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

W.initCandidateEvents(); W.initAnswerEvents();

// Step 1 -> 2: read the module, pull VERIFIED quotes
$('form1').addEventListener('submit', e => {
  e.preventDefault();
  busy($('read-btn'), 'Binabasa ang module...', async () => {
    const s1 = W.readStep1();
    const { textContent } = await extractText(s1.file);
    const cands = await extractIntentions(textContent);
    Object.assign(state, { mode: s1.mode, header: s1.header, moduleText: textContent });
    W.renderCandidates(cands, s1.mode); W.showStep(2);
  }, 'err1').finally(refreshStatus);
});

// Step 2 -> 3: teacher confirms
$('back1-btn').onclick = () => W.showStep(1);
$('to-answers-btn').onclick = () => {
  try { say('err2', ''); state.confirmed = W.readConfirmed(); W.initAnswers(state.header.noOfSessions); W.showStep(3); } catch (e) { say('err2', e.message); }
};

// Step 3 -> 4: organize, grammar, check
$('back2-btn').onclick = () => W.showStep(2);
$('form3').addEventListener('submit', e => {
  e.preventDefault();
  busy($('draft-btn'), 'Inaayos ang draft...', async () => {
    const answers = W.readAnswers({ ...state.header, lessonTitle: $('lessonTitle').value.trim() });
    const r = await draftIlaw({ confirmed: state.confirmed, answers, moduleText: state.moduleText, mode: state.mode });
    state.notes = r.notes || [];
    render(r.draft, r.check, state.notes); W.showStep(4);
  }, 'err3').finally(refreshStatus);
});

// Step 4 tools
$('back3-btn').onclick = () => W.showStep(3);
$('edit-btn').onclick = () => toggleEdit(async draft => {
  try { say('err4', ''); render(draft, await checkDraft({ draft, confirmed: state.confirmed, mode: state.mode, moduleText: state.moduleText }), state.notes); }
  catch (e) { say('err4', e.message); }
});
$('review-btn').onclick = () => busy($('review-btn'), 'Sinusuri...', async () => showReview(await reviewDraft(getCurrent())), 'err4');
$('print-btn').onclick = () => window.print();
$('export-docx-btn').onclick = () =>
  busy(
    $('export-docx-btn'),
    'Gumagawa ng DOCX...',
    async () => exportDocx(getCurrent()),
    'err4'
  );
$('copy-btn').onclick = async () => { await navigator.clipboard.writeText(draftToText(getCurrent())); $('copy-btn').textContent = 'Nakopya!'; setTimeout(() => ($('copy-btn').textContent = 'Copy text'), 1500); };

refreshStatus();