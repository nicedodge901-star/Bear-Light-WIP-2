import { $ } from './utils.js';
import { extractText } from './api.js';
import { GRADE_LEVELS, SUBJECT_AREAS, SAMPLE_PROMPTS } from './data.js';

let attachedFile = null;
const logos = { leftLogo: '', rightLogo: '' };
const FIELDS = ['gradeLevel','subjectArea','quarter','weekNumber','topic','schoolName','teacherName','region','division','teachingDates','noOfSessions','references','declarationOfAiUse'];

function fillSelect(id, items) { $(id).innerHTML = items.map(v => `<option>${v}</option>`).join(''); }

export function initForm(onSubmit) {
  fillSelect('gradeLevel', GRADE_LEVELS);
  fillSelect('subjectArea', SUBJECT_AREAS);
  fillSelect('weekNumber', Array.from({ length: 10 }, (_, i) => `Week ${i + 1}`));

  $('samples').innerHTML = SAMPLE_PROMPTS.map((s, i) => `<button type="button" class="chip" data-i="${i}">${s.label}</button>`).join('');
  $('samples').addEventListener('click', e => {
    const s = SAMPLE_PROMPTS[e.target.dataset.i]; if (!s) return;
    ['gradeLevel','subjectArea','quarter','weekNumber','topic'].forEach(k => ($(k).value = s[k]));
  });

  // Reference file: the backend extracts text from PDF/DOCX/PPTX; plain text is read here.
  $('refFile').addEventListener('change', async e => {
    const f = e.target.files[0]; attachedFile = null; $('refFileNote').textContent = '';
    if (!f) return;
    if (f.size > 20 * 1024 * 1024) { $('refFileNote').textContent = 'Masyadong malaki ang file (max 20MB).'; e.target.value = ''; return; }
    $('refFileNote').textContent = 'Binabasa ang file...';
    try {
      const { textContent } = await extractText(f);
      attachedFile = { name: f.name, type: f.type, size: f.size, textContent };
      $('refFileNote').textContent = `Nakakabit: ${f.name} (${textContent.length} chars na nabasa)`;
    } catch (err) { $('refFileNote').textContent = err.message; e.target.value = ''; }
  });

  // Logos are stored as data URLs (max 5MB each, png/jpg/gif so DOCX export works).
  for (const id of ['leftLogo', 'rightLogo']) {
    $(id).addEventListener('change', e => {
      const f = e.target.files[0]; logos[id] = ''; if (!f) return;
      if (f.size > 5 * 1024 * 1024) { alert('Pakipili ang larawan na mas maliit sa 5MB.'); e.target.value = ''; return; }
      const r = new FileReader(); r.onload = () => (logos[id] = r.result); r.readAsDataURL(f);
    });
  }

  $('dll-form').addEventListener('submit', async e => {
    e.preventDefault();
    const data = Object.fromEntries(FIELDS.map(k => [k, $(k).value.trim()]));
    $('form-error').hidden = true;
    if (!data.topic) { $('form-error').textContent = 'Pakilagay ang paksa o competency.'; $('form-error').hidden = false; return; }
    if (attachedFile) data.attachedFile = attachedFile;
    data.leftLogoUrl = logos.leftLogo; data.rightLogoUrl = logos.rightLogo;
    data.provider = 'auto';
    const btn = $('generate-btn'); btn.disabled = true; btn.textContent = 'Gumagawa ng DLL...';
    try { await onSubmit(data); }
    catch (err) { $('form-error').textContent = err.message; $('form-error').hidden = false; }
    finally { btn.disabled = false; btn.textContent = 'Buuin ang DLL'; }
  });
}
