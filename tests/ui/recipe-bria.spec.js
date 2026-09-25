import { readFileSync } from 'node:fs';
import path from 'node:path';
import { env, expect, state, test } from './support.js';

test('detail choices reach the prompt and BRIA JSON captions are validated on save', async ({ page }) => {
  const recipe = page.locator('#recipe-form');
  await recipe.locator('[name=preset]').selectOption('character');
  await page.locator('#apply-training-preset').click();
  await recipe.locator('[data-attribute=clothing]').uncheck();
  await expect
    .poll(async () => (await state(page)).settings.omitted_attributes.sort())
    .toEqual(['clothing', 'hair_color', 'identity']);

  await page.locator('#preview-prompt').click();
  await expect(page.locator('#prompt-dialog')).toBeVisible();
  const lines = (await page.locator('#prompt-text').textContent()).split('\n');
  expect(lines.some((line) => line.startsWith('LEARN_WITH_LORA') && line.includes('clothing'))).toBe(true);
  expect(lines.some((line) => line.startsWith('CONTROL_WITH_PROMPT') && line.includes('clothing'))).toBe(false);
  await page.locator('#prompt-dialog .close-dialog').click();

  await recipe.locator('[name=output_format]').selectOption('bria_json');
  await expect(recipe.locator('[name=format]')).toBeDisabled();
  await expect(recipe.locator('[name=words]')).toBeDisabled();

  await page.locator('#open-path').click();
  await page.locator('#folder-path').fill(env.bria);
  await page.locator('#import-path').click();
  await expect(page.locator('.image-card')).toHaveCount(1);
  const editor = page.locator('#caption-editor');
  const original = await editor.inputValue();
  expect(JSON.parse(original).short_description.startsWith('testdog')).toBe(true);
  await expect(page.locator('#caption-output-path')).toContainText('dog.json');

  const sidecar = path.join(env.bria, 'dog.json');
  const before = readFileSync(sidecar, 'utf8');
  await editor.fill('{"wrong":"schema"}');
  await page.locator('#save-caption').click();
  await expect(page.locator('#toast')).toContainText('BRIA/FIBO JSON');
  expect(readFileSync(sidecar, 'utf8')).toBe(before);

  await editor.fill(original);
  await page.locator('#save-caption').click();
  await expect(page.locator('#caption-state')).not.toHaveText(/^●/);
  expect(JSON.parse(readFileSync(sidecar, 'utf8')).short_description).toBe(JSON.parse(original).short_description);

  await page.reload();
  await expect(page.locator('[data-attribute]')).toHaveCount(13); // motion and camera movement are clip-only
  await expect(page.locator('[data-attribute]:visible')).toHaveCount(11);
  await expect(recipe.locator('[data-attribute=clothing]')).not.toBeChecked();
  await expect(recipe.locator('[name=output_format]')).toHaveValue('bria_json');
});
