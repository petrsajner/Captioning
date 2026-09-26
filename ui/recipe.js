// Dataset recipe panel: shared caption settings, detail choices and autosave.
import { action, api } from './api.js';
import { $, esc, fillForm, formValues } from './dom.js';
import { t } from './i18n.js';
import { hasBusy, outputsFor, ui } from './store.js';

const recipe = $('recipe-form');
let recipeTimer,
  recipeDirty = false,
  recipeRevision = 0,
  recipeSaving = null,
  // Every LoRA type has its own details and keeps its own choices while another type is shown.
  shownType = null,
  typeChoices = {};

const shownOmitted = () =>
  [...recipe.querySelectorAll('[data-attribute]')].filter((el) => !el.checked).map((el) => el.dataset.attribute);

// Current recipe form values on top of the saved settings.
export function liveSettings() {
  const out = formValues(recipe, ui.state.settings);
  out.omitted_attributes = shownOmitted();
  out.omitted_by_type = { ...typeChoices, [shownType || out.preset]: out.omitted_attributes };
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

// The details of the recipe's LoRA type, with that type's names, checked unless omitted.
export function fillTrainingControls(settings) {
  const omitted = new Set(settings.omitted_attributes || []);
  shownType = settings.preset;
  $('training-controls').innerHTML = ui.state.training_details[settings.preset]
    .map(
      (a) =>
        `<label class="caption-detail" data-media="${a.media || ''}"><span><input type="checkbox" name="include_${a.id}" data-attribute="${a.id}" ${omitted.has(a.id) ? '' : 'checked'}><span class="detail-name">${esc(t(a.label))}</span><span class="detail-state" aria-hidden="true"><span class="state-on">ON</span><span class="state-off">OFF</span></span></span><small>${esc(t(a.detail))}</small></label>`,
    )
    .join('');
}

// A new LoRA type shows its own details: the choices made for it before, or its defaults.
function switchType() {
  const preset = recipe.elements.preset.value;
  if (preset === shownType) return;
  typeChoices[shownType] = shownOmitted();
  fillTrainingControls({ preset, omitted_attributes: typeChoices[preset] ?? ui.state.training_defaults[preset] });
}

// What the trigger and class fields mean for each LoRA type, and how the caption opens.
// The notes show invented example names, never the entered trigger, which may be a real person's name.
function typeFields(s) {
  const cls = s.subject_class.trim();
  if (s.preset === 'character')
    return {
      label: t('Character name'),
      placeholder: t('e.g. Velmira'),
      classLabel: t('Character type'),
      classDefault: 'a person',
      classes: ['a woman', 'a man', 'a person'],
      classNote: t(
        'Written after the name, for example “Velmira, a woman, …”. It also tells the model which pronouns to use.',
      ),
      note: t('Written once where the character is first named: “{trigger}, {cls}, …”.', {
        trigger: 'Velmira',
        cls: cls || 'a person',
      }),
    };
  if (s.preset === 'object')
    return {
      label: t('Object name'),
      placeholder: t('e.g. Zorbo'),
      classLabel: t('Object type'),
      classDefault: 'an object',
      classes: ['a bag', 'a bottle', 'a shoe', 'a watch', 'a car'],
      classNote: t('Written after the name, for example “Zorbo, a backpack, …”.'),
      note: t('Written once where the object is first named: “{trigger}, {cls}, …”.', {
        trigger: 'Zorbo',
        cls: cls || 'an object',
      }),
    };
  if (s.preset === 'style') {
    const phrase = 'Zorvak style';
    return {
      label: t('Style name'),
      placeholder: t('e.g. Zorvak'),
      note: t('Written at the start of every caption: “{phrase}, …”. The caption describes only the content.', {
        phrase,
      }),
    };
  }
  return {
    label: t('Trigger word'),
    placeholder: t('e.g. ohwx'),
    note:
      s.output_format === 'bria_json'
        ? t('Inserted into short_description so the JSON remains valid.')
        : t('Added exactly at the start of each caption.'),
  };
}

function renderTypeFields(s) {
  const fields = typeFields(s),
    classField = $('subject-class-field');
  $('trigger-label').textContent = fields.label;
  recipe.elements.trigger.placeholder = fields.placeholder;
  $('trigger-note').textContent = fields.note;
  classField.hidden = !fields.classLabel;
  if (fields.classLabel) {
    $('subject-class-label').textContent = fields.classLabel;
    recipe.elements.subject_class.placeholder = fields.classDefault;
    $('subject-class-note').textContent = fields.classNote;
    $('subject-classes').innerHTML = fields.classes.map((c) => `<option value="${esc(c)}"></option>`).join('');
  }
}

export function loadRecipe(settings) {
  typeChoices = { ...settings.omitted_by_type };
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
  const attrs = ui.state.training_details[s.preset].filter((a) => video || a.media !== 'clip'),
    omitted = s.omitted_attributes.filter((id) => attrs.some((a) => a.id === id));
  $('training-plan').textContent = t('{included} of {total} details included in caption', {
    included: attrs.length - omitted.length,
    total: attrs.length,
  });
  // Video models get English descriptions.
  recipe.elements.format.disabled = json || video || blocked;
  recipe.elements.language.disabled = video || blocked;
  recipe.elements.words.disabled = json || blocked;
  $('json-format-note').hidden = !json;
  $('length-policy-note').hidden = json;
  $('video-format-note').hidden = !video;
  renderTypeFields(s);
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
  switchType();
  renderTrainingPlan();
  $('recipe-status').textContent = t('Unsaved settings…');
  clearTimeout(recipeTimer);
  recipeTimer = setTimeout(() => action(saveRecipe), 600);
});
recipe.addEventListener('submit', (e) => e.preventDefault());

$('apply-training-preset').onclick = () => {
  // For example, a character's hair color belongs to the LoRA; its hairstyle stays free for prompts.
  const preset = recipe.elements.preset.value;
  fillTrainingControls({ preset, omitted_attributes: ui.state.training_defaults[preset] });
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
