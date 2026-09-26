import { expect, state, test } from './support.js';

test('the name fields, notes and detail names follow the LoRA type', async ({ page }) => {
  const recipe = page.locator('#recipe-form');
  const identity = page.locator('.caption-detail', { has: page.locator('[data-attribute=identity]') });
  await recipe.locator('[name=preset]').selectOption('object');
  await recipe.locator('[name=trigger]').fill('Zorbo');
  await expect(page.locator('#trigger-label')).toHaveText('Object name');
  await expect(page.locator('#subject-class-label')).toHaveText('Object type');
  await expect(recipe.locator('[name=subject_class]')).toHaveAttribute('placeholder', 'an object');
  await recipe.locator('[name=subject_class]').fill('a backpack');
  await expect(page.locator('#trigger-note')).toHaveText(
    'Written once where the object is first named: “Zorbo, a backpack, …”.',
  );
  await expect(identity.locator('.detail-name')).toHaveText('Object appearance');

  await recipe.locator('[name=preset]').selectOption('style');
  await recipe.locator('[name=trigger]').fill('Zorvak');
  await expect(page.locator('#subject-class-field')).toBeHidden();
  await expect(page.locator('#trigger-label')).toHaveText('Style name');
  await expect(page.locator('#trigger-note')).toHaveText(
    'Written at the start of every caption: “Zorvak style, …”. The caption describes only the content.',
  );
  await expect(identity.locator('.detail-name')).toHaveText('Identity / subject appearance');
  await page.locator('#apply-training-preset').click();
  await expect.poll(async () => (await state(page)).settings.omitted_attributes).toEqual(['style']);
  await page.locator('#preview-prompt').click();
  await expect(page.locator('#prompt-text')).toContainText('Never name or describe the medium');
  await expect(page.locator('#prompt-text')).not.toContainText('Zorvak');
});
