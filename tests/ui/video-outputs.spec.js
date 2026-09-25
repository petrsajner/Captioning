import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { card, env, expect, test } from './support.js';

const read = (name) => readFileSync(path.join(env.dataset, name), 'utf8');
const H3 =
  'integrated_multimodal_description: [Shot 1] Live-action, photographic, a medium shot at eye level frames Velmira, a woman, in front of a plain colored wall. The camera holds a static shot.\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A\n';

test('video model outputs write their own caption files and open the character once', async ({ page }) => {
  const recipe = page.locator('#recipe-form');
  await recipe.locator('[name=output_format]').selectOption('wan');
  await expect(page.locator('#character-class-field')).toBeVisible();
  await expect(page.locator('#subject-field')).toBeHidden();
  await expect(recipe.locator('[name=language]')).toBeDisabled();
  await expect(recipe.locator('[name=format]')).toBeDisabled();
  await recipe.locator('[name=trigger]').fill('Velmira');
  await recipe.locator('[name=character_class]').fill('a woman');
  await expect(page.locator('#trigger-note')).toHaveText(
    'Written once where the character is first named: “Velmira, a woman, …”.',
  );
  await expect(page.locator('#output-note')).toContainText('image.jpg → image.wan.txt');

  await page.locator('#select-all').uncheck();
  await card(page, 'blue.png').locator('.card-select').check();
  await expect(page.locator('#generate')).toContainText('Create WAN 2.2 captions (1)');
  await page.locator('#generate').click();
  // The previous test's batch message may still show; wait for this batch's own count.
  await expect(page.locator('#job-count')).toHaveText('1 / 1 · 1 saved', { timeout: 20_000 });
  await expect(page.locator('#job-title')).toHaveText('Batch completed');
  expect(read('blue.wan.txt')).toBe('Velmira, a woman, stands in front of a plain colored wall. The light is even.\n');
  expect(existsSync(path.join(env.dataset, 'blue.txt'))).toBe(false);

  // All video models: the WAN file already exists and is skipped; LTX and H3 are created.
  await recipe.locator('[name=output_format]').selectOption('video_all');
  await expect(page.locator('#generate')).toContainText('Create captions for all video models (1)');
  await page.locator('#generate').click();
  await expect(page.locator('#job-count')).toHaveText('3 / 3 · 2 saved · 1 skipped', { timeout: 20_000 });
  await expect(page.locator('#job-title')).toHaveText('Batch completed');
  expect(read('blue.ltx.txt')).toBe(
    'A medium shot at eye level. Velmira, a woman, stands in front of a plain colored wall.\n',
  );
  expect(read('blue.h3.txt')).toBe(H3);
  await expect(card(page, 'blue.png').locator('.model-dot')).toHaveText(['WAN', 'LTX', 'H3']);

  // The inspector shows every caption file of the image; H3 keeps its three fields.
  await card(page, 'blue.png').click();
  await expect(page.locator('.caption-tab')).toHaveCount(5);
  await page.locator('.caption-tab[data-output=h3]').click();
  await expect(page.locator('#caption-output-path')).toContainText('blue.h3.txt');
  await page.locator('#caption-editor').fill('Velmira, a woman, stands.');
  await page.locator('#save-caption').click();
  await expect(page.locator('#toast')).toContainText('H3 captions need the three fields');
  expect(read('blue.h3.txt')).toBe(H3);
  page.once('dialog', (dialog) => dialog.accept()); // discard the rejected edit
  await page.locator('.caption-tab[data-output=wan]').click();
  await expect(page.locator('#caption-editor')).toHaveValue(
    'Velmira, a woman, stands in front of a plain colored wall. The light is even.',
  );
  await page.locator('.caption-tab[data-output=normal]').click();
  await expect(page.locator('#caption-output-path')).toContainText('blue.txt');
  await expect(page.locator('#caption-editor')).toHaveValue('');
});
