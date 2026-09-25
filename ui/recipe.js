// Dataset recipe panel: shared caption settings, detail choices and autosave.
import { action, api } from './api.js';
import { $, esc, fillForm, formValues } from './dom.js';
import { t } from './i18n.js';
import { hasBusy, outputsFor, ui } from './store.js';

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
        `<label class="caption-detail" data-media="${a.media || ''}"><span><input type="checkbox" name="include_${a.id}" data-attribute="${a.id}" ${omitted.has(a.id) ? '' : 'checked'}><span class="detail-name">${esc(t(a.label))}</span><span class="detail-state" aria-hidden="true"><span class="state-on">ON</span><span class="state-off">OFF</span></span></span><small>${esc(t(a.detail))}</small></label>`,
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
    format = s.output_format,
    json = format === 'bria_json',
    video = format === 'video_all' || ui.state.video_outputs.includes(format),
    blocked = hasBusy() || ui.state.runtime.installing || ui.state.runtime.status === 'loading';
  // Motion and camera movement exist only in clips, which only the video models caption.
  for (const label of $('training-controls').querySelectorAll('[data-media=clip]')) label.hidden = !video;
  const attrs = ui.state.training_attributes.filter((a) => video || a.media !== 'clip'),
    omitted = s.omitted_attributes.filter((id) => attrs.some((a) => a.id === id));
  $('training-plan').textContent = t('{included} of {total} details included in caption', {
    included: attrs.length - omitted.length,
    total: attrs.length,
  });
  // Video models get English descriptions; the trigger is the character's name, so no subject name.
  recipe.elements.format.disabled = json || video || blocked;
  recipe.elements.language.disabled = video || blocked;
  recipe.elements.words.disabled = json || blocked;
  $('json-format-note').hidden = !json;
  $('length-policy-note').hidden = json;
  $('video-format-note').hidden = !video;
  $('character-class-field').hidden = !video;
  $('subject-field').hidden = video;
  recipe.elements.trigger.placeholder = video ? t('e.g. Velmira') : t('e.g. ohwx person');
  $('trigger-note').textContent = json
    ? t('Inserted into short_description so the JSON remains valid.')
    : video
      ? t('Written once where the character is first named: “{trigger}, {cls}, …”.', {
          trigger: s.trigger.trim() || 'Velmira',
          cls: s.character_class.trim() || 'a person',
        })
      : t('Added exactly at the start of each caption.');
  const files = outputsFor(format)
    .map((output) => 'image' + ui.state.caption_outputs[output].suffix)
    .join(', ');
  $('output-note').innerHTML =
    `<b>image.jpg → ${esc(files)}</b><br>${esc(t('Same folder, UTF-8. Every output has its own file; saving one never changes the others. Replaced captions are backed up.'))}`;
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
  // A character's hair color belongs to the LoRA; its hairstyle stays free for prompts.
  const preset = recipe.elements.preset.value,
    omitted =
      {
        character: ['identity', 'hair_color'],
        object: ['identity'],
        style: ['style'],
      }[preset] || [];
  fillTrainingControls({ ...liveSettings(), omitted_attributes: omitted });
  recipe.dispatchEvent(new Event('input', { bubbles: true }));
};

$('preview-prompt').onclick = () =>
  action(async () => {
    const settings = liveSettings(),
      outputs = outputsFor(settings.output_format);
    // Every video model has its own instructions; show each of them for "All video models".
    const prompts = await Promise.all(outputs.map((output) => api('/prompt', { ...settings, output_format: output })));
    $('prompt-text').textContent =
      outputs.length > 1
        ? prompts
            .map((result, i) => `=== ${ui.state.caption_outputs[outputs[i]].name} ===\n${result.prompt}`)
            .join('\n\n')
        : prompts[0].prompt;
    $('prompt-dialog').showModal();
  });
