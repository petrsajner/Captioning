import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { diagnostic, setLanguage, t, useCatalog } from '../ui/i18n.js';

const catalog = JSON.parse(readFileSync(new URL('../ui/locales/cs.json', import.meta.url), 'utf8'));
// setLanguage refreshes static markers and on-screen diagnostics; none exist here.
globalThis.document = { documentElement: {}, querySelectorAll: () => [], getElementById: () => null };

test('locale templates preserve values and translate complete diagnostics', () => {
  useCatalog(catalog);
  assert.equal(t('Caption'), 'Caption');
  setLanguage('cs');
  assert.equal(t('Caption'), catalog.messages.Caption);
  assert.equal(t('Open {name}', { name: 'Saved.png' }), catalog.messages['Open {name}'].replace('{name}', 'Saved.png'));
  assert.equal(t('HTTP 401: Invalid API key.'), 'HTTP 401: ' + catalog.messages['Invalid API key.']);
  assert.equal(
    t('Batch paused: HTTP 401: Invalid API key.'),
    catalog.messages['Batch paused: '] + 'HTTP 401: ' + catalog.messages['Invalid API key.'],
  );
  assert.equal(t('Verifying file: Saved.bin'), catalog.messages['Verifying file: '] + 'Saved.bin');
  assert.equal(t('An unknown provider message.'), 'An unknown provider message.');
  const notice = 'Retained the complete response (121 words; target about 100). The model did not shorten it further.';
  const oldNotice = t(notice);
  assert.notEqual(oldNotice, notice);
  setLanguage('en');
  assert.equal(diagnostic(oldNotice), notice);
});
