import { api, env, expect, state, test } from './support.js';

const detail = (page, id) => page.locator('.caption-detail', { has: page.locator(`[data-attribute=${id}]`) });

test('a switch the model follows only sometimes is orange and stays as chosen', async ({ page }) => {
  const recipe = page.locator('#recipe-form');
  await api(page, '/settings', {
    settings: { ...env.settings, preset: 'style', omitted_attributes: ['identity', 'style', 'palette'] },
  });
  await page.reload();
  // Local Qwen left a print's content out in 3 of 10 test captions and its background in 6 of 10: a style is
  // judged loosely (orange from 30 %), so both switches stay free, in orange, with the measured share.
  await expect(detail(page, 'identity')).toHaveClass(/uncertain/);
  await expect(recipe.locator('[data-attribute=identity]')).toBeEnabled();
  await expect(recipe.locator('[data-attribute=identity]')).not.toBeChecked();
  await expect(detail(page, 'identity').locator('.lock-note')).toHaveText(
    'Switched off, this model left it out in 3 of 10 test captions. Check the captions.',
  );
  await expect(detail(page, 'background')).toHaveClass(/uncertain/);
  await expect(detail(page, 'background').locator('.lock-note')).toHaveText(
    'Switched off, this model left it out in 6 of 10 test captions. Check the captions.',
  );
  // The other switches are green: no note.
  await expect(detail(page, 'palette')).not.toHaveClass(/uncertain|locked/);
  await expect(detail(page, 'palette').locator('.lock-note')).toBeHidden();
  // The caption uses the choice as it is.
  await page.locator('#preview-prompt').click();
  await expect(page.locator('#prompt-text')).toContainText('- What is depicted: nothing about the people');
  // Muse described a character's hair color in 8 of 10 test captions: a character is critical, so orange below 85 %.
  await api(page, '/settings', {
    settings: {
      ...env.settings,
      mode: 'cloud',
      cloud_model: 'meta/muse-spark-1.3',
      preset: 'character',
      omitted_attributes: ['identity'],
    },
  });
  await page.reload();
  await expect(detail(page, 'hair_color')).toHaveClass(/uncertain/);
  await expect(recipe.locator('[data-attribute=hair_color]')).toBeChecked();
  await expect(detail(page, 'hair_color').locator('.lock-note')).toHaveText(
    'Switched on, this model described it in 8 of 10 test captions. Check the captions.',
  );
  // GPT follows every switch: all green.
  await api(page, '/settings', {
    settings: { ...env.settings, mode: 'cloud', cloud_model: 'gpt-6.1-sol', preset: 'style' },
  });
  await page.reload();
  await expect(page.locator('#recipe-form .caption-detail.uncertain, #recipe-form .caption-detail.locked')).toHaveCount(
    0,
  );
});

test('the offer and the recommended length follow the configured model', async ({ page }) => {
  const recipe = page.locator('#recipe-form');
  const note = page.locator('#length-recommendation');
  await recipe.locator('[name=preset]').selectOption('character');
  await page.locator('#apply-training-preset').click();
  // Local Qwen with reasoning: about 6.5 words for each of the 9 switched-on photo details.
  await expect(note).toHaveText('Shortest reliable length for this model and 9 switched-on details: 60 words.');
  await recipe.locator('[name=words]').fill('40');
  await expect(note).toHaveClass(/short/);
  await expect(recipe.locator('[data-attribute=identity]')).toBeEnabled();

  // A model we have not measured gets every switch and about 60 words, like Gemini.
  const base = { ...env.settings, preset: 'character', omitted_attributes: ['identity', 'hair_color'], words: 100 };
  for (const model of ['', 'unknown/vision']) {
    await api(page, '/settings', { settings: { ...base, mode: 'cloud', cloud_model: model } });
    await page.reload();
    for (const id of ['identity', 'hair_color', 'accessories'])
      await expect(recipe.locator(`[data-attribute=${id}]`)).toBeEnabled();
    await expect(page.locator('#recipe-form .lock-note:not([hidden])')).toHaveCount(0);
    await expect(note).toHaveText('Shortest reliable length for this model and 9 switched-on details: 60 words.');
    await expect(note).not.toHaveClass(/short/);
  }

  // Muse, like Gemini, needs about 60 words; its orange hair color switch stays free.
  await api(page, '/settings', { settings: { ...base, mode: 'cloud', cloud_model: 'meta/muse-spark-1.3' } });
  await page.reload();
  await expect(recipe.locator('[data-attribute=hair_color]')).toBeEnabled();
  await expect(recipe.locator('[data-attribute=identity]')).toBeEnabled();
  await expect(note).toHaveText('Shortest reliable length for this model and 9 switched-on details: 60 words.');
  // GPT needs about 40.
  await api(page, '/settings', { settings: { ...base, mode: 'cloud', cloud_model: 'openai/gpt-6.1-sol' } });
  await page.reload();
  await expect(note).toHaveText('Shortest reliable length for this model and 9 switched-on details: 40 words.');
});

test('the settings show the measured models and fill in the chosen one', async ({ page }) => {
  await page.locator('#open-settings').click();
  await expect(page.locator('#local-model-card')).toContainText('Qwen with reasoning');
  await page.locator('[data-mode=cloud]').click();
  const good = page.locator('#model-table .zone.good'),
    bad = page.locator('#model-table .zone.bad');
  await expect(good.locator('summary .name b')).toHaveText([
    'GPT 6.1 Sol',
    'Claude Opus 5.5',
    'Gemini 3.8 Flash',
    'Qwen 3.8 Max',
    'Grok 4.7',
    'Muse Spark 1.3',
    'GLM 5.3 FlashX',
  ]);
  await expect(bad.locator('summary .name b')).toHaveText([
    'GLM 5V Turbo',
    'MiMo 2.6 Flash',
    'DeepSeek V4.1 Flash',
    'MiMo 2.6 Pro',
    'Kimi K3',
  ]);
  // Details open on a click; "Use this model" fills the ID for the chosen provider.
  await good.locator('summary', { hasText: 'GPT 6.1 Sol' }).click();
  await expect(good.locator('details[open] .facts')).toContainText('Clear errors 0.0 / 10');
  // Each model's switches as measured: GPT follows them all; Muse's hair color is orange.
  await expect(good.locator('details[open] .switch-offer')).toHaveText('Detail switches: all green');
  await good.locator('details[open] [data-model]').click();
  await expect(page.locator('[name=cloud_model]')).toHaveValue('openai/gpt-6.1-sol');
  // The choice is saved at once: the recipe follows the new model without another click.
  await expect(page.locator('#settings-message')).toHaveText('GPT 6.1 Sol is set.');
  await expect.poll(async () => (await state(page)).settings.cloud_model).toBe('openai/gpt-6.1-sol');
  // Opus is not offered by Google directly: the choice switches to OpenRouter.
  await page.locator('#cloud-provider').selectOption('https://generativelanguage.googleapis.com/v1beta/openai');
  await good.locator('summary', { hasText: 'Claude Opus 5.5' }).click();
  await expect(good.locator('details[open]')).toHaveCount(1); // one model's details at a time
  await good.locator('details', { hasText: 'Claude Opus 5.5' }).locator('[data-model]').click();
  await expect(page.locator('[name=cloud_url]')).toHaveValue('https://openrouter.ai/api/v1');
  await expect(page.locator('[name=cloud_model]')).toHaveValue('anthropic/claude-opus-5.5');
  await good.locator('summary', { hasText: 'Muse Spark 1.3' }).click();
  await expect(good.locator('details[open] .switch-offer .tag.amber')).toHaveText([
    'Hair color · Character / person 8/10',
  ]);
  await expect(page.locator('#local-model-card .switch-offer .tag.amber')).toHaveCount(2);
  // A model we advise against can be chosen too: we recommend, we do not forbid.
  await bad.locator('summary', { hasText: 'DeepSeek V4.1 Flash' }).click();
  await bad.locator('details[open] [data-model]').click();
  await expect(page.locator('[name=cloud_model]')).toHaveValue('deepseek/deepseek-v4.1-flash');
  await expect(page.locator('#settings-message')).toHaveText('DeepSeek V4.1 Flash is set.');
  await page.locator('#settings-dialog .close-dialog').click();
});
