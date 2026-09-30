import { expect, state, test } from './support.js';

test('the name fields, notes and detail names follow the LoRA type', async ({ page }) => {
  const recipe = page.locator('#recipe-form');
  const identity = page.locator('.caption-detail', { has: page.locator('[data-attribute=identity]') });
  await recipe.locator('[name=preset]').selectOption('object');
  // The notes always show invented example names, never the entered trigger.
  await recipe.locator('[name=trigger]').fill('Kestrin');
  await expect(page.locator('#trigger-label')).toHaveText('Object name');
  await expect(page.locator('#subject-class-label')).toHaveText('Object type');
  await expect(recipe.locator('[name=subject_class]')).toHaveAttribute('placeholder', 'an object');
  await recipe.locator('[name=subject_class]').fill('a backpack');
  await expect(page.locator('#trigger-note')).toHaveText(
    'Written once where the object is first named: “Zorbo, a backpack, …”.',
  );
  await expect(page.locator('#trigger-note')).not.toContainText('Kestrin');
  await expect(identity.locator('.detail-name')).toHaveText('Object appearance');
  // An object has its own details: no hair, clothing or expression.
  await expect(page.locator('#training-controls .detail-name')).toHaveText([
    'Object appearance',
    'Logo and text on the object',
    'Variant and state',
    'Placement and orientation',
    'Use and interaction',
    'Environment and background',
    'Lighting',
    'Composition and camera',
    'Medium',
    'Motion over time',
    'Camera movement',
  ]);
  await expect(page.locator('#training-plan')).toHaveText('7 of 9 details included in caption');
  await recipe.locator('[data-attribute=object_text]').check();

  await recipe.locator('[name=preset]').selectOption('style');
  await recipe.locator('[name=trigger]').fill('Kestrin');
  await expect(page.locator('#subject-class-field')).toBeHidden();
  await expect(page.locator('#trigger-label')).toHaveText('Style name');
  await expect(page.locator('#trigger-note')).toHaveText(
    'Written at the start of every caption: “Zorvak style, …”. The caption describes only the content.',
  );
  await expect(identity.locator('.detail-name')).toHaveText('What is depicted');
  await expect(recipe.locator('[data-attribute=hair_color]')).toHaveCount(0);
  await page.locator('#apply-training-preset').click();
  await expect.poll(async () => (await state(page)).settings.omitted_attributes).toEqual(['style', 'palette']);
  // Back on the object, its own choices return: the logo is still described.
  await recipe.locator('[name=preset]').selectOption('object');
  await expect(recipe.locator('[data-attribute=object_text]')).toBeChecked();
  await expect(recipe.locator('[data-attribute=identity]')).not.toBeChecked();
  await expect
    .poll(async () => (await state(page)).settings.omitted_by_type)
    .toEqual({ general: [], object: ['identity'], style: ['style', 'palette'] });
  await recipe.locator('[name=preset]').selectOption('style');
  await page.locator('#preview-prompt').click();
  await expect(page.locator('#prompt-text')).toContainText('- Medium and technique: never name or describe the medium');
  await expect(page.locator('#prompt-text')).not.toContainText('Kestrin');
});
