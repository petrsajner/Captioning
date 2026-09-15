const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'ui/locales/cs.json'), 'utf8'));

test('locale templates preserve values and translate complete diagnostics', async () => {
  const context = vm.createContext({
    document: {documentElement:{}, querySelectorAll:()=>[], getElementById:()=>null},
    fetch:async()=>({ok:true,json:async()=>catalog}),
  });
  vm.runInContext(fs.readFileSync(path.join(root, 'ui/i18n.js'), 'utf8'), context);
  await vm.runInContext('i18n.ready', context);
  const evaluate = code => vm.runInContext(code, context);
  assert.equal(evaluate("t('Caption')"), 'Caption');
  evaluate("i18n.setLanguage('cs')");
  assert.equal(evaluate("t('Caption')"), catalog.messages.Caption);
  assert.equal(evaluate("t('Open {name}', {name:'Saved.png'})"), catalog.messages['Open {name}'].replace('{name}', 'Saved.png'));
  assert.equal(evaluate("t('HTTP 401: Invalid API key.')"), 'HTTP 401: ' + catalog.messages['Invalid API key.']);
  assert.equal(evaluate("t('Batch paused: HTTP 401: Invalid API key.')"), catalog.messages['Batch paused: '] + 'HTTP 401: ' + catalog.messages['Invalid API key.']);
  assert.equal(evaluate("t('Verifying file: Saved.bin')"), catalog.messages['Verifying file: '] + 'Saved.bin');
  assert.equal(evaluate("t('An unknown provider message.')"), 'An unknown provider message.');
  const notice = 'Retained the complete response (121 words; target about 100). The model did not shorten it further.';
  context.oldNotice = evaluate(`t(${JSON.stringify(notice)})`);
  assert.notEqual(context.oldNotice, notice);
  evaluate("i18n.setLanguage('en')");
  assert.equal(evaluate('diagnostic(oldNotice)'), notice);
});
