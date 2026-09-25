// Shared UI state. main.js provides render/refresh/relocalize so feature modules need not import it.
export const ui = {
  state: null, // latest /api/state snapshot
  selected: new Set(), // image ids ticked for the next batch
  active: null, // image shown in the inspector
  tab: null, // caption output open in the inspector (normal, bria_json, wan, ...)
  dirty: false, // the caption editor has unsaved edits
  busy: false, // a UI-initiated import or model start is in progress
  render: () => {},
  refresh: async () => {},
  relocalize: () => {},
};

export function hasBusy() {
  return ui.busy || ui.state?.job.running || ui.state?.importing;
}

// Ids a paused batch can continue with, limited to images still in the dataset.
export function resumeIds() {
  const { state } = ui;
  return state?.job.paused ? (state.job.remaining_ids || []).filter((id) => state.rows.some((r) => r.id === id)) : [];
}

// Outputs one batch creates for a Caption output choice.
export function outputsFor(format) {
  return format === 'video_all' ? ui.state.video_outputs : [format];
}

// Most urgent first: the state a card shows when one batch creates several outputs.
const URGENCY = [
  'invalid',
  'processing',
  'queued',
  'error',
  'review',
  'draft',
  'pending',
  'skipped',
  'existing',
  'saved',
];

// The caption state of an image for a Caption output choice; null when no such output applies.
export function captionView(row, format) {
  const slots = outputsFor(format)
    .map((output) => row.outputs[output])
    .filter(Boolean);
  if (slots.length < 2) return slots[0] || null;
  const status = URGENCY.find((s) => slots.some((slot) => slot.status === s)) || 'pending';
  return {
    status,
    exists: slots.every((slot) => slot.exists),
    phase: slots.find((slot) => slot.status === 'processing')?.phase || '',
    error: slots.find((slot) => slot.error)?.error || '',
  };
}
