import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { card, env, expect, openDataset, test } from './support.js';

test('clips show their frames and get WAN I2V captions; photo-only outputs leave them out', async ({ page }) => {
  await openDataset(page, env.clips);
  const recipe = page.locator('#recipe-form');
  await expect(card(page, 'walk.mp4').locator('.clip-badge')).toContainText('▶');
  // Normal describes photos only; motion details appear only for the video models.
  await expect(card(page, 'walk.mp4').locator('.status-label')).toHaveText('Video models only');
  await expect(page.locator('[data-attribute=motion]')).toBeHidden();
  await recipe.locator('[name=output_format]').selectOption('wan_i2v');
  await expect(page.locator('[data-attribute=motion]')).toBeVisible();
  await expect(page.locator('[data-attribute=camera_motion]')).toBeVisible();
  await expect(card(page, 'still.png').locator('.status-label')).toHaveText('Clips only');
  await expect(card(page, 'walk.mp4').locator('.status-label')).toHaveText('Waiting');

  await card(page, 'walk.mp4').click();
  await expect(page.locator('#preview-video')).toBeVisible();
  await expect(page.locator('#preview-image')).toBeHidden();
  await expect(page.locator('#image-meta')).toContainText('96 × 64 px · 2 s · 24 fps · 48 frames');
  await expect(page.locator('#frame-strip figure')).toHaveCount(4);
  await expect(page.locator('#frame-strip figcaption').first()).toHaveText('0.25 s');
  await expect(page.locator('#clip-note')).toContainText('WAN 2.2 I2V (A14B) trains at 16 fps');
  await expect(page.locator('.caption-tab')).toHaveText(['.wan.txt', '.wan-i2v.txt', '.ltx.txt', '.h3.txt']);

  await recipe.locator('[name=trigger]').fill('Velmira');
  await recipe.locator('[name=character_class]').fill('a woman');
  await page.locator('#select-all').uncheck();
  await card(page, 'walk.mp4').locator('.card-select').check();
  await page.locator('#generate').click();
  // An earlier test's batch count may still show; wait for this batch's own file.
  await expect.poll(() => existsSync(path.join(env.clips, 'walk.wan-i2v.txt')), { timeout: 20_000 }).toBe(true);
  await expect(page.locator('#job-count')).toHaveText('1 / 1 · 1 saved');
  expect(readFileSync(path.join(env.clips, 'walk.wan-i2v.txt'), 'utf8')).toBe(
    'Velmira, a woman, stands in front of a plain colored wall. The light is even.\n',
  );
});
