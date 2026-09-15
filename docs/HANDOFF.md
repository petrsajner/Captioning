# Caption Studio development handoff

## Current release: 0.1.7 (2026-09-15)

The interface now asks users to choose which details to include in captions.
Checked means describe; unchecked means omit. The previous two-way learning controls
and dataset-dependence caveat were removed at the user's request. Keep this copy
direct and task-oriented. Do not reintroduce the caveat in help text.

English is the default interface language. Setup can switch immediately to Czech.
Caption language remains separate and unchanged. Implementation, diagnostics and
public documentation are English; Czech translations and lexical data live only
in locale resources. Historical release notes remain available in Git history.

## Architecture and boundaries

- `app.py`: desktop lifecycle, instance lock, private loopback server, file picker.
  `--ui-language en|cs` sets an explicit preference; the picker receives the current
  locale. Installer language is passed only on its optional first launch.
- `captioning/models.py`: validated settings and English model instructions.
  `ui_language` is independent of caption `language`. Old omitted-attribute settings
  migrate without changing behavior. Old output-token settings are ignored.
- `captioning/training.py`: shared attribute definitions and mandatory per-attribute
  model policy. **The persisted `learn_attributes` list means omitted details.**
  The UI stores unchecked attributes in this list. Do not invert legacy recipes.
- `captioning/bria.py`: FIBO structure, validation and normalization. Uses BRIA's
  ImageAnalysis field layout, plus optional scores from its fine-tuning example.
  Main subject is first in `objects`; mapped omitted fields are cleared, and the
  model is instructed to omit those details from free text too.
- `captioning/provider.py`: compatible image Chat Completions transport, full response
  retention, automatic text/JSON revisions and service-availability detection.
- `captioning/service.py`: import, batch lifecycle, immutable recipe per batch,
  persistent drafts/history, sidecar conflict and overwrite checks.
- `captioning/storage.py`: UTF-8 writes, byte-preserving backups, fingerprints and DPAPI.
- `captioning/runtime.py`: Caption Studio's own pinned llama.cpp/Qwen downloads and
  process. Never start, stop or reconfigure an external model server.
- `captioning/api.py`: local session protection and endpoints. `/api/ui-language`
  persists only the interface preference through the existing settings guards.
- `ui/i18n.js`: explicit static markers, message IDs and parameterized translations.
  Localize only UI/diagnostic fields; never captions, history bodies, prompts, model
  IDs, paths or editable values. Captured filenames remain opaque. Old stored Czech
  diagnostics have a presentation adapter; persisted data is not rewritten.
- `captioning/i18n.py`: shared locale resources for native UI and completion lexical data.

The application is standalone. Another development AI installation is not a runtime
dependency. Fresh installs download their own runtime only when explicitly requested.
Do not change external memory guards, trainer code or users' original datasets.

## Caption behavior retained from 0.1.6

The old provider sent `max_tokens=700` (at least 3072 for JSON) and treated most
non-stop finish reasons as failures. Those caps and the character limit were removed
in 0.1.6. Requests still contain no `max_tokens`, `max_completion_tokens`, `n_predict`
or application stop sequence. The owned llama-server uses `-n -1`.

Normal captions target approximately the selected word count, including trigger.
Complete results up to 120% are kept. Longer results get up to two text-only revision
attempts; the shortest complete response is retained even if still too long. Suspected
incomplete endings are completed when possible. No mechanical text slicing.

BRIA JSON ignores the normal word target. It is parsed, validated and repaired, with
up to two repair attempts. Unrepaired output remains `review`, preserves the received
draft and does not overwrite a valid sidecar. Validation also applies to manual saves.
Keys stay English; the recipe selects the language of descriptive values. Trigger
insertion happens in `short_description`.

`generation_history` retains responses. Cancelling a revision retains the latest
draft. Model/account/network failures pause remaining work instead of turning every
image into an error. `remaining_ids` lets Continue skip completed work. Diagnostics
in `logs/generation.jsonl` omit caption text, image data, prompts and keys.

For external llama.cpp with advertised `enable_thinking` support, caption requests
disable reasoning per request. Global server configuration is untouched.

Normal writes `.txt`; BRIA writes `.json`. Skip-existing covers either extension.
Explicit format conversion saves validated output before archiving the opposite
sidecar. Both fingerprints are checked. The separately developed LORA Train scanner
has historically preferred TXT, making this retirement important. This application
does not implement training or the official trainer's metadata CSV export.

## Verification and release workflow

Run the Python suite, `node --test tests/localization.test.cjs`, and browser checks.
`scripts/check_localization_ui.js` uses an isolated profile and the sibling directory
`i18n-fixtures` containing `Waiting.png` and `second.png`. It exercises language
switching, unsaved caption/key/connection preservation, checkbox-to-prompt behavior,
folder thumbnails/navigation/errors, BRIA controls and persistence across reload.

Build with `scripts/build.ps1`; it tests, gathers licenses, packages Python/UI with
PyInstaller, compiles Inno Setup and writes the portable ZIP plus SHA-256 manifest.
`scripts/smoke_package.py <exe>` runs a packaged executable in a fresh temporary
profile, from outside the source tree, with a minimal PATH. It checks localization
assets, import, thumbnails, sidecar writes and validated JSON format conversion.

Release 0.1.7 verification: 63 Python tests and the JavaScript localization test
passed. The browser workflow passed in both languages. Both the build output and
installed executable passed the clean-profile package test. The installer completed
with exit code 0; settings.json, keys.json and session.json retained their original
SHA-256 hashes. The installed desktop window was visually checked with the existing
dataset and simplified controls; no captions were regenerated or edited there.
Evidence: `output/build-0.1.7.log`, `output/install-0.1.7-report.json`,
`output/package-smoke.json`, `output/i18n-ui-check.log` and
`output/playwright/localization-{en,cs}.png`.

Never test by overwriting private image sidecars. Use `CAPTION_STUDIO_DATA_DIR` and
copied/public fixtures. Preserve existing installation settings, keys and session
when updating. Close only Caption Studio processes owned by this test or the user-
authorized installation workflow; do not terminate external models.

Build artifacts and logs are ignored in `dist/` and `output/`. Update the version in
`captioning/__init__.py`, `installer/caption-studio.iss` and `scripts/build.ps1` together.
Repository: `main`, `https://github.com/petrsajner/Captioning.git` (private).

## Earlier validation and remaining scope

Release 0.1.6 passed 59 Python tests. Live external Q5 completed five copied user
images with 37/49/46/44/36 words at target 40 and no failed captions. The 49-word
result was preserved after unsuccessful shortening. A public test image through
Gemini produced a 36-word caption without an application token cap. Originals were
unchanged. A later full-set run could not proceed because the external QwenHarness
memory guard stopped its server; an offline check retained remaining images as
pending. Do not report that full-dataset live test as completed.

The 0.1.7 changes do not alter model requests. Localization and caption control
behavior are verified with deterministic tests and browser checks; these are not
a new full-dataset/cloud inference benchmark. Vulkan, CPU and other PCs remain
hardware coverage beyond the current Windows validation. The installer is unsigned.
