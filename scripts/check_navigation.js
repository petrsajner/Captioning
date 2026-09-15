// CLI browser verification: npx @playwright/cli -s=caption-nav run-code <this text>
// Run against an isolated test profile with output/navigation-fixture prepared.
async (page) => {
  const pathInput = page.locator('#browse-path');
  const report = [];
  const fixture = 'C:\\Users\\Petr\\Documents\\Captioning\\output\\navigation-fixture';
  const a = fixture + '\\Collection A';
  const first = a + '\\Set One', second = a + '\\Set Two';
  const waitPath = async path => {
    await page.waitForFunction(expected => document.querySelector('#browse-path').value === expected &&
      !document.querySelector('#use-folder').disabled, path);
    await page.waitForFunction(expected => document.querySelector('#folder-roots [aria-current]')?.dataset.treeOpen === expected, path);
  };
  const go = async path => {
    await pathInput.fill(path); await page.locator('#folder-go').click(); await waitPath(path);
  };
  try {
  if (await page.locator('#settings-dialog').evaluate(d => d.open))
    await page.locator('#settings-dialog .close-dialog').click();
  if (await page.locator('#folder-dialog').evaluate(d => d.open))
    await page.locator('#folder-dialog .close-dialog').click();
  await page.locator('#pick-folder').click();
  await page.waitForFunction(() => !document.querySelector('#use-folder').disabled);
  await go(first);
  await page.locator('#folder-roots').getByRole('button', {name:'Set Two', exact:true}).click();
  await waitPath(second); report.push('sibling folder through expanded tree');
  await page.waitForFunction(() => [...document.querySelectorAll('#folder-grid img')].some(i=>i.alt==='dog.jpg'&&i.complete&&i.naturalWidth>0));
  report.push('real image preview');
  await page.locator('#folder-back').click(); await waitPath(first);
  await page.locator('#folder-forward').click(); await waitPath(second); report.push('back and forward');
  await page.locator('#folder-up').click(); await waitPath(a); report.push('up button');
  await page.locator('#folder-breadcrumbs').getByRole('button',{name:'navigation-fixture',exact:true}).click();
  await waitPath(fixture); report.push('clickable ancestor breadcrumb');
  await page.keyboard.press('Alt+ArrowLeft'); await waitPath(a);
  await page.keyboard.press('Alt+ArrowUp'); await waitPath(fixture); report.push('history and parent shortcuts');
  await page.locator('#folder-roots').getByRole('button',{name:'Expand Collection B',exact:true}).click();
  await page.locator('#folder-roots').getByRole('button',{name:'Other Set',exact:true}).waitFor({state:'visible'});
  await page.locator('#folder-refresh').click(); await waitPath(fixture);
  if (await page.locator('#folder-roots').getByRole('button',{name:'Other Set',exact:true}).count() !== 1)
    throw Error('Refresh lost expanded sibling branch');
  report.push('lazy expansion retained during refresh');
  await pathInput.fill(fixture+'\\does-not-exist'); await page.locator('#folder-go').click();
  await page.locator('#folder-error').waitFor({state:'visible'}); await waitPath(fixture);
  await page.locator('#folder-back').click(); await waitPath(a); report.push('failed path preserved current folder and history');
  if (!await page.locator('#folder-forward').isEnabled()) throw Error('Forward history unexpectedly lost');
  await go(first);
  if (await page.locator('#folder-forward').isEnabled()) throw Error('New destination did not replace forward branch');
  report.push('new destination replaces forward history');
  const selectedLabel = page.locator('#folder-roots [aria-current]');
  await selectedLabel.focus(); await page.keyboard.press('ArrowLeft');
  if (await page.evaluate(() => document.activeElement.textContent) !== 'Collection A')
    throw Error('Left arrow on a leaf did not focus its parent');
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
  await waitPath(second); report.push('keyboard navigation between tree siblings');
  await page.locator('#folder-breadcrumbs button').first().click();
  await page.waitForFunction(() => document.querySelector('#folder-up').disabled && !document.querySelector('#use-folder').disabled);
  report.push('root disables parent navigation');
  await go(first);
  await page.locator('#use-folder').click();
  await page.waitForFunction(() => !document.querySelector('#folder-dialog').open && document.querySelectorAll('.image-card').length===1);
  report.push('confirmed folder imports selected dataset');
  await page.locator('#pick-folder').click(); await waitPath(first);
  await page.screenshot({path:'output/playwright/navigation-final.png'});
  return {passed:report.length, checks:report};
  } catch (error) { return {error:String(error), completedChecks:report, currentPath:await pathInput.inputValue()}; }
}
