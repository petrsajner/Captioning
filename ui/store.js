// Shared UI state. main.js provides render/refresh/relocalize so feature modules need not import it.
export const ui = {
  state: null, // latest /api/state snapshot
  selected: new Set(), // image ids ticked for the next batch
  active: null, // image shown in the inspector
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
