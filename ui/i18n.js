// English source strings are message IDs. Only explicitly marked UI is translated.
export const i18n = {
  language: 'en',
  messages: {},
  patterns: [],
  legacyPatterns: [],
  legacy: new Map(),
};

// Czech counts name things in three forms: 1, then 2-4, then 0 or 5+.
// A message carries them as "one|few|many"; the first numeric value decides which one is used.
function countIn(values) {
  for (const value of Object.values(values ?? {})) {
    const count = typeof value === 'number' ? value : /^\d+$/.test(String(value)) ? Number(value) : NaN;
    if (Number.isFinite(count)) return count;
  }
  return null;
}

function pluralForm(target, values) {
  const forms = String(target).split('|');
  if (forms.length < 2) return target;
  const count = countIn(values);
  return forms[count === 1 ? 0 : count !== null && count >= 2 && count <= 4 ? 1 : 2];
}

export function t(key, values) {
  const source = String(key ?? '');
  let result = source;
  if (i18n.language === 'cs') {
    if (Object.hasOwn(i18n.messages, source)) result = pluralForm(i18n.messages[source], values);
    else if (!values) {
      for (const entry of i18n.patterns) {
        const match = source.match(entry.regex);
        if (match) {
          const captured = Object.fromEntries(entry.names.map((name, index) => [name, match[index + 1]]));
          return pluralForm(entry.target, captured).replace(/\{(\w+)\}/g, (all, name) =>
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
export function diagnostic(text) {
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

export function useCatalog(catalog) {
  // A value with count forms ("one|few|many") matches as any of its forms.
  const variants = Object.entries(catalog.messages).flatMap(([key, value]) =>
    value.split('|').map((form) => [form, key]),
  );
  i18n.messages = catalog.messages;
  i18n.legacy = new Map(variants);
  i18n.patterns = messagePatterns(Object.entries(catalog.messages));
  i18n.legacyPatterns = messagePatterns(variants.filter(([form, key]) => form !== key));
}

export async function loadTranslations() {
  const response = await fetch('/assets/locales/cs.json');
  if (!response.ok) throw Error('Unable to load interface translations.');
  useCatalog(await response.json());
}

function applyStatic() {
  for (const element of document.querySelectorAll('[data-i18n]')) element.textContent = t(element.dataset.i18n);
  for (const attribute of ['title', 'placeholder', 'aria-label', 'alt'])
    for (const element of document.querySelectorAll(`[data-i18n-${attribute}]`))
      element.setAttribute(attribute, t(element.getAttribute(`data-i18n-${attribute}`)));
}

export function setLanguage(language) {
  i18n.language = language === 'cs' ? 'cs' : 'en';
  document.documentElement.lang = i18n.language;
  applyStatic();
  // Messages already on screen are diagnostics; re-translate them in place.
  // Static data-i18n markup is left to applyStatic: rewriting its textContent would drop the
  // marked span, and the surrounding indentation never matches a message again.
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
    if (element && !element.querySelector('[data-i18n]')) element.textContent = diagnostic(element.textContent);
  }
}
