import { $ } from './dom.js';
import { t } from './i18n.js';

let toastTimer;

export function toast(text, error = false, duration = error ? 11000 : 4500) {
  $('toast').textContent = t(text);
  $('toast').className = 'toast' + (error ? ' error' : '');
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($('toast').hidden = true), duration);
}

export async function api(path, body, method = 'POST') {
  const options = { method: body === undefined ? 'GET' : method, headers: { 'X-Caption-Client': '1' } };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch('/api' + path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error(t('The application is unavailable. Start it again.'));
  }
  if (!response.ok)
    throw Error(
      typeof data.detail === 'string'
        ? t(data.detail)
        : t('Check the entered values: ') + (data.detail || []).map((x) => t(x.msg)).join('; '),
    );
  return data;
}

// Runs a UI action and reports its failure instead of leaving an unhandled rejection.
export async function action(fn) {
  try {
    await fn();
  } catch (e) {
    toast(e.message, true);
  }
}
