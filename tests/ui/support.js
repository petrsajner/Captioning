// Shared UI-test setup: every test starts from the fixture dataset, default recipe and English UI.
import { test as base, expect } from '@playwright/test';
import { readdirSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';

export const env = JSON.parse(process.env.CAPTION_STUDIO_UI);
export { expect };

export async function api(page, route, body) {
  const response = await page.request.post(new URL('/api' + route, env.url).href, {
    data: body,
    headers: { 'X-Caption-Client': '1' },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

export async function state(page) {
  return (await page.request.get(new URL('/api/state', env.url).href)).json();
}

// Remove captions and backups written by earlier tests and restore the fixture texts.
function restoreFixtures() {
  for (const folder of [env.dataset, path.join(env.dataset, 'sub'), env.bria]) {
    for (const entry of readdirSync(folder, { withFileTypes: true })) {
      const file = path.join(folder, entry.name);
      if (entry.isDirectory() && entry.name === '.caption-backups') rmSync(file, { recursive: true, force: true });
      else if (entry.isFile() && /\.(txt|json)$/i.test(entry.name) && !(file in env.pristine)) rmSync(file);
    }
  }
  for (const [file, text] of Object.entries(env.pristine)) writeFileSync(file, text, 'utf8');
}

export async function openDataset(page, folder = env.dataset) {
  await api(page, '/jobs/stop', {});
  restoreFixtures();
  await api(page, '/settings', { settings: env.settings });
  await api(page, '/import', { folder, recursive: false });
  await page.reload();
  await expect(page.locator('.image-card').first()).toBeVisible();
}

export const test = base.extend({
  page: async ({ page }, use) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(env.url); // the launch token becomes the session cookie
    await openDataset(page);
    await use(page);
    expect(errors, 'JavaScript errors in the page').toEqual([]);
  },
});

export function card(page, name) {
  return page.locator('.image-card', { has: page.locator('.card-name', { hasText: name }) });
}

export async function switchLanguage(page, value) {
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith('/api/ui-language') && response.ok()),
    page.locator('#ui-language').selectOption(value),
  ]);
  await expect(page.locator('html')).toHaveAttribute('lang', value);
}
