// Starts a stand-in model server and Caption Studio on free ports with a temporary profile,
// then removes everything again. No user profile, dataset or installed copy is touched.
import { execFileSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const workspace = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const python = process.env.CAPTION_STUDIO_PYTHON || path.join(workspace, '.venv', 'Scripts', 'python.exe');
export const CAPTION = 'A plain colored rectangle fills the frame. The surface is even and matte.';
const MODEL_DELAY_MS = 1200; // long enough to observe and stop a running batch

function startModelServer() {
  const server = http.createServer((request, response) => {
    request.resume();
    request.on('end', () => {
      const reply = (status, data) => {
        response.writeHead(status, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify(data));
      };
      if (request.method === 'GET' && request.url === '/v1/models')
        return reply(200, { data: [{ id: 'fake-vision' }] });
      if (request.method === 'POST' && request.url === '/v1/chat/completions')
        return setTimeout(
          () => reply(200, { choices: [{ finish_reason: 'stop', message: { content: CAPTION } }] }),
          MODEL_DELAY_MS,
        );
      reply(404, {});
    });
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

// Text fixtures the tests may overwrite; restored before every test.
function pristineTexts(fixtures) {
  const texts = {};
  for (const file of [path.join(fixtures.dataset, 'red.txt'), path.join(fixtures.bria, 'dog.json')])
    texts[file] = readFileSync(file, 'utf8');
  return texts;
}

export default async function globalSetup() {
  const model = await startModelServer();
  const modelUrl = `http://127.0.0.1:${model.address().port}/v1`;
  // Inside the ignored output/ folder: the folder tree lists every sibling on the path, and the
  // system temp folder can hold thousands of them.
  const parent = process.env.CAPTION_STUDIO_UI_FIXTURES || path.join(workspace, 'output', 'ui-tests');
  mkdirSync(parent, { recursive: true });
  const root = mkdtempSync(path.join(parent, 'run-'));
  const fixtures = JSON.parse(
    execFileSync(python, [path.join(workspace, 'scripts', 'prepare_ui_fixtures.py'), root, modelUrl], {
      encoding: 'utf8',
    }),
  );
  const app = spawn(python, [path.join(workspace, 'app.py'), '--no-open'], {
    cwd: workspace,
    env: { ...process.env, CAPTION_STUDIO_DATA_DIR: fixtures.profile },
    stdio: 'ignore',
  });
  const launch = path.join(fixtures.profile, 'launch.json');
  for (let i = 0; i < 300 && !existsSync(launch); i++) {
    if (app.exitCode !== null) throw Error('Caption Studio exited during startup; run app.py --no-open to see why.');
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const { url } = JSON.parse(readFileSync(launch, 'utf8'));
  process.env.CAPTION_STUDIO_UI = JSON.stringify({ ...fixtures, url, modelUrl, pristine: pristineTexts(fixtures) });

  return async () => {
    try {
      // The venv launcher starts the interpreter as a child process: end the whole tree.
      execFileSync('taskkill', ['/PID', String(app.pid), '/T', '/F'], { stdio: 'ignore' });
    } catch {
      // Already stopped.
    }
    model.close();
    rmSync(root, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 });
  };
}
