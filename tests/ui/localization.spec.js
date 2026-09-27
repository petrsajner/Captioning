import path from 'node:path';
import { env, expect, state, switchLanguage, test } from './support.js';

test('static panel texts follow the interface language', async ({ page }) => {
  // Texts only a language switch touches: they start as static data-i18n markup.
  await page.locator('#open-settings').click();
  await switchLanguage(page, 'cs');
  await expect(page.locator('#recipe-status')).not.toContainText('Settings are saved automatically');
  await expect(page.locator('#local-model-status')).not.toContainText('does not confirm image support');
  await switchLanguage(page, 'en');
  await expect(page.locator('#recipe-status')).toContainText('Settings are saved automatically');
  await expect(page.locator('#local-model-status')).toContainText('does not confirm image support');
});

test('switching language keeps drafts, detail choices and caption text', async ({ page }) => {
  const prompt = page.locator('#prompt-text');
  await page.locator('[data-attribute=identity]').uncheck();
  await page.locator('[data-attribute=background]').uncheck();
  await page.locator('#preview-prompt').click();
  await expect(prompt).toContainText('LEARN_WITH_LORA — DO NOT DESCRIBE: stable visual identity');
  await expect(prompt).toContainText('CONTROL_WITH_PROMPT — DESCRIBE IF VISIBLE: clothing');
  await page.locator('#prompt-dialog .close-dialog').click();

  const editor = page.locator('#caption-editor');
  const caption = 'Clothing, Saved, Waiting. This user text must stay unchanged.';
  await editor.fill(caption);
  await page.locator('#open-settings').click();
  await expect(page.locator('#find-local-servers')).toBeEnabled(); // the automatic server check has settled
  const scanned = await page.locator('#local-discovery-message').textContent();
  await page.locator('[name=local_url]').fill('http://127.0.0.1:12345/v1');
  await page.locator('#local-api-key').fill('qa-draft-key-not-to-save');
  await switchLanguage(page, 'cs');
  await expect(editor).toHaveValue(caption);
  await expect(page.locator('[name=local_url]')).toHaveValue('http://127.0.0.1:12345/v1');
  await expect(page.locator('#local-api-key')).toHaveValue('qa-draft-key-not-to-save');
  await expect(page.locator('[name=language]')).toHaveValue('English');
  await expect(page.locator('[data-attribute=identity]')).not.toBeChecked();
  await expect(page.locator('[data-attribute=clothing]')).toBeChecked();
  await expect(page.locator('#local-discovery-message')).not.toHaveText(scanned);
  await switchLanguage(page, 'en');
  await expect(page.locator('#local-discovery-message')).toHaveText(scanned);
  await switchLanguage(page, 'cs');
  await page.locator('#settings-dialog .close-dialog').click();
  expect((await state(page)).has_local_key).toBe(false);

  await page.locator('#save-caption').click();
  await expect(page.locator('#caption-state')).not.toHaveText(/^●/);
  await page.locator('#pick-folder').click();
  await expect(page.locator('#use-folder')).toBeEnabled();
  await expect(page.locator('#folder-grid img')).toHaveCount(4);
  await expect(page.locator('.tree-row.selected')).toHaveCount(1);
  await page.locator('#browse-path').fill(path.join(env.dataset, 'Waiting.png'));
  await page.locator('#folder-go').click();
  await expect(page.locator('#folder-error')).toBeVisible();
  await expect(page.locator('#folder-error')).not.toContainText('folder.');
  await page.locator('#folder-dialog .close-dialog').click();

  await page.locator('[name=output_format]').selectOption('bria_json');
  await expect(page.locator('[name=words]')).toBeDisabled();
  await expect(page.locator('#json-format-note')).toBeVisible();
  await expect(page.locator('#json-format-note')).not.toHaveText(/^FIBO JSON uses/);
  await page.locator('#preview-prompt').click();
  await expect(prompt).toContainText('short_description');
  await expect(prompt).toContainText('No total word-count constraint applies');
  await page.locator('#prompt-dialog .close-dialog').click();
  await page.locator('#open-settings').click();
  await switchLanguage(page, 'en');
  await page.locator('#settings-dialog .close-dialog').click();
  await page.locator('[name=output_format]').selectOption('normal');
  await expect(page.locator('#recipe-status')).toHaveText('Settings saved');

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(editor).toHaveValue(caption);
  await expect(page.locator('[data-attribute=identity]')).not.toBeChecked();
});
