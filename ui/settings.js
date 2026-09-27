// Setup dialog: model connection, managed runtime, local server discovery and interface language.
import { action, api } from './api.js';
import { $, esc, fillForm, formValues } from './dom.js';
import { diagnostic, setLanguage, t } from './i18n.js';
import { fillTrainingControls, liveSettings, saveRecipe } from './recipe.js';
import { ui } from './store.js';

const settingsForm = $('settings-form');
let settingsMode = 'local',
  localScanBusy = false,
  localModelsBusy = false,
  localServers = [];

const normalizedUrl = (field) => field.value.trim().replace(/\/$/, '');

// Whether an API address has a saved key; the keys themselves never leave the app.
function keySaved(url, local) {
  return ((local ? ui.state.local_keys : ui.state.cloud_keys) || []).includes(url);
}

function keyStatusText(url, local) {
  return keySaved(url, local)
    ? t('Key saved for this address. Leave the field empty to keep it.')
    : t('No key is saved for this address.');
}

function renderProviderOptions() {
  // The name comes from the option's data-i18n; only the key mark is added here.
  for (const option of $('cloud-provider').options) {
    const mark = option.value === 'custom' ? '' : ' · ' + (keySaved(option.value) ? t('key saved') : t('no key'));
    option.textContent = t(option.dataset.i18n) + mark;
  }
}

function renderKeyStatuses() {
  renderProviderOptions();
  $('key-status').textContent = keyStatusText(normalizedUrl(settingsForm.elements.cloud_url), false);
  $('local-key-status').textContent = keyStatusText(normalizedUrl(settingsForm.elements.local_url), true);
}

// What the connection choices offer right now: the managed model, a found server and saved keys.
function renderSummary() {
  const r = ui.state.runtime;
  let local, localReady;
  if (settingsForm.elements.local_source.value === 'managed') {
    localReady = r.running || r.ready;
    local = r.installing
      ? t('Local · preparing the runtime')
      : r.running
        ? t('Local · the model is running')
        : r.ready
          ? t('Local · the model is ready to start')
          : t('Local · the runtime is not downloaded');
  } else if (localScanBusy) {
    localReady = false;
    local = t('Local · checking the servers…');
  } else {
    const found = localServers.find((server) => server.url === normalizedUrl(settingsForm.elements.local_url));
    localReady = !!found;
    local = !found
      ? t('Local · no server answers')
      : found.status === 'requires_key'
        ? t('Local · the server needs a key')
        : t('Local · the server is running');
  }
  const keys = (ui.state.cloud_keys || []).length;
  $('connection-summary').innerHTML =
    `<span><i class="dot ${localReady ? 'green-dot' : 'muted-dot'}"></i>${esc(local)}</span>` +
    `<span><i class="dot ${keys ? 'green-dot' : 'muted-dot'}"></i>${esc(t('Cloud · saved keys: {v0}', { v0: keys }))}</span>`;
}

export function renderRuntime() {
  const r = ui.state.runtime,
    jobRunning = ui.state.job.running;
  for (const el of settingsForm.elements) el.disabled = r.installing || r.status === 'loading';
  $('runtime-badge').textContent = r.running
    ? t('Running')
    : r.ready
      ? t('Ready')
      : r.installing
        ? t('Preparing')
        : t('Not ready');
  $('runtime-message').textContent =
    r.ready && r.status === 'idle' ? t('The runtime and model are ready to start.') : diagnostic(r.message);
  const pct = r.total ? Math.min(100, (100 * r.done) / r.total) : 0;
  $('download-progress').style.width = pct + '%';
  $('download-details').textContent =
    r.total > 1 ? `${(r.done / 1e9).toFixed(2)} / ${(r.total / 1e9).toFixed(2)} GB · ${pct.toFixed(0)} %` : '';
  $('runtime-path').textContent = r.root;
  $('install-runtime').disabled = r.installing || r.running || ui.busy || jobRunning;
  $('install-runtime').textContent = r.ready ? t('Verify / complete model') : t('Download runtime and model');
  $('cancel-install').hidden = !r.installing;
  $('start-model').hidden = r.running;
  $('start-model').disabled = !r.ready || r.installing || ui.busy || jobRunning;
  $('stop-model').hidden = !r.running;
  $('stop-model').disabled = ui.busy || jobRunning;
  // Protect the profile of an in-flight install while allowing its cancellation.
  $('cancel-install').disabled = false;
  $('save-settings').disabled = r.installing || r.status === 'loading' || ui.busy;
  $('find-local-servers').disabled = r.installing || r.status === 'loading' || localScanBusy || localModelsBusy;
  $('load-local-models').disabled = r.installing || r.status === 'loading' || localModelsBusy || localScanBusy;
  renderKeyStatuses();
  renderSummary();
}

function switchMode(mode) {
  settingsMode = mode;
  document.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('active', b.dataset.mode === mode));
  $('local-settings').hidden = mode !== 'local';
  $('cloud-settings').hidden = mode !== 'cloud';
}

function showLocalSource() {
  const external = settingsForm.elements.local_source.value === 'external';
  $('managed-settings').hidden = external;
  $('external-settings').hidden = !external;
}

function clearLocalKeyInput() {
  $('local-api-key').value = '';
  $('clear-local-key').checked = false;
  renderKeyStatuses();
}

function fillLocalModels(models) {
  $('local-models').innerHTML = models.map((id) => `<option value="${esc(id)}">`).join('');
  if (models.length && !models.includes(settingsForm.elements.local_model.value))
    settingsForm.elements.local_model.value = models[0];
}

export function openSettings() {
  const { state } = ui;
  if (!state) return;
  fillForm(settingsForm, state.settings);
  switchMode(state.settings.mode);
  $('api-key').value = '';
  $('clear-key').checked = false;
  clearLocalKeyInput();
  showLocalSource();
  $('local-server-results').hidden = true;
  $('local-server-results').replaceChildren();
  localServers = [];
  $('local-discovery-message').textContent = t(
    'Check common local addresses for Ollama, LM Studio, Unsloth and llama.cpp.',
  );
  $('cloud-provider').value = [...$('cloud-provider').options].some((o) => o.value === state.settings.cloud_url)
    ? state.settings.cloud_url
    : 'custom';
  $('setup-title').textContent = state.settings.setup_complete ? t('Model and runtime') : t('Set up your workspace');
  $('settings-message').textContent = '';
  $('settings-dialog').showModal();
  renderRuntime();
  // What is available must be visible immediately, not after trying buttons.
  action(findLocalServers);
}

async function saveSetup(close = false) {
  await saveRecipe();
  if (!settingsForm.reportValidity()) throw Error(t('Correct the highlighted values.'));
  const config = formValues(settingsForm, liveSettings());
  config.mode = settingsMode;
  config.setup_complete = true;
  const result = await api('/settings', {
    settings: config,
    api_key: $('api-key').value || null,
    clear_key: $('clear-key').checked,
    local_api_key: $('local-api-key').value || null,
    clear_local_key: $('clear-local-key').checked,
  });
  ui.state.settings = config;
  ui.state.has_key = result.has_key;
  $('api-key').value = '';
  $('clear-key').checked = false;
  ui.state.has_local_key = result.has_local_key;
  clearLocalKeyInput();
  $('settings-message').textContent = t('Settings saved');
  await ui.refresh();
  if (close) $('settings-dialog').close();
}

async function changeLanguage() {
  const language = $('ui-language').value;
  try {
    await saveRecipe();
    await api('/ui-language', { language });
    ui.state.settings.ui_language = language;
    const draft = liveSettings();
    setLanguage(language);
    fillTrainingControls(draft);
    ui.relocalize();
    $('setup-title').textContent = t(ui.state.settings.setup_complete ? 'Model and runtime' : 'Set up your workspace');
    $('settings-message').textContent = t('Language saved');
  } catch (e) {
    $('ui-language').value = ui.state.settings.ui_language;
    throw e;
  }
}

async function findLocalServers() {
  if (localScanBusy) return;
  localScanBusy = true;
  renderRuntime();
  $('local-discovery-message').textContent = t('Finding running local servers…');
  $('local-server-results').hidden = true;
  try {
    const result = await api('/local-servers', { url: settingsForm.elements.local_url.value });
    localServers = result.servers;
    $('local-server-results').innerHTML = localServers
      .map(
        (server, index) =>
          `<button type="button" class="local-server" data-server-index="${index}"><span><b>${esc(server.url)}</b><small>${esc(t(server.hint))}</small></span><span>${server.status === 'requires_key' ? t('Key required') : server.models.length ? t('Models: ') + server.models.length : t('No model')}${server.managed ? '' : ' · ' + (keySaved(server.url, true) ? t('key saved') : t('no key'))} →</span></button>`,
      )
      .join('');
    $('local-server-results').hidden = !localServers.length;
    $('local-discovery-message').textContent = localServers.length
      ? t('Servers found: {v0}. Click to select a connection.', { v0: localServers.length })
      : t('No running server was found. Start its API, or select Existing local server and enter a custom address.');
  } catch (e) {
    $('local-discovery-message').textContent = t(e.message);
  } finally {
    localScanBusy = false;
    renderRuntime();
  }
}

function selectLocalServer(e) {
  const button = e.target.closest('[data-server-index]');
  if (!button || localScanBusy) return;
  const server = localServers[Number(button.dataset.serverIndex)];
  if (!server) return;
  settingsForm.elements.local_source.value = server.managed ? 'managed' : 'external';
  if (!server.managed) {
    settingsForm.elements.local_url.value = server.url;
    settingsForm.elements.local_model.value = server.models[0] || '';
  }
  clearLocalKeyInput();
  fillLocalModels(server.models);
  showLocalSource();
  $('local-model-status').textContent =
    server.status === 'requires_key'
      ? t('The server requires a key. Enter it and click Load models. Compatibility has not been verified yet.')
      : server.models.length
        ? t('Select an image-capable model. Its presence in this list does not guarantee image support.')
        : t('The server responds but offers no models. Load a model in its original application and refresh the list.');
  $('local-discovery-message').textContent = t('Selected {url}. Confirm with Save and continue.', { url: server.url });
  if (server.status === 'requires_key') $('local-api-key').focus();
}

async function loadLocalModels() {
  if (localModelsBusy) return;
  localModelsBusy = true;
  renderRuntime();
  $('local-model-status').textContent = t('Checking the connection and loading models…');
  try {
    await saveSetup();
    const localSettings = { ...formValues(settingsForm, ui.state.settings), mode: 'local', local_source: 'external' };
    const result = await api('/models', localSettings);
    fillLocalModels(result.models);
    $('local-model-status').textContent = result.models.length
      ? t('Connected. Available models: {v0}. Select an image-capable model and save settings.', {
          v0: result.models.length,
        })
      : t('Connected, but the list is empty. Load a model in its application first.');
  } catch (e) {
    $('local-model-status').textContent = t(e.message);
  } finally {
    localModelsBusy = false;
    renderRuntime();
  }
}

settingsForm.addEventListener('submit', (e) => e.preventDefault());
$('open-settings').onclick = openSettings;
$('model-chip').onclick = openSettings;
document.querySelectorAll('[data-mode]').forEach((b) => (b.onclick = () => switchMode(b.dataset.mode)));
$('cloud-provider').onchange = () => {
  if ($('cloud-provider').value !== 'custom') settingsForm.elements.cloud_url.value = $('cloud-provider').value;
  settingsForm.elements.cloud_model.value = '';
  $('api-key').value = '';
  $('clear-key').checked = false;
  renderKeyStatuses();
  renderSummary();
};
$('save-settings').onclick = () => action(() => saveSetup(true));
$('ui-language').onchange = () => action(changeLanguage);
$('load-models').onclick = () =>
  action(async () => {
    await saveSetup();
    $('settings-message').textContent = t('Loading models…');
    const result = await api('/models', ui.state.settings);
    $('cloud-models').innerHTML = result.models.map((m) => `<option value="${esc(m)}">`).join('');
    $('settings-message').textContent = t('Connected · {v0} models. Select a model in the field above.', {
      v0: result.models.length,
    });
    settingsForm.elements.cloud_model.focus();
  });
$('install-runtime').onclick = () =>
  action(async () => {
    await saveSetup();
    await api('/runtime/install', {});
    await ui.refresh();
  });
$('cancel-install').onclick = () =>
  action(async () => {
    await api('/runtime/cancel', {});
    $('runtime-message').textContent = t('Pausing download…');
  });
$('start-model').onclick = () =>
  action(async () => {
    await saveSetup();
    ui.busy = true;
    ui.render();
    try {
      await api('/runtime/start', {});
    } finally {
      ui.busy = false;
      await ui.refresh();
    }
  });
$('stop-model').onclick = () =>
  action(async () => {
    await api('/runtime/stop', {});
    await ui.refresh();
  });
$('local-source').onchange = showLocalSource;
settingsForm.elements.local_url.addEventListener('input', () => {
  clearLocalKeyInput();
  renderSummary();
  $('local-models').replaceChildren();
  $('local-model-status').textContent = t('Load the available models for this address.');
});
settingsForm.elements.cloud_url.addEventListener('input', renderKeyStatuses);
$('find-local-servers').onclick = findLocalServers;
$('local-server-results').onclick = selectLocalServer;
$('load-local-models').onclick = loadLocalModels;
