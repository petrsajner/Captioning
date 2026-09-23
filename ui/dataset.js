// Image grid, caption inspector, dataset import and batch control.
import { action, api, toast } from './api.js';
import { $, esc } from './dom.js';
import { diagnostic, t } from './i18n.js';
import { saveRecipe } from './recipe.js';
import { openSettings } from './settings.js';
import { hasBusy, resumeIds, ui } from './store.js';

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
let page = 0,
  lastGrid = '',
  lastCaptionHistory = '';

// Grid and history markup is cached by content; drop the cache when the language changes.
export function invalidateRenderCache() {
  lastGrid = '';
  lastCaptionHistory = '';
}

function activeRow() {
  return ui.state.rows.find((r) => r.id === ui.active);
}

function allowDiscard() {
  return !ui.dirty || window.confirm(t('The caption has unsaved edits. Discard these edits?'));
}

function filteredRows() {
  if (!ui.state) return [];
  const query = $('search').value.toLowerCase(),
    filter = $('filter').value;
  return ui.state.rows.filter(
    (r) =>
      r.name.toLowerCase().includes(query) &&
      (filter === 'all' ||
        (filter === 'saved' && r.exists) ||
        (filter === 'pending' && !r.exists) ||
        (filter === 'review' && r.status === 'review') ||
        (filter === 'error' && ['error', 'invalid'].includes(r.status))),
  );
}

export function renderGrid() {
  const { selected } = ui;
  const rows = filteredRows();
  page = Math.min(page, Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1));
  const visible = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const signature = JSON.stringify([
    visible.map((r) => [r.id, r.status, r.phase, r.exists, selected.has(r.id)]),
    ui.active,
  ]);
  if (signature !== lastGrid) {
    $('grid').innerHTML = visible
      .map(
        (r) =>
          `<article class="image-card ${r.status} ${r.id === ui.active ? 'active' : ''}" data-id="${r.id}" tabindex="0" aria-label="${esc(r.name)}"><input class="card-select" type="checkbox" ${selected.has(r.id) ? 'checked' : ''} aria-label="${esc(t('Select {name}', { name: r.name }))}"><img class="thumb" loading="lazy" src="/api/image/${r.id}" alt="${esc(r.name)}"><div class="card-info"><div class="card-name" title="${esc(r.path)}">${esc(r.name)}</div><div class="card-bottom"><span>${r.width} × ${r.height}</span><span class="status-label ${r.status}">${esc(t(r.status === 'processing' ? phaseLabels[r.phase] || labels.processing : labels[r.status] || r.status))}</span></div></div></article>`,
      )
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

function updateWords() {
  const text = $('caption-editor').value.trim();
  if (activeRow()?.caption_format === 'bria_json') {
    try {
      JSON.parse(text);
      $('caption-words').textContent = t('JSON object');
    } catch {
      $('caption-words').textContent = t('Invalid JSON');
    }
  } else $('caption-words').textContent = (text ? text.split(/\s+/).length : 0) + t(' words');
}

export function renderInspector() {
  const row = activeRow();
  $('inspector-empty').hidden = !!row;
  $('inspector-content').hidden = !row;
  if (!row) return;
  const src = '/api/image/' + row.id + '?full=true';
  if ($('preview-image').getAttribute('src') !== src) $('preview-image').src = src;
  $('image-name').textContent = row.name;
  $('image-meta').textContent = `${row.width} × ${row.height} px${row.seconds ? ' · ' + row.seconds + ' s' : ''}`;
  $('image-path').textContent = row.path;
  $('image-path').title = row.path;
  if (!ui.dirty && $('caption-editor').value !== row.caption) $('caption-editor').value = row.caption;
  $('image-error').hidden = !row.error;
  $('image-error').textContent = diagnostic(row.error);
  $('caption-state').textContent = ui.dirty
    ? t('● Unsaved edits')
    : row.status === 'draft'
      ? t('● Generated, not saved yet')
      : t(labels[row.status]);
  const json = row.caption_format === 'bria_json';
  $('caption-output-path').textContent = t('File: ') + row.name.replace(/\.[^.]+$/, json ? '.json' : '.txt');
  $('caption-notice').hidden = !row.notice;
  $('caption-notice').textContent = diagnostic(row.notice || '');
  $('format-json').hidden = !json;
  $('format-json').disabled = hasBusy();
  $('caption-editor').classList.toggle('json-editor', json);
  $('caption-editor').disabled = hasBusy() || row.status === 'invalid';
  $('save-caption').disabled = hasBusy() || row.status === 'invalid' || !$('caption-editor').value.trim();
  $('regenerate').disabled = hasBusy() || row.status === 'invalid';
  updateWords();
  const history = row.generation_history || [];
  $('caption-history').hidden = !history.length;
  const historyKey = row.id + ':' + JSON.stringify(history);
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

function showCaptionHistory() {
  $('caption-history-text').textContent =
    activeRow()?.generation_history?.[Number($('caption-history-select').value)]?.text || '';
  $('use-caption-history').disabled = hasBusy() || !$('caption-history-text').textContent.trim();
}

function selectImage(id) {
  if (id !== ui.active && !allowDiscard()) return;
  if (id !== ui.active) ui.dirty = false;
  ui.active = id;
  renderGrid();
  renderInspector();
}

async function saveCaption() {
  if (!ui.active || hasBusy()) return;
  await api('/caption/' + ui.active, { text: $('caption-editor').value }, 'PUT');
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

async function generate(ids, regenerate = false) {
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
  await api('/jobs', { ids, regenerate });
  await ui.refresh();
}

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
    return generate(
      pending.length ? pending : [...ui.selected],
      pending.length ? !!ui.state.job.resume_regenerate : false,
    );
  });
$('regenerate').onclick = () => action(() => generate([ui.active], true));
$('stop-job').onclick = () =>
  action(async () => {
    await api('/jobs/stop', {});
    await ui.refresh();
  });
