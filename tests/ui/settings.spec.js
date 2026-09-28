import { env, expect, state, test } from './support.js';

test('finds a running local server, loads its models and saves the connection', async ({ page }) => {
  await page.locator('#open-settings').click();
  // The dialog checks the servers on its own; settle before the manual check.
  await expect(page.locator('#find-local-servers')).toBeEnabled();
  await page.locator('[name=local_url]').fill(env.modelUrl);
  await page.locator('#find-local-servers').click();
  await expect(page.locator('#find-local-servers')).toBeEnabled();
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
  await expect(page.locator('#find-local-servers')).toBeEnabled();
  await page.locator('[name=local_url]').fill('http://192.168.1.2/v1');
  await page.locator('#find-local-servers').click();
  await expect(page.locator('#local-discovery-message')).toHaveText('Local mode requires a localhost address.');

  await page.locator('[data-mode=cloud]').click();
  await page.locator('#cloud-provider').selectOption('https://api.openai.com/v1');
  await expect(page.locator('[name=cloud_url]')).toHaveValue('https://api.openai.com/v1');
  await expect(page.locator('#key-status')).toHaveText('No key is saved for this address.');
  await page.locator('[data-mode=local]').click();
  await page.locator('#local-source').selectOption('managed');
  await expect(page.locator('#runtime-badge')).toHaveText('Not ready');
  await expect(page.locator('#start-model')).toBeDisabled();
  await page.locator('#settings-dialog .close-dialog').click();

  const saved = (await state(page)).settings;
  expect(saved).toMatchObject({ mode: 'local', local_source: 'external', cloud_url: 'https://openrouter.ai/api/v1' });
});

test('saved keys and the running server are visible at a glance', async ({ page }) => {
  await page.locator('#open-settings').click();
  await expect(page.locator('#find-local-servers')).toBeEnabled();
  await expect(page.locator('#connection-summary')).toContainText('Local · the server is running');
  await expect(page.locator('#connection-summary')).toContainText('Cloud · saved keys: 0');
  await page.locator('[data-mode=cloud]').click();
  await expect(page.locator('#cloud-provider option[value="https://openrouter.ai/api/v1"]')).toContainText('no key');
  await expect(page.locator('#key-status')).toHaveText('No key is saved for this address.');
  await page.locator('#api-key').fill('qa-key-never-used');
  await page.locator('#save-settings').click();
  await page.locator('#open-settings').click();
  await page.locator('[data-mode=cloud]').click();
  await expect(page.locator('#cloud-provider option[value="https://openrouter.ai/api/v1"]')).toContainText('key saved');
  await expect(page.locator('#key-status')).toHaveText('Key saved for this address. Leave the field empty to keep it.');
  await expect(page.locator('#connection-summary')).toContainText('Cloud · saved keys: 1');
});

test('a first setup without an NVIDIA card preselects the cloud; with one, local', async ({ page }) => {
  // The state tells whether this computer has an NVIDIA driver; answer both ways for a first setup.
  for (const [nvidia, mode] of [
    [false, 'cloud'],
    [true, 'local'],
  ]) {
    await page.route('**/api/state', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.nvidia_gpu = nvidia;
      body.settings.setup_complete = false;
      await route.fulfill({ response, json: body });
    });
    await page.reload();
    await expect(page.locator('#settings-dialog')).toBeVisible();
    await expect(page.locator(`[data-mode=${mode}]`)).toHaveClass(/active/);
    await page.unroute('**/api/state');
  }
});
