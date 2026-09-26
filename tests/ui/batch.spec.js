import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { CAPTION } from './global-setup.js';
import { card, env, expect, state, test } from './support.js';

test('captions selected images, keeps model responses and saves manual edits', async ({ page }) => {
  await page.locator('#select-all').uncheck();
  await card(page, 'second.png').locator('.card-select').check();
  await card(page, 'Waiting.png').locator('.card-select').check();
  await expect(page.locator('#generate')).toContainText('(2)');
  await page.locator('#generate').click();
  await expect(page.locator('#stop-job')).toBeVisible();
  await expect(card(page, 'second.png').locator('.status-label')).toHaveText(/Captioning…|Queued/);
  await expect(page.locator('#job-title')).toHaveText('Batch completed', { timeout: 20_000 });
  await expect(page.locator('#job-count')).toHaveText('2 / 2 · 2 saved');
  for (const name of ['second', 'Waiting']) {
    await expect(card(page, name + '.png').locator('.status-label')).toHaveText('Saved');
    expect(readFileSync(path.join(env.dataset, name + '.txt'), 'utf8')).toBe(
      `ohwx, ${CAPTION[0].toLowerCase()}${CAPTION.slice(1)}\n`,
    );
  }
  await expect(card(page, 'blue.png').locator('.status-label')).toHaveText('Waiting');

  await card(page, 'Waiting.png').click();
  await expect(page.locator('#caption-history')).toBeVisible();
  await expect(page.locator('#caption-history-title')).toHaveText('Model responses (1)');
  const editor = page.locator('#caption-editor');
  await editor.fill('ohwx, A gray rectangle, edited by hand.');
  await expect(page.locator('#caption-state')).toHaveText('● Unsaved edits');
  await page.keyboard.press('Control+s');
  await expect(page.locator('#toast')).toHaveText('Caption saved next to the image.');
  expect(readFileSync(path.join(env.dataset, 'Waiting.txt'), 'utf8')).toBe('ohwx, A gray rectangle, edited by hand.\n');
  expect(existsSync(path.join(env.dataset, '.caption-backups'))).toBe(true); // the replaced caption is kept
});

test('stopping a batch keeps unfinished images waiting and writes nothing for them', async ({ page }) => {
  await page.locator('#select-all').uncheck();
  await card(page, 'blue.png').locator('.card-select').check();
  await page.locator('#generate').click();
  await expect(card(page, 'blue.png').locator('.status-label')).toHaveText('Captioning…');
  await page.locator('#stop-job').click();
  await expect(page.locator('#job-title')).toHaveText('Batch stopped; saved captions have been preserved');
  await expect(card(page, 'blue.png').locator('.status-label')).toHaveText('Waiting');
  expect((await state(page)).job.running).toBe(false);
  expect(existsSync(path.join(env.dataset, 'blue.txt'))).toBe(false);
});

test('existing captions are skipped and left unchanged', async ({ page }) => {
  await expect(card(page, 'red.png').locator('.status-label')).toHaveText('Existing');
  await page.locator('#select-all').uncheck();
  await card(page, 'red.png').locator('.card-select').check();
  await page.locator('#generate').click();
  await expect(page.locator('#job-title')).toHaveText('Batch completed', { timeout: 20_000 });
  await expect(page.locator('#job-count')).toHaveText('1 / 1 · 0 saved · 1 skipped');
  expect(readFileSync(path.join(env.dataset, 'red.txt'), 'utf8')).toBe(env.pristine[path.join(env.dataset, 'red.txt')]);
});
