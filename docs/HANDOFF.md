# Caption Studio development handoff

## Current release: 0.2.0 (2026-09-25)

Caption outputs for video character LoRAs, following [VIDEO_LORA_PLAN.md](VIDEO_LORA_PLAN.md)
(photos; clips follow in 0.2.1).

- New outputs **WAN 2.2** (`name.wan.txt`), **LTX-2.5** (`name.ltx.txt`), **MiniMax H3**
  (`name.h3.txt`) and **All video models**. Each model has its own instructions
  (`captioning/video.py`: `wan_prompt`, `ltx_prompt`, `h3_prompt`); they are English
  descriptions. The model names the character once as `<character>`; the app writes
  `{trigger}, {character_class},` there. H3 files are the official three fields; the
  app adds the labels, `[Shot 1]` and `N/A` sound and validates them on save.
- Every output is a separate file and they coexist. `.txt` and `.json` no longer exclude
  each other: saving one does not archive the other, and skip-existing checks only the
  selected output's file (Petr, 2026-09-25: LORA Train picks the file for its model).
- Rows hold one slot per output (`row["outputs"][output]`); sessions from 0.1.13 and
  earlier migrate once. The inspector has a tab per caption file; Regenerate creates only
  the open tab's output; Continue resumes the exact image/output pairs of a paused batch.
- Images that would share any caption file (`a.jpg` + `a.wan.png`) are rejected on import.
- The managed runtime matches Marvin: llama.cpp b10935, a new Q2_K_XL profile, `-c 65536`,
  `--fit off`, the image projector on the CPU for IQ3. Placements and memory figures come
  from Marvin's RTX 5090 qualification (`QWEN local/harness/measured_profiles.py`). An
  installed older runtime is replaced after the new one is downloaded.

## Previous release: 0.1.13 (2026-09-23)

User data now lives in a `data` folder next to `CaptionStudio.exe` (at the user's request:
every copy self-contained and runnable from any folder or drive). `captioning/paths.py`:

- `CAPTION_STUDIO_DATA_DIR` still overrides the location; tests always use it.
- A built program moves `%LOCALAPPDATA%\CaptionStudio` (pre-0.1.13) once when its own data
  folder is empty: one rename on the same drive; on another drive only settings, keys,
  session and logs are copied, then removed, and a notice explains how to move the model.
  Nothing moves while an older instance holds the lock or if copying fails.
- A source checkout uses `<repo>/data` (git-ignored) and never adopts installed data.
- An unwritable program folder falls back to `%LOCALAPPDATA%\CaptionStudio` with a notice.
- `runtime/verified.json` keys are relative to the runtime folder (old absolute keys are
  converted), so moved models stay verified without re-hashing.
- `build.ps1` refuses to build while `dist\CaptionStudio\data` exists, because PyInstaller
  deletes that folder. Never run a build output without `CAPTION_STUDIO_DATA_DIR`.
- The installer deletes `{app}\_internal` and `{app}\licenses` before copying, because it
  never removed files dropped from a release (0.1.8 still carried UCRT DLLs from an older
  build environment and pre-0.1.11 UI files). `{app}\data` is never touched.

Installed on the development machine over 0.1.8: the first start moved the data into
`{app}\data` with byte-identical settings, keys and session; a reinstall left the data
folder unchanged and the installed bundle identical to the build. Logs: `output/install-0.1.13*`.

## Earlier release: 0.1.12 (2026-09-23)

Tests and QA from the 0.1.8 code review (phase 5).

- `tests/test_runtime.py` covers the managed runtime: install (download, verification,
  extraction, resume after cancel, disk/HTTP/archive/checksum failures), start (arguments,
  one owned process, profile conflicts, exit or timeout while loading, busy port), stop,
  and the runtime endpoints' guards. A stand-in process is used; llama-server never runs.
- `npm run test:ui` is an automated Playwright suite replacing the hand-run snippets that
  hardcoded developer paths (see Verification). `build.ps1` runs it.
- A caption file that is not UTF-8 (for example cp1250 from older tools) now shows a
  clear message; it is still never overwritten.
- Live helper scripts use `data_directory()` and accept `--names` instead of fixed files.

Phase 4 (0.1.11) formatted the UI with Prettier, merged the stylesheets and split the UI
into ES modules; English text stays the diagnostic message ID (message codes would change
session.json and every message site). Keep `Generation failed.` and ` · {v0} drafts to
review` in the locale for sessions from 0.1.8 and earlier.

## Standing interface decisions

Users choose which details to include in captions: checked means describe,
unchecked means omit. The earlier two-way learning controls and dataset-dependence
caveat were removed at the user's request (0.1.7). Keep this copy direct and
task-oriented. Do not reintroduce the caveat in help text.

English is the default interface language. Setup can switch immediately to Czech.
Caption language remains separate and unchanged. Implementation, diagnostics and
public documentation are English; Czech translations and lexical data live only
in locale resources. Historical release notes remain available in Git history.

Real datasets are typically up to about 100 images. The 20,000-image import limit
is a guard, not a performance target; full-state polling and whole-file session
writes are deliberate simplifications at that scale.

## Architecture and boundaries

- `app.py`: desktop lifecycle, instance lock, private loopback server, file picker.
  `--ui-language en|cs` sets an explicit preference; the picker receives the current
  locale. Installer language is passed only on its optional first launch.
- `captioning/models.py`: validated settings and English model instructions.
  `ui_language` is independent of caption `language`. Old omitted-attribute settings
  migrate without changing behavior. Old output-token settings are ignored.
- `captioning/training.py`: shared attribute definitions and mandatory per-attribute
  model policy. `omitted_attributes` lists the details left out of captions (unchecked
  in the UI). Up to 0.1.9 the same list was saved as `learn_attributes`; it migrates
  on load without inversion. The model prompt still labels these LEARN_WITH_LORA.
- `captioning/video.py`: WAN 2.2, LTX-2.5 and MiniMax H3 instructions, the `<character>`
  replacement, H3 field wrapping and validation, trigger warnings.
- `captioning/bria.py`: FIBO structure, validation and normalization. Uses BRIA's
  ImageAnalysis field layout, plus optional scores from its fine-tuning example.
  Main subject is first in `objects`; mapped omitted fields are cleared, and the
  model is instructed to omit those details from free text too.
- `captioning/provider.py`: compatible image Chat Completions transport. `CaptionSession`
  runs one image's request sequence (caption, retry, JSON repair or text revision), keeps
  every response and returns a `CaptionResult`; instruction texts are separate functions.
- `captioning/service.py`: import, batch lifecycle, immutable recipe per batch,
  persistent drafts/history, sidecar conflict and overwrite checks.
- `captioning/storage.py`: UTF-8 writes, byte-preserving backups, fingerprints and DPAPI.
- `captioning/paths.py`: program folder, data folder (`data` next to the program) and the
  one-time move from the pre-0.1.13 location.
- `captioning/errors.py`: `UserError` messages are UI message IDs (API 400);
  `ProviderUnavailableError` pauses the batch. Anything else is a defect: logged, API 500.
  Keep `ValueError` for pydantic validators and JSON parsing only.
- `captioning/runtime.py`: Caption Studio's own pinned llama.cpp/Qwen downloads and
  process. Never start, stop or reconfigure an external model server.
- `captioning/api.py`: local session protection and endpoints. `/api/ui-language`
  persists only the interface preference through the existing settings guards.
- `ui/`: ES modules without a build step, loaded from `main.js` (entry, header/run bar,
  polling). `store.js` holds shared UI state and the render/refresh hooks main provides;
  `recipe.js`, `dataset.js` (grid, inspector, import, batches), `settings.js` and
  `folder-browser.js` own their panels; `api.js` and `dom.js` are helpers. No globals.
  One `style.css`. The server registers JavaScript/CSS MIME types explicitly.
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

Normal writes `.txt`, BRIA `.json`, the video models `.wan.txt`, `.ltx.txt` and `.h3.txt`.
Since 0.2.0 all of them coexist; a write checks and changes only its own file, and
skip-existing checks only the selected output's file. (Up to 0.1.13 `.txt` and `.json`
excluded each other and conversion archived the other file.) LORA Train reads `.txt` for
its image profiles and `.json` for FIBO. This application does not implement training or
the official trainer's metadata CSV export.

## Verification and release workflow

Run the Python suite, `npm test` and `npm run test:ui`. The UI suite (`tests/ui`, Playwright
with the system Microsoft Edge) creates fixtures under the ignored `output/ui-tests/`
(`scripts/prepare_ui_fixtures.py`), starts a stand-in model server and the app with a
temporary profile on free ports, and removes everything afterwards. It covers language
switching with drafts, detail choices and the prompt, folder navigation, BRIA JSON
validation, batches with stop and skip, caption editing and history, and settings.
Run other helper scripts from the repository root as `python -m scripts.<name>`; the
live checks read the profile from `data_directory()` and honour `CAPTION_STUDIO_DATA_DIR`.

Build with `scripts/build.ps1`; it runs ruff (lint and format check), mypy, pytest and the
JavaScript and UI suites, gathers licenses of the bundled runtime packages, packages Python/UI with PyInstaller,
compiles Inno Setup and writes the portable ZIP plus SHA-256 manifest.
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

Build artifacts and logs are ignored in `dist/` and `output/`. The version is defined only in
`captioning/__init__.py`; `scripts/build.ps1` passes it to Inno Setup and names the artifacts.
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
