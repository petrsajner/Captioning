export const $ = (id) => document.getElementById(id);

export const esc = (text) =>
  String(text ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );

// Caption detail checkboxes (data-attribute) are collected separately by the recipe.
export function formValues(form, base) {
  const out = { ...base };
  for (const el of form.elements)
    if (el.name && !el.dataset.attribute)
      out[el.name] =
        el.type === 'checkbox'
          ? el.checked
          : ['number', 'range'].includes(el.type) || el.name === 'image_size'
            ? Number(el.value)
            : el.value;
  return out;
}

export function fillForm(form, values) {
  for (const el of form.elements)
    if (el.name && el.name in values) {
      if (el.type === 'checkbox') el.checked = values[el.name];
      else el.value = values[el.name];
    }
}
