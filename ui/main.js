// Entry point: renders the shared header and run bar, polls the application state and wires the modules.
import { api, toast } from './api.js';
import { doImport, invalidateRenderCache, renderGrid, renderInspector } from './dataset.js';
import { $ } from './dom.js';
import { FolderPicker } from './folder-browser.js';
import { diagnostic, loadTranslations, setLanguage, t } from './i18n.js';
import { hasUnsavedRecipe, liveSettings, loadRecipe, renderRecipe } from './recipe.js';
import { openSettings, renderRuntime } from './settings.js';
import { hasBusy, resumeIds, ui } from './store.js';

const folderPicker = new FolderPicker(doImport);
let pollBusy = false;

function render() {
  const { state } = ui;
  const version = 'v' + state.version;
  if ($('app-version').textContent !== version) {
    $('app-version').textContent = version;
    document.title = 'Caption Studio ' + version;
  }
  $('total-badge').textContent = state.rows.length;
  $('pending-count').textContent = state.rows.filter(
    (r) => !r.exists && !['invalid', 'error', 'review'].includes(r.status),
  ).length;
  $('saved-count').textContent = state.rows.filter((r) => r.exists).length;
  $('error-count').textContent = state.rows.filter((r) => ['invalid', 'error'].includes(r.status)).length;
  $('review-count').textContent = state.rows.filter((r) => r.status === 'review').length;
  const j = state.job;
  $('job-title').textContent = ui.busy ? t('Working…') : diagnostic(j.message);
  $('job-count').textContent = j.total
    ? t('{v0} / {v1} · {v2} saved{v3}{v4}', {
        v0: j.completed,
        v1: j.total,
        v2: j.saved,
        v3: j.review ? ' · ' + j.review + t(' to review') : '',
        v4: j.skipped ? ' · ' + j.skipped + t(' skipped') : '',
      })
    : '';
  $('job-progress').style.width = j.total ? (100 * j.completed) / j.total + '%' : '0%';
  $('stop-job').hidden = !j.running;
  const pending = resumeIds(),
    runCount = pending.length || ui.selected.size;
  $('generate').disabled = hasBusy() || !runCount;
  $('generate').innerHTML =
    `${pending.length ? t('Continue') : liveSettings().output_format === 'bria_json' ? t('Create BRIA JSON') : t('Create captions')}${runCount ? ' (' + runCount + ')' : ''} <span>→</span>`;
  $('model-chip').querySelector('span').textContent =
    state.settings.mode === 'local'
      ? state.settings.local_source === 'external'
        ? t('Local · ') + (state.settings.local_model || t('external server'))
        : t('Local · {v0}', { v0: state.runtime.running ? t('Qwen running') : 'Qwen / server' })
      : 'Cloud · ' + (state.settings.cloud_model.split('/').pop() || t('select a model'));
  $('mode-note').textContent =
    state.settings.mode === 'local'
      ? t('Local mode · images stay on this computer')
      : t('Cloud mode · selected images will be sent to {v0}', { v0: new URL(state.settings.cloud_url).hostname });
  for (const id of ['pick-folder', 'pick-files', 'open-path', 'open-settings', 'model-chip'])
    $(id).disabled = hasBusy();
  renderRecipe();
  renderGrid();
  renderInspector();
  renderRuntime();
}

async function refresh() {
  if (pollBusy) return;
  pollBusy = true;
  try {
    const next = await api('/state');
    // Keep the recipe being edited; the server copy lags until autosave completes.
    if (hasUnsavedRecipe() && ui.state) next.settings = ui.state.settings;
    ui.state = next;
    render();
  } finally {
    pollBusy = false;
  }
}

function relocalize() {
  invalidateRenderCache();
  render();
  if (folderPicker.listing) {
    folderPicker.renderContents();
    folderPicker.renderTree();
  }
}

Object.assign(ui, { render, refresh, relocalize });

document.querySelectorAll('.close-dialog').forEach((b) => (b.onclick = () => b.closest('dialog').close()));
$('pick-folder').onclick = () => {
  if (!hasBusy()) folderPicker.open();
};
window.addEventListener('beforeunload', (e) => {
  if (ui.dirty || hasUnsavedRecipe()) {
    e.preventDefault();
    e.returnValue = '';
  }
});

try {
  await loadTranslations();
  ui.state = await api('/state');
  setLanguage(ui.state.settings.ui_language);
  loadRecipe(ui.state.settings);
  ui.selected = new Set(ui.state.rows.map((r) => r.id));
  ui.active = ui.state.rows[0]?.id || null;
  render();
  if (!ui.state.settings.setup_complete) openSettings();
  // One-time startup messages: moved data folder, preserved damaged files. They carry paths, so stay longer.
  const notes = ui.state.notices.map((notice) => t(notice));
  if (ui.state.recovered.length)
    notes.push(
      t('Some saved data could not be used and was reset. The original file was kept as: {names}', {
        names: ui.state.recovered.join(', '),
      }),
    );
  if (notes.length) {
    toast(notes.join(' '), ui.state.recovered.length > 0, 20000);
    if ($('settings-dialog').open) $('settings-message').textContent = notes.join(' ');
  }
  setInterval(
    () =>
      refresh().catch(() => {
        $('job-title').textContent = t('Connection to the application was lost');
      }),
    1200,
  );
} catch (e) {
  toast(e.message, true);
}
