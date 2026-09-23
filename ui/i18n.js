'use strict';
// English source strings are message IDs. Only explicitly marked UI is translated.
const i18n = {
  language: 'en',
  messages: {},
  patterns: [],
  legacyPatterns: [],
  legacy: new Map(),
  ready: null,
  setLanguage(language) {
    this.language = language === 'cs' ? 'cs' : 'en';
    document.documentElement.lang = this.language;
    this.applyStatic();
    for (const id of [
      'recipe-status',
      'key-status',
      'local-key-status',
      'local-discovery-message',
      'local-model-status',
      'settings-message',
      'toast',
      'folder-error',
    ]) {
      const element = document.getElementById(id);
      if (element) element.textContent = diagnostic(element.textContent);
    }
  },
  applyStatic() {
    for (const element of document.querySelectorAll('[data-i18n]')) element.textContent = t(element.dataset.i18n);
    for (const attribute of ['title', 'placeholder', 'aria-label', 'alt'])
      for (const element of document.querySelectorAll(`[data-i18n-${attribute}]`))
        element.setAttribute(attribute, t(element.getAttribute(`data-i18n-${attribute}`)));
  },
};
function t(key, values) {
  const source = String(key ?? '');
  let result = source;
  if (i18n.language === 'cs') {
    if (Object.hasOwn(i18n.messages, source)) result = i18n.messages[source];
    else if (!values) {
      for (const entry of i18n.patterns) {
        const match = source.match(entry.regex);
        if (match) {
          const captured = Object.fromEntries(entry.names.map((name, index) => [name, match[index + 1]]));
          return entry.target.replace(/\{(\w+)\}/g, (all, name) =>
            name === 'message' ? t(captured[name]) : (captured[name] ?? all),
          );
        }
      }
    }
  }
  return values ? result.replace(/\{(\w+)\}/g, (all, name) => String(values[name] ?? all)) : result;
}
// Existing sessions may contain Czech diagnostics from older versions. Only
// diagnostic fields use this adapter; filenames and generated text never do.
function diagnostic(text) {
  const source = String(text ?? '');
  if (i18n.legacy.has(source)) return t(i18n.legacy.get(source));
  for (const entry of i18n.legacyPatterns) {
    const match = source.match(entry.regex);
    if (match) {
      const captured = Object.fromEntries(entry.names.map((name, index) => [name, match[index + 1]]));
      return t(entry.target, captured);
    }
  }
  return t(source);
}
function messagePatterns(messages) {
  return messages
    .filter(([key]) => /\{\w+\}/.test(key))
    .map(([key, target]) => {
      const names = [];
      const parts = key.split(/(\{\w+\})/g).map((part) => {
        if (/^\{\w+\}$/.test(part)) {
          names.push(part.slice(1, -1));
          return '([\\s\\S]*?)';
        }
        return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      });
      return {
        regex: new RegExp('^' + parts.join('') + '$'),
        names,
        target,
        weight: key.replace(/\{\w+\}/g, '').length,
      };
    })
    .sort((a, b) => b.weight - a.weight);
}
i18n.ready = fetch('/assets/locales/cs.json')
  .then((response) => {
    if (!response.ok) throw Error('Unable to load interface translations.');
    return response.json();
  })
  .then((catalog) => {
    i18n.messages = catalog.messages;
    i18n.legacy = new Map(Object.entries(catalog.messages).map(([key, value]) => [value, key]));
    i18n.patterns = messagePatterns(Object.entries(catalog.messages));
    i18n.legacyPatterns = messagePatterns(
      Object.entries(catalog.messages)
        .filter(([key, value]) => key !== value)
        .map(([key, value]) => [value, key]),
    );
  });
