// Image grid, caption inspector, dataset import and batch control.
import { action, api, toast } from './api.js';
import { $, esc } from './dom.js';
import { diagnostic, t } from './i18n.js';
import { liveSettings, saveRecipe } from './recipe.js';
import { openSettings } from './settings.js';
import { captionView, hasBusy, outputsFor, resumeIds, ui } from './store.js';

const PAGE_SIZE = 60;
const labels = {
  pending: 'Waiting',
  queued: 'Queued',
  processing: 'Analyzing…',
  saved: 'Saved',
  existing: 'Existing',
  skipped: 'Skipped',
  draft: 'Draft',
  review: 'To review',
  error: 'Error',
  invalid: 'Conflict / error',
};
const phaseLabels = {
  caption: 'Captioning…',
  shorten: 'Shortening…',
  complete: 'Completing…',
  repair_json: 'Repairing JSON…',
  retry_caption: 'Requesting a response…',
};
// Short model names for the per-model dots on a card.
const SHORT = { wan: 'WAN', wan_i2v: 'I2V', ltx: 'LTX', h3: 'H3' };
// What each video model trains on, shown for clips.
const modelNotes = {
  wan: 'WAN 2.2 (A14B) trains at 16 fps with up to 81 frames, about 5 s.',
  wan_i2v: 'WAN 2.2 I2V (A14B) trains at 16 fps with up to 81 frames, about 5 s; the first frame is the start image.',
  ltx: 'LTX-2.5 trains at 24–25 fps with up to 121 frames, about 5 s.',
  h3: 'MiniMax H3 trains at 24 fps on clips of 5–15 s.',
};
let page = 0,
  lastGrid = '',
  lastCaptionHistory = '',
  lastFormat = null,
  lastStrip = '';

// Grid and history markup is cached by content; drop the cache when the language changes.
export function invalidateRenderCache() {
  lastGrid = '';
  lastCaptionHistory = '';
}

function activeRow() {
  return ui.state.rows.find((r) => r.id === ui.active);
}

function format() {
  return liveSettings().output_format;
}

// The caption output open in the inspector.
function activeSlot() {
  return activeRow()?.outputs[ui.tab] || null;
}

function allowDiscard() {
  return !ui.dirty || window.confirm(t('The caption has unsaved edits. Discard these edits?'));
}

function filteredRows() {
  if (!ui.state) return [];
  const query = $('search').value.toLowerCase(),
    filter = $('filter').value,
    current = format();
  return ui.state.rows.filter((r) => {
    const view = captionView(r, current);
    return (
      r.name.toLowerCase().includes(query) &&
      (filter === 'all' ||
        (view &&
          ((filter === 'saved' && view.exists) ||
            (filter === 'pending' && !view.exists) ||
            (filter === 'review' && view.status === 'review') ||
            (filter === 'error' && ['error', 'invalid'].includes(view.status)))))
    );
  });
}

function statusLabel(view) {
  return t(
    view.status === 'processing' ? phaseLabels[view.phase] || labels.processing : labels[view.status] || view.status,
  );
}

function modelDots(row, current) {
  const outputs = outputsFor(current);
  if (outputs.length < 2) return '';
  return `<span class="model-dots">${outputs
    .filter((output) => row.outputs[output])
    .map((output) => {
      const slot = row.outputs[output];
      return `<i class="model-dot ${slot.status}" title="${esc(ui.state.caption_outputs[output].name + ': ' + statusLabel(slot))}">${SHORT[output]}</i>`;
    })
    .join('')}</span>`;
}

export function renderGrid() {
  const { selected } = ui;
  const rows = filteredRows(),
    current = format();
  page = Math.min(page, Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1));
  const visible = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const signature = JSON.stringify([
    current,
    visible.map((r) => [
      r.id,
      outputsFor(current).map((o) => [r.outputs[o]?.status, r.outputs[o]?.phase, r.outputs[o]?.exists]),
      selected.has(r.id),
    ]),
    ui.active,
  ]);
  if (signature !== lastGrid) {
    $('grid').innerHTML = visible
      .map((r) => {
        // An output that does not apply to this file, such as Normal for a clip.
        const view = captionView(r, current) || { status: 'unused' },
          label =
            view.status === 'unused' ? t(r.kind === 'clip' ? 'Video models only' : 'Clips only') : statusLabel(view),
          size =
            (r.kind === 'clip' ? `<span class="clip-badge">▶ ${r.clip?.duration ?? '?'} s</span> · ` : '') +
            `${r.width} × ${r.height}`;
        return `<article class="image-card ${view.status} ${r.id === ui.active ? 'active' : ''}" data-id="${r.id}" tabindex="0" aria-label="${esc(r.name)}"><input class="card-select" type="checkbox" ${selected.has(r.id) ? 'checked' : ''} aria-label="${esc(t('Select {name}', { name: r.name }))}"><img class="thumb" loading="lazy" src="/api/image/${r.id}" alt="${esc(r.name)}"><div class="card-info"><div class="card-name" title="${esc(r.path)}">${esc(r.name)}</div><div class="card-bottom"><span>${size}</span><span class="status-label ${view.status}">${esc(label)}</span></div>${modelDots(r, current)}</div></article>`;
      })
      .join('');
    lastGrid = signature;
  }
  $('empty').hidden = ui.state.rows.length > 0;
  $('grid').hidden = !rows.length;
  $('pagebar').hidden = !ui.state.rows.length;
  $('page-label').textContent = rows.length
    ? t('{start}–{end} of {count}', {
        start: page * PAGE_SIZE + 1,
        end: Math.min((page + 1) * PAGE_SIZE, rows.length),
        count: rows.length,
      })
    : t('No images match this filter');
  $('prev-page').disabled = page === 0;
  $('next-page').disabled = (page + 1) * PAGE_SIZE >= rows.length;
  $('selection-count').textContent = selected.size ? t('{v0} selected', { v0: selected.size }) : t('Select all');
  $('select-all').checked = rows.length > 0 && rows.every((r) => selected.has(r.id));
  $('select-all').indeterminate = rows.some((r) => selected.has(r.id)) && !$('select-all').checked;
}

// Words of an H3 caption are counted in its [Shot 1] description only, as the backend does.
function h3Body(text) {
  const match = text.match(
    /^integrated_multimodal_description: \[Shot 1\] ([\s\S]+?)\n\noverall_soundscape: [\s\S]+\n\nnon_diegetic_music: [\s\S]+$/,
  );
  return match ? match[1] : text;
}

function updateWords() {
  const text = $('caption-editor').value.trim();
  if (ui.tab === 'bria_json') {
    try {
      JSON.parse(text);
      $('caption-words').textContent = t('JSON object');
    } catch {
      $('caption-words').textContent = t('Invalid JSON');
    }
  } else {
    const words = ui.tab === 'h3' ? h3Body(text).trim() : text;
    $('caption-words').textContent = (words ? words.split(/\s+/).length : 0) + t(' words');
  }
}

// Tab marks: saved file, unsaved draft, or a problem.
function tabMark(slot) {
  if (['error', 'invalid'].includes(slot.status)) return '!';
  if (['draft', 'review'].includes(slot.status)) return '●';
  return slot.exists ? '✓' : '';
}

function renderTabs(row) {
  const current = format();
  if (current !== lastFormat) {
    // A new Caption output choice opens its first file, unless an edit is in progress.
    lastFormat = current;
    if (!ui.dirty) ui.tab = null;
  }
  if (!row.outputs[ui.tab]) ui.tab = outputsFor(current).find((o) => row.outputs[o]) || Object.keys(row.outputs)[0];
  $('caption-tabs').innerHTML = Object.keys(ui.state.caption_outputs)
    .filter((output) => row.outputs[output])
    .map((output) => {
      const slot = row.outputs[output],
        mark = tabMark(slot);
      return `<button type="button" role="tab" class="caption-tab ${slot.status}" data-output="${output}" aria-selected="${output === ui.tab}" title="${esc(ui.state.caption_outputs[output].name)}">${esc(ui.state.caption_outputs[output].suffix)}${mark ? ` <span aria-hidden="true">${mark}</span>` : ''}</button>`;
    })
    .join('');
}

export function renderInspector() {
  const row = activeRow();
  $('inspector-empty').hidden = !!row;
  $('inspector-content').hidden = !row;
  if (!row) return;
  renderTabs(row);
  const slot = activeSlot();
  const clip = row.kind === 'clip';
  $('preview-image').hidden = clip;
  $('preview-video').hidden = !clip;
  if (clip) {
    const media = '/api/media/' + row.id;
    if ($('preview-video').getAttribute('src') !== media) $('preview-video').src = media;
  } else {
    const src = '/api/image/' + row.id + '?full=true';
    if ($('preview-image').getAttribute('src') !== src) $('preview-image').src = src;
    if ($('preview-video').getAttribute('src')) {
      $('preview-video').pause();
      $('preview-video').removeAttribute('src');
      $('preview-video').load();
    }
  }
  renderClip(row);
  $('image-name').textContent = row.name;
  $('image-meta').textContent = clip
    ? t('{width} × {height} px · {duration} s · {fps} fps · {frames} frames', { ...row.clip }) +
      (row.clip.has_audio ? ' · ' + t('audio') : '')
    : `${row.width} × ${row.height} px${slot.seconds ? ' · ' + slot.seconds + ' s' : ''}`;
  $('image-path').textContent = row.path;
  $('image-path').title = row.path;
  if (!ui.dirty && $('caption-editor').value !== slot.caption) $('caption-editor').value = slot.caption;
  $('image-error').hidden = !slot.error;
  $('image-error').textContent = diagnostic(slot.error);
  $('caption-state').textContent = ui.dirty
    ? t('● Unsaved edits')
    : slot.status === 'draft'
      ? t('● Generated, not saved yet')
      : t(labels[slot.status]);
  const json = ui.tab === 'bria_json';
  $('caption-output-path').textContent =
    t('File: ') + row.name.replace(/\.[^.]+$/, ui.state.caption_outputs[ui.tab].suffix);
  // Several notices are stored one per line so each one is translated.
  const notices = (slot.notice || '').split('\n').filter(Boolean);
  $('caption-notice').hidden = !notices.length;
  $('caption-notice').textContent = notices.map((n) => diagnostic(n)).join(' ');
  $('format-json').hidden = !json;
  $('format-json').disabled = hasBusy();
  $('caption-editor').classList.toggle('json-editor', json);
  $('caption-editor').disabled = hasBusy() || slot.status === 'invalid';
  $('save-caption').disabled = hasBusy() || slot.status === 'invalid' || !$('caption-editor').value.trim();
  $('regenerate').disabled = hasBusy() || slot.status === 'invalid';
  updateWords();
  const history = slot.generation_history || [];
  $('caption-history').hidden = !history.length;
  const historyKey = row.id + ':' + ui.tab + ':' + JSON.stringify(history);
  if (lastCaptionHistory !== historyKey) {
    lastCaptionHistory = historyKey;
    $('caption-history-title').textContent = t('Model responses ({count})', { count: history.length });
    $('caption-history-select').innerHTML = history
      .map(
        (h, i) =>
          `<option value="${i}">${i + 1}. ${esc(t(phaseLabels[h.stage] || h.stage))}${h.word_count != null ? ' · ' + h.word_count + t(' words') : ''}</option>`,
      )
      .join('');
    showCaptionHistory();
  }
  $('use-caption-history').disabled = hasBusy() || !$('caption-history-text').textContent.trim();
}

// The model note of the open tab and the strip of frames the model receives.
function renderClip(row) {
  const clip = row.kind === 'clip';
  $('clip-note').hidden = !clip;
  $('frame-strip').hidden = !clip;
  if (!clip) return;
  $('clip-note').textContent = modelNotes[ui.tab] ? t(modelNotes[ui.tab]) : '';
  const key = row.id + ':' + ui.state.settings.clip_interval;
  if (key === lastStrip) return;
  lastStrip = key;
  $('frame-strip').innerHTML = '';
  api('/clip-frames/' + row.id)
    .then(({ times }) => {
      if (lastStrip !== key) return;
      $('frame-strip').innerHTML = times
        .map(
          (time) =>
            `<figure><img loading="lazy" src="/api/frame/${row.id}?t=${time}" alt=""><figcaption>${time.toFixed(2)} s</figcaption></figure>`,
        )
        .join('');
      $('frame-strip').title = t('{count} frames sent to the model', { count: times.length });
    })
    .catch(() => (lastStrip = ''));
}

function showCaptionHistory() {
  $('caption-history-text').textContent =
    activeSlot()?.generation_history?.[Number($('caption-history-select').value)]?.text || '';
  $('use-caption-history').disabled = hasBusy() || !$('caption-history-text').textContent.trim();
}

function selectImage(id) {
  if (id !== ui.active && !allowDiscard()) return;
  if (id !== ui.active) ui.dirty = false;
  ui.active = id;
  renderGrid();
  renderInspector();
}

function selectTab(output) {
  if (output === ui.tab || !allowDiscard()) return;
  ui.dirty = false;
  ui.tab = output;
  renderInspector();
}

async function saveCaption() {
  if (!ui.active || hasBusy()) return;
  await api('/caption/' + ui.active, { text: $('caption-editor').value, output: ui.tab }, 'PUT');
  ui.dirty = false;
  await ui.refresh();
  toast(t('Caption saved next to the image.'));
}

export async function doImport(paths = [], folder = '') {
  if (!allowDiscard()) return false;
  await saveRecipe();
  ui.busy = true;
  ui.render();
  try {
    const append = $('append').checked,
      oldIds = new Set(ui.state.rows.map((r) => r.id));
    await api('/import', { paths, folder, recursive: $('recursive').checked, append });
    ui.dirty = false;
    await ui.refresh();
    if (!append) ui.selected.clear();
    for (const r of ui.state.rows) if (!oldIds.has(r.id) || !append) ui.selected.add(r.id);
    if (!ui.state.rows.some((r) => r.id === ui.active)) ui.active = ui.state.rows[0]?.id || null;
    page = 0;
    toast(t('Loaded {v0} images.', { v0: ui.state.rows.length }));
    return true;
  } finally {
    ui.busy = false;
    ui.render();
  }
}

async function pickFiles() {
  if (hasBusy()) return;
  const result = await api('/pick/files', {});
  if (result.paths.length) await doImport(result.paths);
}

// `output` limits the batch to one caption file (Regenerate); `resume` continues a paused batch.
async function generate(ids, regenerate = false, { output = null, resume = false } = {}) {
  if (hasBusy() || !allowDiscard()) return;
  await saveRecipe();
  ui.dirty = false;
  const { settings, runtime } = ui.state;
  if (settings.mode === 'local' && settings.local_source === 'managed' && !runtime.running) {
    if (!runtime.ready) {
      openSettings();
      toast(t('Download the runtime and model first, or select a cloud API.'));
      return;
    }
    ui.busy = true;
    ui.render();
    toast(t('Starting the local model. Loading may take a moment.'));
    try {
      await api('/runtime/start', {});
    } finally {
      ui.busy = false;
      await ui.refresh();
    }
  }
  await api('/jobs', { ids, regenerate, output, resume });
  await ui.refresh();
}

$('caption-tabs').addEventListener('click', (e) => {
  const tab = e.target.closest('.caption-tab');
  if (tab) selectTab(tab.dataset.output);
});
$('caption-history-select').onchange = showCaptionHistory;
$('use-caption-history').onclick = () => {
  if (hasBusy()) return;
  $('caption-editor').value = $('caption-history-text').textContent;
  ui.dirty = true;
  renderInspector();
};
$('grid').addEventListener('click', (e) => {
  const card = e.target.closest('.image-card');
  if (!card) return;
  if (e.target.matches('.card-select')) {
    e.target.checked ? ui.selected.add(card.dataset.id) : ui.selected.delete(card.dataset.id);
    ui.render();
  } else selectImage(card.dataset.id);
});
$('grid').addEventListener('keydown', (e) => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.image-card')) {
    e.preventDefault();
    selectImage(e.target.dataset.id);
  }
});
$('select-all').onchange = () => {
  for (const r of filteredRows()) $('select-all').checked ? ui.selected.add(r.id) : ui.selected.delete(r.id);
  ui.render();
};
for (const id of ['search', 'filter'])
  $(id).addEventListener('input', () => {
    page = 0;
    renderGrid();
  });
$('prev-page').onclick = () => {
  page--;
  renderGrid();
};
$('next-page').onclick = () => {
  page++;
  renderGrid();
};
$('caption-editor').oninput = () => {
  ui.dirty = true;
  renderInspector();
};
$('save-caption').onclick = () => action(saveCaption);
$('format-json').onclick = () =>
  action(async () => {
    const data = JSON.parse($('caption-editor').value);
    if (!data || Array.isArray(data) || typeof data !== 'object') throw Error(t('BRIA requires a JSON object.'));
    $('caption-editor').value = JSON.stringify(data, null, 2);
    ui.dirty = true;
    renderInspector();
  });
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    action(saveCaption);
  }
});
$('pick-files').onclick = () => action(pickFiles);
$('open-path').onclick = () => $('path-dialog').showModal();
$('import-path').onclick = () =>
  action(async () => {
    await doImport([], $('folder-path').value.trim());
    $('path-dialog').close();
  });
$('folder-path').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $('import-path').click();
});
$('generate').onclick = () =>
  action(() => {
    const pending = resumeIds();
    return pending.length
      ? generate(pending, !!ui.state.job.resume_regenerate, { resume: true })
      : generate([...ui.selected], false);
  });
$('regenerate').onclick = () => action(() => generate([ui.active], true, { output: ui.tab }));
$('stop-job').onclick = () =>
  action(async () => {
    await api('/jobs/stop', {});
    await ui.refresh();
  });
