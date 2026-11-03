// Cards 1-4 of the questionnaire. No network calls here (main.js does those).
import { $, esc } from './utils.js';

const GROUPS = [['competencies', 'Learning Competency'], ['standards', 'Curriculum Standards (content / performance)'], ['objectives', 'Learning Objectives'], ['references', 'References']];
const HEADER_KEYS = ['lessonTitle', 'learningArea', 'teacherName', 'gradeSection', 'noOfSessions', 'schoolName', 'division', 'region', 'teachingDates'];
const REQUIRED = { learningArea: 'Learning Area/s', teacherName: 'Name of Teacher/s', gradeSection: 'Grade Level and Section', noOfSessions: 'No. of Sessions' };  // Lesson Title may be filled from the module
let items = {};            // group -> [{ text, checked: bool[] }]  (weekly: checked[0]; daily: 5 flags, except references)
let mode = 'weekly';
let refsDefault = '';

const isDaily = (g) => mode === 'daily' && g !== 'references';
const blank = (g, on) => (isDaily(g) ? [false, false, false, false, false] : [on]);
const calm = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// One page, cards revealed in order. Later cards stay hidden until the card before them is done.
export function reveal(id) {
  const el = $(id); el.hidden = false;
  el.scrollIntoView({ behavior: calm() ? 'auto' : 'smooth', block: 'start' });
}
export const hide = (...ids) => ids.forEach(id => { $(id).hidden = true; });

// Current text of every header field (read fresh: the header card stays editable the whole time).
export const readHeader = () => Object.fromEntries(HEADER_KEYS.map(k => [k, $(k).value.trim()]));

export function readStep1() {
  const header = readHeader(), file = $('moduleFile').files[0];
  HEADER_KEYS.forEach(k => $(k).removeAttribute('aria-invalid'));
  const missing = Object.keys(REQUIRED).filter(k => !header[k]);
  if (missing.length) {
    missing.forEach(k => $(k).setAttribute('aria-invalid', 'true')); $(missing[0]).focus();
    throw new Error('Punan muna ang: ' + missing.map(k => REQUIRED[k]).join(', ') + '.');
  }
  if (!file) { $('moduleFile').focus(); throw new Error('Kailangan ang module. I-upload muna ang file.'); }
  return { mode: $('mode').value, header, file };
}

function draw() {
  $('candidates').innerHTML = GROUPS.map(([g, label]) => {
    const rows = items[g].map((it, i) => isDaily(g)
      ? `<div class="pick"><span>${esc(it.text)}</span><span class="pickdays">${it.checked.map((on, d) => `<label><input type="checkbox" data-g="${g}" data-i="${i}" data-d="${d}"${on ? ' checked' : ''}> D${d + 1}</label>`).join('')}</span></div>`
      : `<label class="pick"><input type="checkbox" data-g="${g}" data-i="${i}" data-d="0"${it.checked[0] ? ' checked' : ''}><span>${esc(it.text)}</span></label>`).join('');
    return `<fieldset class="group"><legend>${label}</legend>${rows || '<p class="hint">Walang nakita sa module.</p>'}
      <div class="addrow"><input class="field" id="add-${g}" placeholder="Magdagdag ng sarili mo (mamarkahan bilang Na-edit ng guro)" aria-label="Magdagdag sa ${esc(label)}"><button type="button" class="btn soft" data-add="${g}">Idagdag</button></div></fieldset>`;
  }).join('');
}

export function renderCandidates(cands, m) {
  mode = m; items = {};
  for (const [g] of GROUPS) items[g] = (cands[g] || []).map(text => ({ text, checked: blank(g, true) }));
  refsDefault = items.references.map(x => x.text).join('\n');
  $('dropped').textContent = cands.dropped ? `${cands.dropped} na sipi ang inalis ng sistema dahil hindi eksaktong makita sa module.` : '';
  $('confirmBox').checked = false;
  if (cands.topic?.[0] && !$('lessonTitle').value.trim()) $('lessonTitle').value = cands.topic[0];
  draw();
}

export function initCandidateEvents() {
  $('candidates').addEventListener('change', e => {
    const t = e.target, it = items[t.dataset.g]?.[Number(t.dataset.i)];
    if (it) it.checked[Number(t.dataset.d)] = t.checked;
  });
  $('candidates').addEventListener('click', e => {
    const g = e.target.dataset.add; if (!g) return;
    const text = $('add-' + g).value.trim(); if (!text) return;
    items[g].push({ text, checked: blank(g, true) }); draw();
  });
}

export function readConfirmed() {
  if (!$('confirmBox').checked) throw new Error('Lagyan ng tsek ang kumpirmasyon bago magpatuloy.');
  const out = {};
  for (const [g] of GROUPS) out[g] = isDaily(g) ? [0, 1, 2, 3, 4].map(d => items[g].filter(it => it.checked[d]).map(it => it.text)) : items[g].filter(it => it.checked[0]).map(it => it.text);
  const flat = (g) => (isDaily(g) ? out[g].flat() : out[g]);
  if (!flat('competencies').length || !flat('objectives').length) throw new Error('Pumili ng kahit isang Learning Competency at isang Learning Objective.');
  return out;
}

function addSession(text = '') {
  const n = $('flow-list').children.length + 1;
  $('flow-list').insertAdjacentHTML('beforeend', `<label class="cell"><span>Sesyon ${n}</span><textarea rows="3"></textarea></label>`);
  $('flow-list').lastElementChild.querySelector('textarea').value = text;
}

export function initAnswers(noOfSessions) {
  const n = Math.min(10, Math.max(1, parseInt(noOfSessions, 10) || 1));
  if (!$('flow-list').children.length) for (let i = 0; i < n; i++) addSession();
  if (!$('references').value) $('references').value = refsDefault;
}

export function initAnswerEvents() {
  $('add-session-btn').onclick = () => addSession();
  $('na-btn').onclick = () => { $('integration').value = 'N/A'; };
}

export function readAnswers(header) {
  const v = (id) => $(id).value.trim();
  const refs = v('references');
  return { ...header, preLesson: v('preLesson'), flow: [...document.querySelectorAll('#flow-list textarea')].map(t => t.value.trim()).filter(Boolean),
    learningResources: v('learningResources'), integration: v('integration'), formative: v('formative'), extendedLearning: v('extendedLearning'),
    learnerContext: v('learnerContext'), reflections: v('reflections'), references: refs === refsDefault ? '' : refs };
}
