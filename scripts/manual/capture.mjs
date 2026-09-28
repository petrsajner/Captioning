// Screenshots for the user manual in English and Czech: the app from source on the demo dataset
// (scripts/manual/prepare.py), each language with its own fresh profile. Writes docs/manual/img/<lang>.
// Run from the repository root: node scripts/manual/capture.mjs
import { chromium } from '@playwright/test';
import { execFileSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const python = path.join(root, '.venv', 'Scripts', 'python.exe');
// Paths on the screenshots read like an ordinary installation, not like the build computer.
const SHOWN_DATA = 'C:\\Users\\you\\AppData\\Local\\Programs\\Caption Studio\\data';
const SHOWN_DATASET = 'D:\\LoRA\\edo-prints';
const WIDTH = 1480;

function freePort() {
  return new Promise((resolve) => {
    const server = net.createServer().listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function startApp(profile) {
  const port = await freePort();
  const proc = spawn(python, ['app.py', '--no-open', '--port', String(port)], {
    cwd: root,
    env: { ...process.env, CAPTION_STUDIO_DATA_DIR: profile },
    stdio: 'ignore',
  });
  const launch = path.join(profile, 'launch.json');
  for (let i = 0; i < 200 && !existsSync(launch); i++) await new Promise((r) => setTimeout(r, 100));
  return { proc, url: JSON.parse(readFileSync(launch, 'utf8')).url };
}

// Marvin, the local Qwen harness, serves its model as "q5" on 127.0.0.1:8080. When Marvin itself is not
// running, a stand-in answers the model list the same way, so the setup shows what a Marvin user sees.
const MARVIN_PORT = 8080;
function standInMarvin() {
  return new Promise((resolve) => {
    const server = http.createServer((request, response) => {
      if (request.method === 'GET' && request.url === '/v1/models') {
        response.writeHead(200, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify({ object: 'list', data: [{ id: 'q5', object: 'model', owned_by: 'llamacpp' }] }));
      } else {
        response.writeHead(404);
        response.end();
      }
    });
    // A busy port means Marvin (or another server) already runs there; use it as it is.
    server.once('error', () => resolve(() => {}));
    server.listen(MARVIN_PORT, '127.0.0.1', () => resolve(() => server.close()));
  });
}

// Replace the demo profile and dataset paths wherever the page shows them.
async function tidy(page, pairs) {
  await page.evaluate((pairs) => {
    const swap = (text) => pairs.reduce((value, [from, to]) => value.split(from).join(to), text);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const value = swap(node.nodeValue);
      if (value !== node.nodeValue) node.nodeValue = value;
    }
    for (const el of document.querySelectorAll('input, textarea')) el.value = swap(el.value);
    for (const el of document.querySelectorAll('[title]')) el.title = swap(el.title);
  }, pairs);
}

// The area of an element down to its last visible content, so a tall panel has no empty tail.
async function contentBox(page, target) {
  return page.locator(target).evaluate((el) => {
    const outer = el.getBoundingClientRect();
    let bottom = outer.top;
    for (const child of el.querySelectorAll('*')) {
      const r = child.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) bottom = Math.max(bottom, r.bottom);
    }
    return { x: outer.left, y: outer.top, width: outer.width, height: Math.min(outer.height, bottom - outer.top + 28) };
  });
}

// The area of a panel from the top of one element to the bottom of another.
async function spanBox(page, panel, from, to, pad) {
  return page.locator(panel).evaluate(
    (el, [from, to, pad]) => {
      const outer = el.getBoundingClientRect();
      const top = from ? el.querySelector(from).getBoundingClientRect().top - pad : outer.top;
      const bottom = el.querySelector(to).getBoundingClientRect().bottom + 18;
      return { x: outer.left, y: top, width: outer.width, height: bottom - top };
    },
    [from, to, pad],
  );
}

async function shootSpan(page, file, panel, from, to, pairs, pad = 14) {
  await page.waitForTimeout(700);
  await tidy(page, pairs);
  const clip = await spanBox(page, panel, from, to, pad);
  await page.screenshot({ path: file, type: 'jpeg', quality: 90, animations: 'disabled', clip });
}

async function shoot(page, file, target, pairs, trim = false) {
  await page.waitForTimeout(700);
  await tidy(page, pairs);
  const options = { path: file, type: 'jpeg', quality: 90, animations: 'disabled' };
  if (target && trim) await page.screenshot({ ...options, clip: await contentBox(page, target) });
  else if (target) await page.locator(target).screenshot(options);
  else await page.screenshot(options);
}

const demo = JSON.parse(
  execFileSync(python, ['-m', 'scripts.manual.prepare'], { cwd: root, encoding: 'utf8' }).trim().split('\n').pop(),
);
const browser = await chromium.launch({ channel: 'msedge' });
try {
  for (const [language, profile] of Object.entries(demo.profiles)) {
    const dir = path.join(root, 'docs', 'manual', 'img', language);
    mkdirSync(dir, { recursive: true });
    const img = (name) => path.join(dir, name);
    const pairs = [
      [path.join(profile), SHOWN_DATA],
      [demo.dataset, SHOWN_DATASET],
    ];
    const app = await startApp(profile);
    const page = await browser.newPage({ viewport: { width: WIDTH, height: 940 }, deviceScaleFactor: 1.5 });
    try {
      await page.goto(app.url);
      await page.request.post(new URL('/api/import', app.url).href, {
        data: { folder: demo.dataset, recursive: false, append: false },
        headers: { 'X-Caption-Client': '1' },
      });
      await page.reload();
      const card = (name) => page.locator('.image-card', { has: page.locator('.card-name', { hasText: name }) });
      await card('dawn-in-the-yoshiwara').click();
      await page.locator('#caption-editor').waitFor();
      await shoot(page, img('main.jpg'), null, pairs);

      // Setup: cloud, the downloadable local model and an existing local server.
      await page.setViewportSize({ width: WIDTH, height: 1500 });
      await page.locator('#open-settings').click();
      await page.locator('#settings-dialog').waitFor();
      await page.locator('[data-mode=cloud]').click();
      await shoot(page, img('setup-cloud.jpg'), '#settings-dialog', pairs);
      await page.locator('[data-mode=local]').click();
      await page.locator('#local-source').selectOption('managed');
      await shoot(page, img('setup-local.jpg'), '#settings-dialog', pairs);
      // Marvin as the local server: found by the search and selected with one click.
      const stopMarvin = await standInMarvin();
      try {
        await page.locator('#find-local-servers').click();
        await page.locator(`.local-server:has-text("127.0.0.1:${MARVIN_PORT}")`).click();
        await shoot(page, img('setup-server.jpg'), '#settings-dialog', pairs);
      } finally {
        stopMarvin();
      }
      await page.locator('#settings-dialog details').evaluate((details) => (details.open = true));
      await page.locator('#settings-dialog details').scrollIntoViewIfNeeded();
      await shoot(page, img('setup-analysis.jpg'), '#settings-dialog details', pairs);
      await page.locator('#settings-dialog .close-dialog').click();

      // The recipe of a character LoRA, with its details.
      await page.setViewportSize({ width: WIDTH, height: 2100 });
      const recipe = page.locator('#recipe-form');
      await recipe.locator('[name=preset]').selectOption('character');
      await recipe.locator('[name=trigger]').fill('Velmira');
      await recipe.locator('[name=subject_class]').fill('a woman');
      // The fields and the details as two pictures; the whole panel is too tall for a page.
      const textCheck = 'label.check:has([name=text_in_image])';
      await shootSpan(page, img('recipe-character.jpg'), 'aside.recipe', null, '#length-policy-note', pairs);
      await shootSpan(page, img('details-character.jpg'), 'aside.recipe', '.label-heading', textCheck, pairs);
      await recipe.locator('[name=preset]').selectOption('object');
      await recipe.locator('[name=trigger]').fill('Zorbo');
      await recipe.locator('[name=subject_class]').fill('a backpack');
      await shootSpan(page, img('details-object.jpg'), 'aside.recipe', '.label-heading', textCheck, pairs);
      await recipe.locator('[name=preset]').selectOption('style');
      await recipe.locator('[name=trigger]').fill('Zorvak');
      await shootSpan(page, img('details-style.jpg'), 'aside.recipe', '.label-heading', textCheck, pairs);
      await page.setViewportSize({ width: WIDTH, height: 940 });

      // The instructions the model receives.
      await page.locator('#preview-prompt').click();
      await page.locator('#prompt-dialog').waitFor();
      await shoot(page, img('prompt.jpg'), '#prompt-dialog', pairs);
      await page.locator('#prompt-dialog .close-dialog').click();

      // A BRIA JSON caption and a clip with its caption files, player and frames.
      await recipe.locator('[name=output_format]').selectOption('bria_json');
      await card('fox-fires').click();
      await page.setViewportSize({ width: WIDTH, height: 1300 });
      await shoot(page, img('bria.jpg'), 'aside.inspector', pairs, true);
      await recipe.locator('[name=output_format]').selectOption('video_all');
      await card('ryogoku-bridge-pan').click();
      await page.locator('#frame-strip figure').first().waitFor();
      await page.waitForFunction(() => document.querySelector('#preview-video').readyState >= 2);
      // Play briefly and stop on a frame, so the player shows the picture instead of its loading state.
      await page.locator('#preview-video').evaluate(async (video) => {
        video.muted = true;
        await video.play().catch(() => {});
        await new Promise((resolve) => setTimeout(resolve, 800));
        video.pause();
        video.currentTime = 1.5;
        await new Promise((resolve) => video.addEventListener('seeked', resolve, { once: true }));
      });
      await shoot(page, img('clip.jpg'), 'aside.inspector', pairs, true);
      await page.setViewportSize({ width: WIDTH, height: 940 });
      await shoot(page, img('video-models.jpg'), null, pairs);
    } finally {
      await page.close();
      app.proc.kill();
    }
    console.log(`${language}: screenshots in ${dir}`);
  }
} finally {
  await browser.close();
}
