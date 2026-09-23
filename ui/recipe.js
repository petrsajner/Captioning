// Dataset recipe panel: shared caption settings, detail choices and autosave.
import { action, api } from './api.js';
import { $, esc, fillForm, formValues } from './dom.js';
import { t } from './i18n.js';
import { hasBusy, ui } from './store.js';

const recipe = $('recipe-form');
let recipeTimer,
  recipeDirty = false,
  recipeRevision = 0,
  recipeSaving = null;

// Current recipe form values on top of the saved settings.
export function liveSettings() {
  const out = formValues(recipe, ui.state.settings);
  out.omitted_attributes = [...recipe.querySelectorAll('[data-attribute]')]
    .filter((el) => !el.checked)
    .map((el) => el.dataset.attribute);
  return out;
}

export function hasUnsavedRecipe() {
  return recipeDirty;
}

export async function saveRecipe() {
  clearTimeout(recipeTimer);
  if (recipeSaving) await recipeSaving;
  if (!recipeDirty) return;
  const snapshot = liveSettings(),
    revision = recipeRevision;
  recipeSaving = api('/settings', { settings: snapshot });
  try {
    await recipeSaving;
    ui.state.settings = snapshot;
    recipeDirty = recipeRevision !== revision;
    $('recipe-status').textContent = recipeDirty ? t('Unsaved settings…') : t('Settings saved');
  } finally {
    recipeSaving = null;
  }
  if (recipeDirty) await saveRecipe();
}

export function fillTrainingControls(settings) {
  const omitted = new Set(settings.omitted_attributes || []);
  $('training-controls').innerHTML = ui.state.training_attributes
    .map(
      (a) =>
        `<label class="caption-detail"><span><input type="checkbox" name="include_${a.id}" data-attribute="${a.id}" ${omitted.has(a.id) ? '' : 'checked'}><span class="detail-name">${esc(t(a.label))}</span><span class="detail-state" aria-hidden="true"><span class="state-on">ON</span><span class="state-off">OFF</span></span></span><small>${esc(t(a.detail))}</small></label>`,
    )
    .join('');
}

export function loadRecipe(settings) {
  fillTrainingControls(settings);
  fillForm(recipe, settings);
  $('word-output').value = settings.words;
}

function renderTrainingPlan() {
  const s = liveSettings(),
    omitted = new Set(s.omitted_attributes),
    attrs = ui.state.training_attributes;
  $('training-plan').textContent = t('{included} of {total} details included in caption', {
    included: attrs.length - omitted.size,
    total: attrs.length,
  });
  const json = s.output_format === 'bria_json',
    blocked = hasBusy() || ui.state.runtime.installing || ui.state.runtime.status === 'loading';
  recipe.elements.format.disabled = json || blocked;
  recipe.elements.words.disabled = json || blocked;
  $('json-format-note').hidden = !json;
  $('length-policy-note').hidden = json;
  $('trigger-note').textContent = json
    ? t('Inserted into short_description so the JSON remains valid.')
    : t('Added exactly at the start of each caption.');
  $('output-note').innerHTML =
    `<b>image.jpg → image.${json ? 'json' : 'txt'}</b><br>${esc(t('Same folder, UTF-8. Skipping applies to both formats. Replaced captions are backed up; the other format is archived so the trainer cannot select it accidentally.'))}`;
}

export function renderRecipe() {
  const { runtime } = ui.state;
  for (const el of recipe.elements) el.disabled = hasBusy() || runtime.installing || runtime.status === 'loading';
  renderTrainingPlan();
}

recipe.addEventListener('input', () => {
  $('word-output').value = recipe.elements.words.value;
  recipeDirty = true;
  recipeRevision++;
  renderTrainingPlan();
  $('recipe-status').textContent = t('Unsaved settings…');
  clearTimeout(recipeTimer);
  recipeTimer = setTimeout(() => action(saveRecipe), 600);
});
recipe.addEventListener('submit', (e) => e.preventDefault());

$('apply-training-preset').onclick = () => {
  const preset = recipe.elements.preset.value,
    omitted = preset === 'character' || preset === 'object' ? ['identity'] : preset === 'style' ? ['style'] : [];
  fillTrainingControls({ ...liveSettings(), omitted_attributes: omitted });
  recipe.dispatchEvent(new Event('input', { bubbles: true }));
};

$('preview-prompt').onclick = () =>
  action(async () => {
    const result = await api('/prompt', liveSettings());
    $('prompt-text').textContent = result.prompt;
    $('prompt-dialog').showModal();
  });
