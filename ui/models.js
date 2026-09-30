// Measured cloud models (2026-09-30, blind judged): recommended ones by quality, then the ones we advise against.
// Quality dots follow clear errors per 10 captions on the 55 hardest shots: up to 0.4 = 5, 0.9 = 4, 1.9 = 3,
// 2.9 = 2, more = 1. Seconds and dollars are per caption and per 100 captions, rewrites with minimal reasoning.
import { $, esc } from './dom.js';
import { i18n, t } from './i18n.js';

const RECOMMENDED = [
  {
    name: 'GPT 6.1 Sol',
    maker: 'OpenAI',
    tag: 'best quality',
    quality: 5,
    seconds: 9,
    price: '1.50',
    clear: '0.0',
    minor: '1.5',
    described: 99,
    ids: { 'https://api.openai.com/v1': 'gpt-6.1-sol', 'https://openrouter.ai/api/v1': 'openai/gpt-6.1-sol' },
  },
  {
    name: 'Claude Opus 5.5',
    maker: 'Anthropic',
    tag: 'top quality',
    quality: 5,
    seconds: 13,
    price: '3.90',
    clear: '0.0',
    minor: '2.4',
    described: 98,
    ids: { 'https://openrouter.ai/api/v1': 'anthropic/claude-opus-5.5' },
  },
  {
    name: 'Gemini 3.8 Flash',
    maker: 'Google',
    tag: 'best price for quality',
    quality: 5,
    seconds: 12,
    price: '0.85',
    clear: '0.4',
    minor: '2.4',
    described: 93,
    ids: {
      'https://generativelanguage.googleapis.com/v1beta/openai': 'gemini-3.8-flash',
      'https://openrouter.ai/api/v1': 'google/gemini-3.8-flash',
    },
  },
  {
    name: 'Qwen 3.8 Max',
    maker: 'Alibaba',
    tag: 'slower, pricier',
    warn: true,
    quality: 4,
    seconds: 61,
    price: '2.95',
    clear: '0.7',
    minor: '2.5',
    described: 99,
    ids: { 'https://openrouter.ai/api/v1': 'qwen/qwen3.8-max-0902' },
  },
  {
    name: 'Grok 4.7',
    maker: 'xAI',
    quality: 4,
    seconds: 43,
    price: '3.45',
    clear: '0.7',
    minor: '3.3',
    described: 98,
    ids: { 'https://openrouter.ai/api/v1': 'x-ai/grok-4.7' },
  },
  {
    name: 'Muse Spark 1.3',
    maker: 'Meta',
    tag: '18+ confirmation',
    warn: true,
    note: 'OpenRouter runs it only after you confirm you are 18+ in your account settings. Hair color of a character is not offered.',
    quality: 4,
    seconds: 44,
    price: '2.25',
    clear: '0.7',
    minor: '3.3',
    described: 97,
    ids: { 'https://openrouter.ai/api/v1': 'meta/muse-spark-1.3' },
  },
  {
    name: 'GLM 5.3 FlashX',
    maker: 'Z.ai',
    tag: 'cheap and fast',
    note: 'More errors than the models above; check the captions.',
    quality: 3,
    seconds: 14,
    price: '0.36',
    clear: '1.9',
    minor: '3.1',
    described: 97,
    ids: { 'https://openrouter.ai/api/v1': 'z-ai/glm-5.3-flashx' },
  },
];

const NOT_RECOMMENDED = [
  {
    name: 'GLM 5V Turbo',
    maker: 'Z.ai',
    why: 'many minor errors, slow',
    quality: 3,
    seconds: 69,
    price: '2.55',
    clear: '1.8',
    minor: '6.7',
    described: 96,
  },
  {
    name: 'MiMo 2.6 Flash',
    maker: 'Xiaomi',
    why: 'leaves out details, slow',
    quality: 2,
    seconds: 99,
    price: '0.21',
    clear: '2.2',
    minor: '4.9',
    described: 87,
  },
  {
    name: 'DeepSeek V4.1 Flash',
    maker: 'DeepSeek',
    why: 'many errors, sometimes no caption',
    quality: 2,
    seconds: 40,
    price: '0.85',
    clear: '2.7',
    minor: '4.9',
    described: 93,
  },
  {
    name: 'MiMo 2.6 Pro',
    maker: 'Xiaomi',
    why: 'most errors',
    quality: 1,
    seconds: 71,
    price: '0.52',
    clear: '3.5',
    minor: '6.9',
    described: 94,
  },
  { name: 'Kimi K3', maker: 'Moonshot AI', why: 'expensive and slow', quality: 0 },
];

const SWITCHES = 'Every detail switch except content and background of a style (no model leaves those out reliably).';
const meter = (n) =>
  `<span class="meter" aria-label="${esc(t('Quality {v0} of 5', { v0: n }))}">${[1, 2, 3, 4, 5].map((i) => `<i class="${i <= n ? 'on' : ''}"></i>`).join('')}</span>`;
// Czech writes a decimal comma.
const num = (value) => (i18n.language === 'cs' ? String(value).replace('.', ',') : String(value));
const money = (value) => (value ? `${num(value)} $` : '–');

function facts(m) {
  if (!m.seconds) return `<p>${esc(t('We stopped measuring it: too expensive and too slow.'))}</p>`;
  return `<div class="facts"><span>${esc(t('Clear errors'))} <b>${num(m.clear)}</b> / 10</span><span>${esc(t('minor'))} <b>${num(m.minor)}</b></span><span>${esc(t('switched-on details described'))} <b>${m.described} %</b></span></div>`;
}

function row(m, rank, recommended) {
  const tag = m.tag ? `<span class="tag${m.warn ? ' amber' : ''}">${esc(t(m.tag))}</span>` : '';
  const second = recommended
    ? `<span class="provider">${esc(m.maker)}</span>`
    : `<span class="reason">${esc(t(m.why))}</span>`;
  const use = recommended
    ? `<button type="button" class="use secondary" data-model="${esc(m.name)}">${esc(t('Use this model'))}</button>`
    : '';
  const note = recommended
    ? `<p>${esc(t(m.note || SWITCHES))}</p>`
    : `<p>${esc(m.maker)}. ${esc(t('You can still use it; it gets the strictest detail switch offer.'))}</p>`;
  return `<details><summary class="row"><span class="rank">${rank}</span><span class="name"><b>${esc(m.name)}</b>${tag}${second}</span>${meter(m.quality)}<span class="num${m.seconds > 60 ? ' slow' : ''}">${m.seconds ? m.seconds + ' s' : '–'}</span><span class="num price">${money(m.price)}</span></summary><div class="more">${facts(m)}${note}${use}</div></details>`;
}

function columns(first) {
  return `<div class="cols"><span></span><span>${esc(t(first))}</span><span>${esc(t('QUALITY'))}</span><span class="num">${esc(t('TIME'))}</span><span class="num price">${esc(t('PRICE / 100'))}</span></div>`;
}

export function renderModelTable() {
  $('model-table').innerHTML =
    `<section class="zone good"><div class="zone-head"><span class="dot"></span><h3>${esc(t('Recommended models'))}</h3><small>${esc(t('by quality'))}</small></div>${columns('MODEL')}${RECOMMENDED.map((m, i) => row(m, i + 1, true)).join('')}</section>` +
    `<section class="zone bad"><div class="zone-head"><span class="dot"></span><h3>${esc(t('Models we advise against'))}</h3><small>${esc(t('measured, but not good for captions'))}</small></div>${columns('MODEL · WHY NOT')}${NOT_RECOMMENDED.map((m) => row(m, '–', false)).join('')}</section>` +
    `<p class="tiny muted">${esc(t('Measured on the 55 hardest shots with 40-word captions, judged blind (September 2026). Time per caption, price per 100 captions. Click a model for details.'))}</p>`;
  $('local-model-card').innerHTML =
    `<section class="zone good"><div class="zone-head"><span class="dot"></span><h3>${esc(t('Local model'))}</h3><small>${esc(t('runs on your computer'))}</small></div>` +
    `<div class="local-card"><span class="name"><b>${esc(t('Qwen with reasoning'))}</b><span class="tag">${esc(t('free, images stay with you'))}</span><span class="provider">${esc(t('Reasons while it looks at the image, shortens without reasoning.'))}</span></span>${meter(3)}<span class="num">~23 s</span><span class="num">0 $</span></div></section>` +
    `<p class="tiny muted">${esc(t('Time measured on an RTX 5090; a smaller card takes longer. Clear errors 1.4 per 10 captions, minor 5.8, switched-on details described 96 %.'))}</p>`;
}

// One model's details open at a time.
document.addEventListener(
  'toggle',
  (e) => {
    const opened = e.target;
    if (!(opened instanceof HTMLDetailsElement) || !opened.open || !opened.closest('.model-table')) return;
    for (const other of document.querySelectorAll('.model-table details[open]'))
      if (other !== opened) other.open = false;
  },
  true,
);

// "Use this model": the model's ID for the chosen provider, or OpenRouter when that provider does not offer it.
export function modelChoice(name, providerUrl) {
  const m = RECOMMENDED.find((x) => x.name === name);
  if (!m) return null;
  if (m.ids[providerUrl]) return { url: providerUrl, id: m.ids[providerUrl] };
  const url = 'https://openrouter.ai/api/v1';
  return { url, id: m.ids[url] };
}
