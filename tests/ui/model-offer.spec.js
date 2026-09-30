import { api, env, expect, state, test } from './support.js';

const detail = (page, id) => page.locator('.caption-detail', { has: page.locator(`[data-attribute=${id}]`) });

test('a switch the model cannot follow is greyed at the type default and the recipe keeps the choice', async ({
  page,
}) => {
  const recipe = page.locator('#recipe-form');
  await recipe.locator('[name=preset]').selectOption('style');
  // No measured model leaves out the content or background of a style image: both stay described.
  for (const id of ['identity', 'background']) {
    await expect(recipe.locator(`[data-attribute=${id}]`)).toBeDisabled();
    await expect(recipe.locator(`[data-attribute=${id}]`)).toBeChecked();
    await expect(detail(page, id).locator('.lock-note')).toHaveText(
      'No measured model leaves this out reliably in style images, so it stays described.',
    );
  }
  await expect(recipe.locator('[data-attribute=palette]')).toBeEnabled();
  await expect(recipe.locator('[data-attribute=palette]')).not.toBeChecked();
  // A recipe that left the background out keeps it; the caption uses the default.
  await api(page, '/settings', {
    settings: { ...env.settings, preset: 'style', omitted_attributes: ['style', 'palette', 'background'] },
  });
  await page.reload();
  await expect(recipe.locator('[data-attribute=background]')).toBeChecked();
  await recipe.locator('[data-attribute=palette]').check();
  await expect.poll(async () => (await state(page)).settings.omitted_attributes).toEqual(['background', 'style']);
  await page.locator('#preview-prompt').click();
  await expect(page.locator('#prompt-text')).toContainText('- Environment and background: where the main subject is');
  await expect(page.locator('#prompt-text')).toContainText('- Color palette and grading: one phrase');
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

  // An unmeasured cloud model: identity and accessories keep the character defaults, 80 words.
  const base = { ...env.settings, preset: 'character', omitted_attributes: ['identity', 'hair_color'], words: 100 };
  await api(page, '/settings', { settings: { ...base, mode: 'cloud', cloud_model: 'unknown/vision' } });
  await page.reload();
  await expect(recipe.locator('[data-attribute=identity]')).toBeDisabled();
  await expect(recipe.locator('[data-attribute=accessories]')).toBeDisabled();
  await expect(recipe.locator('[data-attribute=accessories]')).toBeChecked();
  await expect(note).toHaveText('Shortest reliable length for this model and 9 switched-on details: 80 words.');
  await expect(note).not.toHaveClass(/short/);

  // Muse describes everything but a character's hair color reliably; the cloud models need about 40 words.
  await api(page, '/settings', { settings: { ...base, mode: 'cloud', cloud_model: 'meta/muse-spark-1.3' } });
  await page.reload();
  await expect(recipe.locator('[data-attribute=hair_color]')).toBeDisabled();
  await expect(recipe.locator('[data-attribute=identity]')).toBeEnabled();
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
  await good.locator('details[open] [data-model]').click();
  await expect(page.locator('[name=cloud_model]')).toHaveValue('openai/gpt-6.1-sol');
  await expect(page.locator('#settings-message')).toHaveText('GPT 6.1 Sol selected. Save to use it.');
  // Opus is not offered by Google directly: the choice switches to OpenRouter.
  await page.locator('#cloud-provider').selectOption('https://generativelanguage.googleapis.com/v1beta/openai');
  await good.locator('summary', { hasText: 'Claude Opus 5.5' }).click();
  await expect(good.locator('details[open]')).toHaveCount(1); // one model's details at a time
  await good.locator('details', { hasText: 'Claude Opus 5.5' }).locator('[data-model]').click();
  await expect(page.locator('[name=cloud_url]')).toHaveValue('https://openrouter.ai/api/v1');
  await expect(page.locator('[name=cloud_model]')).toHaveValue('anthropic/claude-opus-5.5');
  await page.locator('#settings-dialog .close-dialog').click();
});
