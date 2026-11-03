// The draft overlay: renders the draft in the school ILAW template layout
// (letterhead, HEADER, Intentions., Learning Experience., Assessment., Ways Forward) so it matches the DOCX export.
import { $, esc, getPath, setPath } from './utils.js';
import { getLogos, safeLogo } from './logos.js';

let current = null, editing = false;
const SRC = { extracted: 'Mula sa module', teacher: 'Isinulat ng guro', 'ai-organized': 'Inayos ng AI', 'teacher-edited': 'Na-edit ng guro' };
const LABEL = { pass: 'Kumpleto ang istruktura', review: 'May dapat suriin', fail: 'May kulang' };
const TAG = { fail: 'Kulang', warn: 'Suriin' };

const text = (d, path) => String(getPath(d, path)?.text || '').trim();
const tag = (leaf) => (leaf && leaf.source ? `<span class="src src-${esc(leaf.source)} no-print">${esc(SRC[leaf.source] || leaf.source)}${leaf.grammarFixed ? ' + grammar' : ''}</span>` : '');
const editable = (d, path) => `<span class="val" data-path="${path}.text">${esc(getPath(d, path)?.text)}</span>${tag(getPath(d, path))}`;
const row = (label, field, inner) => `<tr data-field="${field}"><th>${label}</th><td>${inner}</td></tr>`;
const band = (title) => `<tr><th class="band" colspan="2">${title}</th></tr>`;
const dayTable = (days) => `<table class="days"><tr>${[1, 2, 3, 4, 5].map(i => `<th>Day ${i}</th>`).join('')}</tr><tr>${days.map(t => `<td><span class="val">${esc(t)}</span></td>`).join('')}</tr></table>`;

// Logos + DepEd lines. Only shown when the teacher gave a logo, school, division or region (same rule as the DOCX).
function letterheadHtml(d) {
  const L = getLogos(), left = safeLogo(L.left), right = safeLogo(L.right);   // safeLogo only passes our own canvas output, so it is safe inside src=""
  const [school, division, region] = ['schoolName', 'division', 'region'].map(k => text(d, 'header.' + k));
  if (!(left || right || school || division || region)) return '';
  const img = (src) => (src ? `<img src="${src}" alt="">` : '');
  return `<div class="letterhead"><div class="lh-logo">${img(left)}</div>
    <div class="lh-text"><p>Republic of the Philippines</p><p><strong>Department of Education</strong></p>${region ? `<p>${esc(region)}</p>` : ''}${division ? `<p>${esc(division)}</p>` : ''}${school ? `<p class="lh-school">${esc(school)}</p>` : ''}</div>
    <div class="lh-logo lh-right">${img(right)}</div></div>`;
}

export function draftToHtml(d) {
  const locked = (label, path) => {  // competency / standards / objectives: shown, never editable
    const leaf = getPath(d, path) || {};
    return (label ? `<div class="sub"><strong>${label}</strong></div>` : '') + (leaf.days ? dayTable(leaf.days) : `<span class="val">${esc(leaf.text)}</span>`) + tag(leaf);
  };
  const flow = getPath(d, 'experience.flow') || [];
  const flowHtml = flow.length ? flow.map((f, i) => `<div class="sess"><strong>Sesyon ${i + 1}</strong><br><span class="val" data-path="experience.flow.${i}.text">${esc(f.text)}</span>${tag(f)}</div>`).join('') : '<span class="val"></span>';
  const dates = text(d, 'header.teachingDates') ? row('Teaching Dates', 'header.teachingDates', editable(d, 'header.teachingDates')) : '';
  return `${letterheadHtml(d)}
    <table>
      ${row('Lesson Title', 'header.lessonTitle', editable(d, 'header.lessonTitle'))}
      ${row('Learning Area/s', 'header.learningArea', editable(d, 'header.learningArea'))}
      ${row('Name of Teacher/s', 'header.teacherName', editable(d, 'header.teacherName'))}
      ${row('Grade Level and Section', 'header.gradeSection', editable(d, 'header.gradeSection'))}
      ${row('No. of Sessions', 'header.noOfSessions', editable(d, 'header.noOfSessions'))}
      ${dates}
      ${row('References <small>(books, websites, toolkits, etc.)</small>', 'header.references', editable(d, 'header.references'))}
    </table>
    <table>${band('Intentions.')}
      ${row('Learning Competency and Curriculum Standards:', 'intentions.competencies intentions.standards', locked('Learning Competency', 'intentions.competencies') + locked('Curriculum Standards', 'intentions.standards'))}
      ${row('Learning Objectives:', 'intentions.objectives', locked('', 'intentions.objectives'))}
      ${row('Learner Context:', 'intentions.learnerContext', editable(d, 'intentions.learnerContext'))}
    </table>
    <table>${band('Learning Experience.')}
      ${row('Pre-Lesson:', 'experience.preLesson', editable(d, 'experience.preLesson'))}
      ${row('Flow:', 'experience.flow', flowHtml)}
      ${row('Learning Resources:', 'experience.learningResources', editable(d, 'experience.learningResources'))}
      ${row('Opportunities for integration:', 'experience.integration', editable(d, 'experience.integration'))}
    </table>
    <table>${band('Assessment.')}
      ${row('Formative Assessment:', 'assessment.formative', editable(d, 'assessment.formative'))}
    </table>
    <table>${band('Ways Forward')}
      ${row('Extended learning opportunities:', 'waysForward.extendedLearning', editable(d, 'waysForward.extendedLearning'))}
      ${row('Reflections:', 'waysForward.reflections', editable(d, 'waysForward.reflections'))}
    </table>
    <p class="prepared"><strong>Prepared by:</strong> ${esc(text(d, 'header.teacherName'))}</p>
    <p class="disclaimer no-print">Draft lang ito. Ang guro ang may pananagutan sa nilalaman: suriin bago gamitin.</p>`;
}

export function checkHtml(c, notes = []) {
  if (!c) return '';
  const items = c.flags.map(f => `<li><span class="comp-tag comp-${f.level}">${TAG[f.level]}</span> <strong>${esc(f.field)}:</strong> ${esc(f.message)}</li>`).join('');
  const nt = notes.map(n => `<li><span class="comp-tag comp-warn">Paalala</span> <strong>${esc(n.field)}:</strong> ${esc(n.message)}</li>`).join('');
  return `<section class="compliance no-print" aria-label="Compliance check">
    <p class="comp-head"><strong>Structure check:</strong> <span class="comp-badge comp-${c.status}">${LABEL[c.status]}</span> <span>${c.fail} kulang · ${c.warn} suriin</span></p>
    ${items || nt ? `<ul>${items}${nt}</ul>` : ''}<p class="comp-note">${esc(c.note)}</p></section>`;
}

function mark(c) {
  for (const f of c?.flags || []) document.querySelectorAll(`#print-doc tr[data-field~="${f.field}"]`).forEach(tr => {
    if (f.level === 'fail') { tr.classList.remove('flag-warn'); tr.classList.add('flag-fail'); } else if (!tr.classList.contains('flag-fail')) tr.classList.add('flag-warn');
  });
}

export function render(draft, check, notes = []) {
  current = draft;
  $('preview-notes').innerHTML = checkHtml(check, notes);
  $('print-doc').innerHTML = draftToHtml(draft);
  setEditing(false); mark(check);
}

export const getCurrent = () => current;

// Swap only the letterhead (logo changed, or the header card was edited) without touching anything the teacher typed in the draft.
export function refreshLetterhead() {
  if (!current) return;
  const html = letterheadHtml(current), old = $('print-doc').querySelector('.letterhead');
  if (old && html) old.outerHTML = html;
  else if (old) old.remove();
  else if (html) $('print-doc').insertAdjacentHTML('afterbegin', html);
}

// School / division / region live in the header card. Pull their latest values into the draft whenever it is opened.
export function syncLetterhead(header) {
  if (!current) return;
  for (const k of ['schoolName', 'division', 'region']) current.header[k] = { text: header[k] || '', source: 'teacher' };
  refreshLetterhead();
}

export const isEditing = () => editing;

function setEditing(on) {
  editing = on;
  document.querySelectorAll('#print-doc [data-path]').forEach(el => (el.contentEditable = on ? 'true' : 'false'));
  $('edit-btn').textContent = on ? 'Done editing' : 'Edit';
}

// Locked fields (competency, standards, objectives) have no data-path, so they can never be edited here.
export function toggleEdit(onDone) {
  if (!editing) return setEditing(true);
  document.querySelectorAll('#print-doc [data-path]').forEach(el => setPath(current, el.dataset.path, (el.innerText ?? el.textContent).trim()));
  setEditing(false);
  onDone(current);
}

export function showReview(r) {
  $('preview-notes').querySelector('.ai-review')?.remove();
  const V = { ok: 'Walang nakitang problema', review: 'May dapat suriin', problems: 'May nakitang problema' };
  const items = r.flags.map(f => `<li><span class="comp-tag comp-${f.level}">${TAG[f.level]}</span> <strong>${esc(f.field)}:</strong> ${esc(f.message)}
    ${f.quote ? `<div class="comp-quote">"${esc(f.quote)}"${f.quote_verified ? '' : ' <em>(hindi makita ang sipi na ito sa draft: mag-ingat)</em>'}</div>` : ''}</li>`).join('');
  const html = `<section class="compliance ai-review no-print" aria-label="AI review">
    <p class="comp-head"><strong>AI review (advisory):</strong> <span class="comp-badge comp-${r.verdict === 'ok' ? 'pass' : r.verdict === 'problems' ? 'fail' : 'review'}">${V[r.verdict]}</span> <span>${r.fail} kulang · ${r.warn} suriin</span></p>
    ${items ? `<ul>${items}</ul>` : ''}<p class="comp-note">Binuo ng AI; maaaring magkamali. Basahin ang mismong teksto bago magdesisyon.</p></section>`;
  const first = $('preview-notes').querySelector('.compliance');
  first ? first.insertAdjacentHTML('afterend', html) : $('preview-notes').insertAdjacentHTML('afterbegin', html);
}

export function draftToText(d) {
  const t = (p) => getPath(d, p)?.text || '';
  const days = (p) => (getPath(d, p)?.days || []).map((x, i) => `Day ${i + 1}: ${x}`).join('\n');
  const lock = (p) => (getPath(d, p)?.days ? days(p) : t(p));
  const flow = (getPath(d, 'experience.flow') || []).map((f, i) => `Sesyon ${i + 1}: ${f.text}`).join('\n');
  const opt = (label, p) => (t(p).trim() ? [`${label}: ${t(p)}`] : []);
  return [`HEADER`, ...opt('School', 'header.schoolName'), ...opt('Division', 'header.division'), ...opt('Region', 'header.region'),
    `Lesson Title: ${t('header.lessonTitle')}`, `Learning Area/s: ${t('header.learningArea')}`, `Name of Teacher/s: ${t('header.teacherName')}`,
    `Grade Level and Section: ${t('header.gradeSection')}`, `No. of Sessions: ${t('header.noOfSessions')}`, ...opt('Teaching Dates', 'header.teachingDates'), `References: ${t('header.references')}`, '',
    'Intentions.', `Learning Competency:\n${lock('intentions.competencies')}`, `Curriculum Standards:\n${lock('intentions.standards')}`, `Learning Objectives:\n${lock('intentions.objectives')}`,
    `Learner Context: ${t('intentions.learnerContext')}`, '', 'Learning Experience.', `Pre-Lesson: ${t('experience.preLesson')}`, `Flow:\n${flow}`,
    `Learning Resources: ${t('experience.learningResources')}`, `Opportunities for integration: ${t('experience.integration')}`, '', 'Assessment.',
    `Formative Assessment: ${t('assessment.formative')}`, '', 'Ways Forward', `Extended learning opportunities: ${t('waysForward.extendedLearning')}`,
    `Reflections: ${t('waysForward.reflections')}`, '', `Prepared by: ${t('header.teacherName')}`].join('\n');
}
