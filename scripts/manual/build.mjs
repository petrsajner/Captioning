// The user manual as PDF in English and Czech: docs/manual/manual.<lang>.html printed by Edge.
// Writes dist/Caption-Studio-Manual-<version>-<lang>.pdf. Run from the repository root:
// node scripts/manual/build.mjs [en|cs ...]
import { chromium } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const version = readFileSync(path.join(root, 'captioning', '__init__.py'), 'utf8').match(/__version__ = "(.+)"/)[1];
const languages = process.argv.length > 2 ? process.argv.slice(2) : ['en', 'cs'];
const TITLES = { en: 'User manual', cs: 'Uživatelská příručka' };

const footer = (language) => `
  <div style="width:100%; padding:0 17mm; font:7.5pt 'Segoe UI', Arial, sans-serif; color:#7a857f;
              display:flex; justify-content:space-between">
    <span>Caption Studio ${version} · ${TITLES[language]}</span>
    <span><span class="pageNumber"></span> / <span class="totalPages"></span></span>
  </div>`;

mkdirSync(path.join(root, 'dist'), { recursive: true });
const browser = await chromium.launch({ channel: 'msedge' });
try {
  for (const language of languages) {
    const source = path.join(root, 'docs', 'manual', `manual.${language}.html`);
    const target = path.join(root, 'dist', `Caption-Studio-Manual-${version}-${language}.pdf`);
    const page = await browser.newPage();
    await page.goto(pathToFileURL(source).href, { waitUntil: 'load' });
    // Every screenshot must be loaded; a missing one would print as an empty frame.
    const broken = await page.evaluate(() =>
      [...document.images].filter((img) => !img.complete || img.naturalWidth === 0).map((img) => img.src),
    );
    if (broken.length) throw new Error(`${language}: images not found: ${broken.join(', ')}`);
    // The version in the text (cover, file names) is always the one being built.
    await page.evaluate((version) => {
      for (const el of document.querySelectorAll('[data-version]')) el.textContent = version;
    }, version);
    // Czech typography: a one-letter preposition or conjunction never ends a line.
    if (language === 'cs')
      await page.evaluate(() => {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const node = walker.currentNode;
          if (node.parentElement.closest('code, kbd, pre')) continue;
          // Twice, so that neighbours such as "a v" are both bound.
          for (let pass = 0; pass < 2; pass++)
            node.nodeValue = node.nodeValue.replace(/(^|[\s(„])([aikosuvzAIKOSUVZ])\s+/g, '$1$2\u00a0');
        }
      });
    await page.pdf({
      path: target,
      preferCSSPageSize: true,
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: footer(language),
      tagged: true,
      outline: true,
    });
    await page.close();
    console.log(`${language}: ${target}`);
  }
} finally {
  await browser.close();
}
