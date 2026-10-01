import { $, esc, getPath, setPath } from './utils.js';
import { PROCEDURES, REFLECTION } from './data.js';

let current = null;
let editing = false;

const cell = (path) => `<span data-path="${path}">${esc(getPath(current, path))}</span>`;
const row = (label, path) => `<tr><th>${label}</th><td>${cell(path)}</td></tr>`;

const logo = (u) => (u && u.startsWith('data:image/') ? `<img src="${u.replace(/"/g, '')}" alt="Logo">` : '<span></span>');

export function getCurrent() { return current; }

export function render(dll) {
  current = dll;
  if (!dll) { $('preview').innerHTML = '<p class="empty">Wala pang DLL. Punan ang pormularyo at pindutin ang "Buuin ang DLL".</p>'; return; }
  const comps = (dll.objectives.learningCompetencies || []).map(c => `<li>${esc(c)}</li>`).join('');
  $('preview').innerHTML = `
    <div class="logos">${logo(dll.header.leftLogoUrl)}<h2>Daily Lesson Log</h2>${logo(dll.header.rightLogoUrl)}</div>
    <p class="meta">Provider: ${esc(dll.providerUsed)}${dll.fallbackOccurred ? ' (fallback)' : ''} · ${esc(dll.dateCreated)}</p>
    <h3>Header</h3>
    <table>
      ${row('Paaralan','header.schoolName')}${row('Guro','header.teacherName')}${row('Antas','header.gradeLevel')}
      ${row('Asignatura','header.learningArea')}${row('Term / Week','header.quarter')}${row('Petsa','header.teachingDates')}
      ${row('Division','header.division')}${row('Region','header.region')}${row('Sesyon','header.noOfSessions')}
      ${row('References','header.references')}${row('Declaration of AI use','header.declarationOfAiUse')}
    </table>
    <h3>Intentions</h3>
    <table>${row('Content Standard','objectives.contentStandard')}${row('Performance Standard','objectives.performanceStandard')}
      <tr><th>Learning Competencies</th><td><ul>${comps}</ul></td></tr></table>
    <h3>Nilalaman</h3>
    <table>${row('Paksa','content.topic')}${row('Subtopic','content.subtopic')}${row('Values','content.integrationValues')}${row('HOTS','content.hotsSkills')}</table>
    <h3>Learning Resources</h3>
    <table>${row('Teacher\'s Guide','resources.teacherGuidePages')}${row('Learner\'s Materials','resources.learnerMaterialPages')}
      ${row('Textbook','resources.textbookPages')}${row('Karagdagang Kagamitan','resources.additionalMaterials')}</table>
    <h3>Learning Experience</h3>
    <table>${PROCEDURES.map(([k, label]) => row(label, `procedures.${k}`)).join('')}</table>
    <h3>Remarks</h3><table>${row('Tala','remarks.notes')}</table>
    <h3>Reflection</h3><table>${REFLECTION.map(([k, label]) => row(label, `reflection.${k}`)).join('')}</table>`;
  setEditing(false);
}

function setEditing(on) {
  editing = on;
  document.querySelectorAll('#preview [data-path]').forEach(el => (el.contentEditable = on ? 'true' : 'false'));
  $('edit-btn').textContent = on ? 'Done editing' : 'Edit';
}

export function toggleEdit() {
  if (editing) document.querySelectorAll('#preview [data-path]').forEach(el => setPath(current, el.dataset.path, el.innerText.trim()));
  setEditing(!editing);
}

export function asPlainText() { return $('preview').innerText; }
