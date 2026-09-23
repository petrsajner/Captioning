import path from 'node:path';
import { env, expect, test } from './support.js';

test('folder dialog navigates by tree, history, breadcrumbs and keyboard, then imports', async ({ page }) => {
  const fixture = env.navigation;
  const collection = path.join(fixture, 'Collection A');
  const first = path.join(collection, 'Set One'),
    second = path.join(collection, 'Set Two');
  const roots = page.locator('#folder-roots');
  const pathInput = page.locator('#browse-path');
  const at = async (folder) => {
    await expect(pathInput).toHaveValue(folder);
    await expect(page.locator('#use-folder')).toBeEnabled();
    await expect(roots.locator('[aria-current]')).toHaveAttribute('data-tree-open', folder);
  };
  const go = async (folder) => {
    await pathInput.fill(folder);
    await page.locator('#folder-go').click();
    await at(folder);
  };

  await page.locator('#pick-folder').click();
  await expect(page.locator('#use-folder')).toBeEnabled();
  await go(first);
  await roots.getByRole('button', { name: 'Set Two', exact: true }).click();
  await at(second);
  await expect(page.locator('#folder-grid img[alt="dog.jpg"]')).toBeVisible();

  await page.locator('#folder-back').click();
  await at(first);
  await page.locator('#folder-forward').click();
  await at(second);
  await page.locator('#folder-up').click();
  await at(collection);
  await page.locator('#folder-breadcrumbs').getByRole('button', { name: 'navigation', exact: true }).click();
  await at(fixture);
  await page.keyboard.press('Alt+ArrowLeft');
  await at(collection);
  await page.keyboard.press('Alt+ArrowUp');
  await at(fixture);

  await roots.getByRole('button', { name: 'Expand Collection B', exact: true }).click();
  const otherSet = roots.getByRole('button', { name: 'Other Set', exact: true });
  await expect(otherSet).toBeVisible();
  await page.locator('#folder-refresh').click();
  await at(fixture);
  await expect(otherSet).toHaveCount(1); // refresh keeps other expanded branches

  await pathInput.fill(path.join(fixture, 'does-not-exist'));
  await page.locator('#folder-go').click();
  await expect(page.locator('#folder-error')).toBeVisible();
  await at(fixture); // a failed destination keeps the current folder
  await page.locator('#folder-back').click();
  await at(collection);
  await expect(page.locator('#folder-forward')).toBeEnabled();
  await go(first);
  await expect(page.locator('#folder-forward')).toBeDisabled(); // a new destination replaces forward history

  await roots.locator('[aria-current]').focus();
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator(':focus')).toHaveText('Collection A');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await at(second);

  await page.locator('#folder-breadcrumbs button').first().click();
  await expect(page.locator('#folder-up')).toBeDisabled();
  await expect(page.locator('#use-folder')).toBeEnabled();

  await go(first);
  await page.locator('#use-folder').click();
  await expect(page.locator('#folder-dialog')).not.toBeVisible();
  await expect(page.locator('.image-card')).toHaveCount(1);
  await expect(page.locator('.card-name')).toHaveText('one.png');
});
