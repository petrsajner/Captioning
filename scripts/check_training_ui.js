// Run through playwright-cli run-code against the isolated training-qa profile.
async (page) => {
  const checks=[];
  try {
    if(await page.locator('#settings-dialog').evaluate(d=>d.open))await page.locator('#settings-dialog .close-dialog').click();
    if(await page.locator('#prompt-dialog').evaluate(d=>d.open))await page.locator('#prompt-dialog .close-dialog').click();
    const recipe=page.locator('#recipe-form');
    await recipe.locator('[name=preset]').selectOption('character');
    await page.locator('#apply-training-preset').click();
    await recipe.locator('[data-attribute=clothing]').uncheck();
    await page.waitForFunction(async()=>{const s=await (await fetch('/api/state')).json();return s.settings.learn_attributes.includes('identity')&&s.settings.learn_attributes.includes('clothing');});
    checks.push('attribute toggles saved and summarized');
    await page.locator('#preview-prompt').click();
    await page.locator('#prompt-dialog').waitFor({state:'visible'});
    const prompt=await page.locator('#prompt-text').textContent();
    if(!prompt.split('\n').some(l=>l.startsWith('LEARN_WITH_LORA')&&l.includes('clothing'))||prompt.split('\n').some(l=>l.startsWith('CONTROL_WITH_PROMPT')&&l.includes('clothing')))throw Error('Contradictory clothing instructions');
    checks.push('same policy reaches model prompt');
    await page.locator('#prompt-dialog .close-dialog').click();
    await recipe.locator('[name=output_format]').selectOption('bria_json');
    if(!await recipe.locator('[name=format]').isDisabled()||!await recipe.locator('[name=words]').isDisabled())throw Error('BRIA-only controls not applied');
    checks.push('BRIA mode disables text-only controls');
    await page.locator('#open-path').click();
    await page.locator('#folder-path').fill('C:\\Users\\Petr\\Documents\\Captioning\\output\\training-live\\bria-identity-learn');
    await page.locator('#import-path').click();
    await page.locator('#inspector-content').waitFor({state:'visible'});
    const editor=page.locator('#caption-editor'), original=await editor.inputValue();
    if(!JSON.parse(original).short_description.startsWith('testdog'))throw Error('JSON caption not loaded');
    if(!await page.locator('#caption-output-path').textContent().then(t=>t.includes('dog.json')))throw Error('Wrong sidecar extension');
    checks.push('JSON sidecar loaded into editor');
    await editor.fill('{"wrong":"schema"}');await page.locator('#save-caption').click();
    await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('BRIA/FIBO JSON'));
    checks.push('invalid JSON save rejected visibly');
    await editor.fill(original);await page.locator('#save-caption').click();
    await page.waitForFunction(()=>document.querySelector('#save-caption').disabled === false && !document.querySelector('#caption-state').textContent.startsWith('\u25cf'));
    checks.push('valid JSON manual save');
    await page.reload();
    await page.waitForFunction(()=>document.querySelectorAll('[data-attribute]').length===10);
    if(await recipe.locator('[data-attribute=clothing]').isChecked())throw Error('Training policy lost on reload');
    if(await recipe.locator('[name=output_format]').inputValue()!=='bria_json')throw Error('BRIA format lost on reload');
    checks.push('recipe and JSON format survive restart');
    await page.locator('#training-plan').scrollIntoViewIfNeeded();
    await page.screenshot({path:'output/playwright/training-final.png'});
    return {passed:checks.length,checks};
  }catch(error){return {error:String(error),checks};}
}
