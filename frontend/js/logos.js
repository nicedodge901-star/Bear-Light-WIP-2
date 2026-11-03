// Letterhead logos. They stay in the browser: shrunk to a small PNG/JPEG data URL, shown in the preview,
// and sent ONLY to /api/export-docx. They never go to the AI.
import { $ } from './utils.js';

const OK_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_FILE = 5 * 1024 * 1024;   // raw upload
const MAX_H = 240;                  // px after shrinking: plenty for a 0.8in logo at print quality
const SAFE = /^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/;
const logos = { left: '', right: '' };

export const getLogos = () => ({ ...logos });
export const safeLogo = (url) => (SAFE.test(url || '') ? url : '');   // only our own canvas output ever passes

function say(msg) { const el = $('logo-err'); el.textContent = msg || ''; el.hidden = !msg; }

async function shrink(file) {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image(); img.src = url; await img.decode();
    const k = Math.min(1, MAX_H / img.naturalHeight, (MAX_H * 2) / img.naturalWidth);
    const c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(img.naturalWidth * k)); c.height = Math.max(1, Math.round(img.naturalHeight * k));
    const ctx = c.getContext('2d');
    const jpeg = file.type === 'image/jpeg';
    if (jpeg) { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height); }   // JPEG has no transparency
    ctx.drawImage(img, 0, 0, c.width, c.height);
    const out = jpeg ? c.toDataURL('image/jpeg', 0.9) : c.toDataURL('image/png');
    if (!SAFE.test(out)) throw new Error('bad output');
    return out;
  } finally { URL.revokeObjectURL(url); }
}

function paint(cell, url) {
  const img = cell.querySelector('img'), none = cell.querySelector('small'), rm = cell.querySelector('.logo-remove');
  img.hidden = !url; none.hidden = !!url; rm.hidden = !url;
  if (url) img.src = url; else img.removeAttribute('src');
}

export function initLogos(onChange) {
  document.querySelectorAll('.logo-cell').forEach(cell => {
    const side = cell.dataset.side, input = cell.querySelector('input[type=file]');
    input.addEventListener('change', async () => {
      const file = input.files[0]; input.value = '';   // reset so choosing the same file again still fires
      if (!file) return;
      say('');
      if (!OK_TYPES.includes(file.type)) return say('PNG, JPG o WebP lang ang tinatanggap na logo.');
      if (file.size > MAX_FILE) return say('Masyadong malaki ang larawan (hanggang 5MB).');
      try { logos[side] = await shrink(file); paint(cell, logos[side]); onChange(); }
      catch { say('Hindi mabasa ang larawan. Subukan ang ibang file.'); }
    });
    cell.querySelector('.logo-remove').addEventListener('click', () => { say(''); logos[side] = ''; paint(cell, ''); onChange(); });
  });
}
