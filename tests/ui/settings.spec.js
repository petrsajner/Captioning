import { env, expect, state, test } from './support.js';

test('finds a running local server, loads its models and saves the connection', async ({ page }) => {
  await page.locator('#open-settings').click();
  await page.locator('[name=local_url]').fill(env.modelUrl);
  await page.locator('#find-local-servers').click();
  const found = page.locator('[data-server-index]', { hasText: env.modelUrl });
  await expect(found).toBeVisible({ timeout: 15_000 });
  await expect(found).toContainText('Models: 1');
  await found.click();
  await expect(page.locator('#local-discovery-message')).toHaveText(
    `Selected ${env.modelUrl}. Confirm with Save and continue.`,
  );
  await page.locator('#load-local-models').click();
  await expect(page.locator('#local-model-status')).toHaveText(/^Connected\. Available models: 1\./);
  await page.locator('#save-settings').click();
  await expect(page.locator('#settings-dialog')).not.toBeVisible();
  await expect(page.locator('#model-chip')).toContainText('fake-vision');
  expect((await state(page)).settings).toMatchObject({ local_source: 'external', local_model: 'fake-vision' });
});

test('invalid addresses are explained and unsaved dialog changes are discarded', async ({ page }) => {
  await page.locator('#open-settings').click();
  await page.locator('[name=local_url]').fill('http://192.168.1.2/v1');
  await page.locator('#find-local-servers').click();
  await expect(page.locator('#local-discovery-message')).toHaveText('Local mode requires a localhost address.');

  await page.locator('[data-mode=cloud]').click();
  await page.locator('#cloud-provider').selectOption('https://api.openai.com/v1');
  await expect(page.locator('[name=cloud_url]')).toHaveValue('https://api.openai.com/v1');
  await expect(page.locator('#key-status')).toHaveText('Keys are stored separately for each API address.');
  await page.locator('[data-mode=local]').click();
  await page.locator('#local-source').selectOption('managed');
  await expect(page.locator('#runtime-badge')).toHaveText('Not ready');
  await expect(page.locator('#start-model')).toBeDisabled();
  await page.locator('#settings-dialog .close-dialog').click();

  const saved = (await state(page)).settings;
  expect(saved).toMatchObject({ mode: 'local', local_source: 'external', cloud_url: 'https://openrouter.ai/api/v1' });
});
