# Caption Studio development handoff

## Current release: 0.3.0 (2026-09-30)

Switches offered per model, reasoning per stage and provider, measured models in the settings. Petr's
rules (2026-09-29/30): a switch a model cannot follow must not be offered ("it would lie"); unknown
models get the strictest offer; lower Qwen quants and all local Qwen share one profile; all Anthropic
models count as Opus, all Gemini as Gemini Flash, GPT at Anthropic level; local Qwen always reasons (no
toggle); send each provider only the reasoning value it is known to accept, no blind fallback. The
measurements, blind judgements and the proposal Petr approved are in `output/switch-test` (PROPOSAL.md,
model-table-mockup.html; not in git).

- `capabilities.py`: model profiles ("full", "muse", "strict") by name and mode, the locked details per
  profile with their reason, `effective()` (a locked detail at the type default; the recipe keeps the
  user's choice) and the recommended length (words per switched-on photo detail: GPT, Claude, Qwen Max,
  Grok 4.4; Gemini, Muse, GLM and local Qwen 6.5, as Gemini described a close-up's pose in 7/9/10 of 10 at
  40/60/80 words; strict 8.8). Style content and background OFF are locked for every model (even Opus leaked 5 of 10 on
  one-subject prints), Muse locks a character's hair color ON, strict locks character identity ON,
  accessories OFF, object background OFF and the palette ON (measured as Qwen without reasoning).
- `provider.py`: `generate` applies `effective`; local Qwen reasons for `caption`/`retry_caption` and not
  for rewrites (`CaptionSession.stage_options`; managed always, external when `/props` shows
  `enable_thinking`, else the strict profile and `NO_LOCAL_REASONING`); cloud rewrites send
  `REWRITE_REASONING` (OpenRouter `reasoning.effort` minimal, Google `reasoning_effort` none, OpenAI
  low; "none" is rejected by OpenRouter, "minimal" by Google and gpt-6.1-sol). `<thinking>` blocks are
  removed; `not_a_caption` keeps a message to the user or stray markup for review; `http_error` adds the
  provider's message with an echoed key masked.
- `training.py`: palette is a style detail again (default OFF, `bria.py` and `anchor.py` follow it);
  pose NEVER forbids naming held objects and, in a close-up, the head turn; pose MUST asks for the head
  turn in a close-up; hair color MUST gives the tone in black-and-white; identity MUST names one face or
  body feature (facial hair belongs to the hairstyle; "clean-shaven" in the tested wording was copied
  onto men with a moustache, so it is not in the rule); object interaction NEVER covers sleeves and
  wristbands; `_combinations` adds the headwear rule and an object's placement without its surface;
  state "assembled or taken apart".
- UI: `models.js` (green/red model table, local card, "Use this model"), `recipe.js` (greyed switches
  with `data-choice` holding the user's state, length recommendation), `state.capabilities` from
  `service.snapshot`, the prompt preview shows the effective prompt. Manual 3.2 (recommended models),
  3.1 (reasoning), 7.3 (length), 7.4 (greyed switches), 10 (what happens automatically).
- Measured (40 words, blind): model table from the 55 hardest shots; switch offer from the full switch
  test (Opus, Gemini, GLM FlashX, local Qwen, GPT 10 photos per type; Qwen Max, Grok, Muse 5) and a
  re-measure of the borderline switches on a second photo set with the four rule fixes, all models.
- Still open: the switch test after implementation for local Qwen and Gemini with the final code;
  screenshots in the manual; the managed runtime's reasoning is assumed from its Qwen template.

## 0.2.10 (2026-09-28)

Exact caption rules per detail (Petr, 2026-09-29: "the model does not have to understand general
wording, the LoRA learns that; tell it exactly what must be in the caption and forbid outright what
must not"; and "a shortening rewrite must have the same rules").

- `training.py`: every detail has a `must` text (switched on) and a `never` text (switched off) with
  concrete words; `policy_prompt` writes them as CAPTION RULES with a MUST DESCRIBE and a NEVER
  DESCRIBE list, rules for details that touch each other (`_combinations`: hair color without the
  hairstyle, a learned background with lighting or composition described, and the reverse) and a
  final check against the NEVER list. The LEARN_WITH_LORA / CONTROL_WITH_PROMPT labels, the "what
  the LoRA learns" sentences (`anchor.PURPOSE`), `worn_line`, `STYLE_MEDIUM`, `STYLE_PALETTE` and the
  object's own never-describe lines are gone; `anchor.text_line` lets an object's own logo be
  transcribed when that detail is on.
- Examples must never come from the test photos, and lighting, composition and medium get only the
  options to choose from: the model copies examples word for word ("a dark military uniform" 31
  times in a first run whose examples came from the test photos).
- `provider.revision_instruction`: shortening and finishing get the same rules as the caption and
  delete what the NEVER list forbids (`training.described_details` is gone).
- `video.py`: WAN, LTX and H3 list only the parts the rules allow (a learned pose, background,
  lighting or composition is no longer asked for in the order line; LTX and H3 open without the
  shot when composition is learned).
- Live on Marvin (Q5, 2026-09-29), every photo detail of every LoRA type switched one at a time from
  the type's defaults, 10 photos per type (`output/switches-src`, Commons credits in
  `credits.json`), Normal at 40 and 20 words, 840 captions before and 840 after, each judged by an
  independent reviewer against the image. Clear leaks of a detail switched off: 194 before, 20 after
  (character 53 to 2, general 36 to 0, object 52 to 3, style 53 to 15). Leaks of clothing,
  accessories and background were already in 0.2.9 (12, 5 and 11 of 20), not new in 0.2.10.
  Details switched on are described more often (character lighting 5 to 16 of 20, composition 9 to
  16, identity 4 to 14; cube state 3 to 11). Still open: a style LoRA's palette is never described
  (0 of 20), a photo's medium rarely (5 of 20); a style LoRA still names its subjects (7 of 20) and
  background (7 of 20) when they are switched off; a blind accuracy check of the default captions
  found 16 clear errors in 80 captions after against 10 before (wrong pose, camera angle, copied
  examples such as "square jaw").

Described details stay in the caption (Petr, 2026-09-28: a user reported a character's clothing
missing from a caption; neither the LoRA type nor the output is known, so every path that could drop
a detail switched on in the recipe is covered).

- The detail switches worked: the prompt of every output asked for clothing. What could still drop it
  (the rules above later replaced `described_details` and `worn_line`):
  - `provider.py`: a caption over 120 % of the target is rewritten shorter without the image or the
    policy ("remove secondary wording"). The rewrite now lists the details the caption describes
    (`training.described_details`, WAN I2V only motion and camera) and keeps a few words about each.
  - `anchor.py`: a character prompt said the LoRA learns "the main character's appearance", which
    includes clothing. It now says the LoRA learns the details marked LEARN_WITH_LORA. With the
    identity learned, character and general prompts add that the described clothing and accessories
    are not part of it, even when distinctive (`worn_line`; not WAN I2V, and not hair, which could
    leak a learned hair color).
  - `training.py`: the policy asks for at least a few words about every visible described detail,
    also in a short caption.
  - `bria.py`: "use null for optional fields" could read as leaving `clothing` empty; null is now
    only for fields the policy omits or that are not visible, and every described detail's field is
    filled.
- Checked live on Marvin (Q5, 2026-09-29) against 0.2.9 with `scripts/check_video_captions_live.py`:
  20 character photos (7 Clover, 3 Holly, 10 free Wikimedia Commons photos of other people,
  `output/clothing-src/credits.json`), character type with the default details, outputs Normal,
  BRIA JSON, WAN, LTX and H3, at 100, 40 and 20 words (20: no BRIA), 280 captions per version.
  - 0.2.10 names clothing in 280 of 280 captions. 0.2.9 dropped it once, at 20 words: after
    shortening, the LTX caption of a woman in a navy suit kept only the pose and the building.
  - Share of the visible garments named (dress, jacket, trousers, apron, cap...): at 100 and
    40 words 97 % in 0.2.10 against 96 % in 0.2.9; at 20 words 90 % against 82 %.
  - Hair color and facial features: no leaks on the Clover and Holly photos in either version.
    Both versions sometimes name the hair color on six Commons photos, most often a dark pixie cut
    and a white cosplay wig: 17 captions in 0.2.10, 13 in 0.2.9. 0.2.10 also named green eyes
    twice on the cosplay photo; a thick moustache is described in both.

## Previous release: 0.2.9 (2026-09-28)

- The user manual, English and Czech PDF (`docs/manual`, see Verification and release workflow),
  ships with the application: `scripts/build.ps1` prints it and copies it into
  `dist\CaptionStudio\manuals\Caption-Studio-Manual-{EN,CS}.pdf`, so the installer and the portable
  ZIP both carry it. The installer adds Start menu shortcuts for both languages (names from the
  installer language) and replaces `{app}\manuals` on update. `scripts/smoke_package.py` and the
  sandbox test check the files; the sandbox test also checks the shortcuts.
- Marvin (`github.com/petrsajner/marvin`, Petr's published local Qwen harness) is the recommended
  local model: the manual features it, README names it, and server search labels 127.0.0.1:8080
  "Typical Marvin / llama.cpp address"; the search hint lists Marvin first.

## Previous release: 0.2.8 (2026-09-28)

- A graphics card is never required (Petr, 2026-09-28): the app, import and Cloud API captions
  run without one; only the optional local model's CUDA backend needs an NVIDIA driver. A first
  setup on a computer without the NVIDIA driver (`runtime.nvidia_driver_installed()`: no
  `System32\nvcuda.dll`) preselects **Cloud API**; the state carries `nvidia_gpu`. Local stays
  one click away and nothing is saved until the user confirms the setup.

## Previous release: 0.2.7 (2026-09-28)

The installer works on a clean Windows with nothing installed (Petr, 2026-09-28, preparing the
first release). Checked with a static import scan of every `.exe`, `.dll` and `.pyd`:

- The app package itself needs nothing beyond Windows; its own Visual C++ DLLs and Python
  ship with it. `mscoree.dll` (.NET Framework for pywebview) is part of Windows 10 and 11.
- The downloaded llama.cpp runtime needs `msvcp140.dll`, `vcruntime140.dll` and
  `vcruntime140_1.dll` (its CUDA build 14.44 or newer), which a clean Windows lacks, so the
  managed model would not start. `build.ps1` now bundles them from System32 into
  `_internal\vcredist` (the build fails below 14.44), and `runtime.py` copies them next to
  `llama-server.exe` when it extracts a runtime; Windows looks there first. `smoke_package.py`
  checks that they are packaged.
- The installer carries Microsoft's WebView2 Evergreen Bootstrapper
  (`installer\redist\MicrosoftEdgeWebview2Setup.exe`, Microsoft-signed) and runs it with
  `/silent /install` only when Microsoft's registry check finds no runtime (machine or user
  key). It installs per user without admin rights; without internet the app still opens in
  the browser.
- Not bundled, by nature: the NVIDIA driver for the CUDA backend and the downloads of the
  runtime and model (internet).
- Checked in Windows Sandbox (a clean Windows 11 Enterprise 26100 without Python or the Visual
  C++ runtime): the silent install took 7 s; the app window opened with WebView2 (already part
  of Windows 11, so the bootstrapper was correctly skipped); import of two photos and a clip,
  thumbnails, clip frames, a saved caption and the WAN prompt worked; the llama.cpp CPU runtime
  failed without the bundled DLLs (0xC0000135, DLL not found) and ran with them.

## Previous release: 0.2.6 (2026-09-27)

The setup shows what is available at a glance (Petr, 2026-09-27: choosing a connection must
not be guessing), instead of hiding the state behind the Find and Load buttons.

- `/api/state` lists `cloud_keys` and `local_keys`: the API addresses with a saved key,
  never the keys themselves (`KeyStore.endpoints()`).
- `settings.js`: every provider option carries its key mark ("key saved" / "no key"), and
  the status under the key field answers for the address in the field — including while
  switching providers, which used to show only a generic sentence and looked keyless.
  The summary line above the mode tabs reports the managed model, the answering local
  server and the saved key count; `findLocalServers` runs when the dialog opens, so a
  running server and its model count are visible without clicking.
- `main.js`: callers of `refresh` share one in-flight state read instead of being dropped
  when the poll was busy. An import that was dropped finished on the rows from before its
  own request: it kept the old selection and active image, so the inspector stayed empty
  and its message counted the old dataset (seen as a failing recipe/BRIA UI test).

## Previous release: 0.2.5 (2026-09-27)

A paused batch can be discarded instead of only continued (Petr, 2026-09-27: the Continue
button must not trap the user in the old selection), and the Czech interface keeps its
count forms.

- `service.py`: `cancel_job` also discards a paused batch — `paused` is cleared and
  `remaining_ids`/`remaining_tasks` emptied, so the next batch starts from the current
  selection. The run bar button reads "Discard batch" while paused and "Stop batch" while
  running.
- `ui/i18n.js`: a Czech value may carry the three count forms as "one|few|many" (1, then
  2-4, then 0 or 5+); the first numeric value picks the form. Used for "Loaded {v0}
  images.", the frame count and the found-server and available-model counts.
- The language switch no longer rewrites the static `data-i18n` texts of `recipe-status`,
  `key-status`, `local-key-status`, `local-discovery-message` and `local-model-status`.
  Rewriting their `textContent` dropped the marked span and the indented text matched no
  message again, so "Settings are saved automatically" and "A model appearing in the list
  does not confirm image support." stayed English in the Czech interface.
- `setup_local.py` accepts the `q2` profile like the application and the README.

## Previous release: 0.2.4 (2026-09-26)

- The notes under the trigger field show invented example names (Velmira, Zorbo, Zorvak style)
  and never repeat the entered trigger, which can be a real person's name (Petr, 2026-09-26: no
  real person's name may appear anywhere in the product). Docs and tests use invented names
  only.

## Previous release: 0.2.3 (2026-09-26)

Every LoRA type has its own caption details (Petr, 2026-09-26: the character set, with hair,
clothing and expression, made no sense for a product or a style; logo and text on a product
are a detail of their own; every type keeps its own choices).

- `training.py`: every detail lists the types that show it and may have its own name and
  instruction per type (`by_type`); `details_for(type)` gives a type's list, `TYPE_DEFAULTS`
  its defaults. The state sends `training_details` and `training_defaults`.
  - Character and general: unchanged.
  - Object: **Object appearance**, **Logo and text on the object** (new), Variant and state
    (new), Placement and orientation, Use and interaction (new), Environment, Lighting,
    Composition and camera, Medium.
  - Style: What is depicted, Pose and action, Environment, Light situation, Composition and
    camera, **Medium and technique**, **Color palette and grading** (new).
  - Bold details are left out by default; clips add motion and camera movement.
- `Settings.omitted_by_type` remembers the choices of every type; `omitted_attributes` is the
  current type's list, filtered to its details. A style recipe from 0.2.2 that left out "Visual
  style" also leaves out the palette.
- The object rule in `anchor.py` follows the two object details and now also covers summaries
  and color descriptions; the style rule is split into medium and palette. WAN I2V forbids
  every detail the LoRA learns. BRIA: the palette maps to `color_scheme`; an object's
  `appearance_details` go with its appearance.
- Live on Marvin (Q5), copies, Normal, BRIA and all video models:
  - style (4 Hiroshige prints), 20 captions: no medium or technique words;
  - object (4 Rubik's Cube photos), 20 captions: no cube colors in the text outputs; one H3
    named "a logo" on the cube. BRIA's `color_scheme` named the cube's colors in 3 of 4 until
    the rule covered color descriptions, then in 1 of 4 ("the multicolor of the cube"). Review
    `color_scheme` of object datasets.

## Previous release: 0.2.2 (2026-09-26)

The LoRA type ("What are you training?") decides how every caption output names what the LoRA
learns (Petr, 2026-09-26: trigger plus type instead of a subject name, fields per type, style
captions describe only the content, style trigger at the start, style defaults omit only style).

- New `captioning/anchor.py` holds the rules for all outputs (Normal, BRIA JSON, WAN, WAN I2V,
  LTX, H3):
  - character and object: the model writes `<character>` or `<object>` once and the app writes
    `{trigger}, {class},` there; later mentions use "the woman" or a pronoun;
  - style: the prompt forbids naming the medium or technique and asks for people described
    generically; the app starts the caption with `{trigger} style, ` (H3: inside `[Shot 1]`,
    which then opens with the composition instead of style words);
  - general: `{trigger}, ` at the start, as before.
- The recipe fields follow the type: Character name + Character type, Object name + Object
  type, Style name, Trigger word. **Main subject name** is gone; it made the model write a name
  that the trigger then repeated. `character_class` became `subject_class` (empty means `a
  person` or `an object`); old recipes migrate, and the old default `a person` becomes empty.
- For objects the identity detail is shown as **Object appearance**, and person details refer
  to people who hold, wear or use the object. With it omitted the prompt says outright never to
  describe the object's shape, parts, material, colors, markings or logo, and to call it only by
  its type.
- If the model forgets the token and writes the type with adjectives ("A 3x3 puzzle cube sits"),
  the name replaces that phrase; a type said again after the token ("<object>, the puzzle cube,")
  is removed.
- Video prompts follow the type as well (0.2.0 and 0.2.1 always wrote character prompts).
- After a style or general trigger the first letter is lowercased (`ohwx, a woman sits`), except
  "I" and words with more capitals.
- Fixed: a lowercase trigger at a sentence start was capitalized (`velmira` became `Velmira`), so
  case-sensitive trainers missed it. This affected video outputs since 0.2.0.
- Normal word counts still include the trigger; video outputs count the model's own text.
- `class_caption` gives the caption without its trigger for preservation (DOP). The same rule is
  in [LORA_TRAIN_HANDOFF.md](LORA_TRAIN_HANDOFF.md) section 6, checked against the app for every
  type and output.
- `scripts/check_video_captions_live.py` takes `--preset`, `--class` and `--outputs`.
- Live check on Marvin (Qwen3.8 27B Q5), copies, outputs Normal plus all video models, 16
  captions per type, 2–5 s each, all saved with the trigger exactly once:
  - character: 4 photos from Petr's character dataset, `a woman`: no hair color or facial
    features; hairstyle, clothing, expression, setting, light and shot described;
  - style: 4 prints from Hiroshige's "One Hundred Famous Views of Edo" (public domain, Wikimedia
    Commons), trigger `Zorvak`: every caption starts `Zorvak style, …`, none names the medium
    (no print, woodblock, ukiyo-e, illustration, painting); H3 opens with the composition;
  - object: 4 photos of a Rubik's Cube (CC BY / CC BY-SA, Wikimedia Commons), trigger `Zorbo`,
    `a puzzle cube`: the first run described the cube's colors, stickers and logo in 11 of 16
    captions; after the object line above, none of 16. Hands, a cat, settings and light are
    described.
  - The downloaded images and their credits are in `output/live-types-src` (not committed).

## Previous release: 0.2.1 (2026-09-25)

Video clips, following [VIDEO_LORA_PLAN.md](VIDEO_LORA_PLAN.md) section 5.

- Clips (`.mp4 .mov .webm .mkv .m4v .avi`) import next to photos. `captioning/media.py` reads
  them with PyAV (bundled; its wheel ships FFmpeg): size as displayed (the display matrix is
  applied), rate, length, frames, audio. A clip cut without re-encoding keeps its header's
  frame count, so the count comes from length × rate when the two disagree.
- Rows have `kind` (`image`/`clip`) and `clip`; outputs per kind are `MEDIA_OUTPUTS`: clips get
  WAN, **WAN 2.2 I2V** (`name.wan-i2v.txt`, motion and camera only, at most 100 words), LTX and
  H3; Normal and BRIA stay photo-only.
- The model gets a frame every `clip_interval` seconds (0.25/0.5/1, default 0.5) at the middles
  of equal parts, at most 30, about 1 MP each, labeled "Frame n at t s:". If the frames would
  exceed 18 MB they are re-encoded at lower JPEG quality (the frame count never drops).
- Every video model has its own photo and clip instructions (`video.py`). New details
  **Motion over time** and **Camera movement** (`"media": "clip"`) are sent for clips only.
  H3 clips describe their own camera movement; only photos get the static-shot sentence.
- Facial hair is part of the hair details: its color under hair color, its shape under hairstyle.
- Inspector: player (`/api/media/{id}`, range requests), meta line, model note, frame strip
  (`/api/clip-frames/{id}`, `/api/frame/{id}?t=`, cached). Cards show ▶ and the length.
- Live checks with copies (`scripts/check_video_captions_live.py`, reports in `output/`):
  - Marvin (Qwen3.8 27B Q5, b10935): 3 of Petr's own clips (6 s, 12 s, 68 s;
    13/25/30 frames) × 4 models: 12/12 saved, the trigger once each, motion and static camera
    described, 16–31 s per caption. A 30-frame request used 32,409 prompt tokens (the managed
    64k window fits) and 7.5 MB of frames; Marvin's preallocated VRAM did not grow.
  - Gemini 3.8 Flash (`https://generativelanguage.googleapis.com/v1beta/openai`,
    `gemini-3.8-flash`): the same clips 12/12 in one pass each, 14–22 s including frame
    decoding of 4K; 4 character photos × 3 models 12/12, 6–9 s. No hair color with
    `--omit identity hair_color`.
  - Managed runtime, measured 2026-09-25 on the RTX 5090 with the installed 0.2.1 runtime
    (`scripts/measure_managed_clip.py`, a 30-frame request from the 68 s clip, 32,409 prompt
    tokens; GPU memory as the rise over what other programs used):

    | Profile | After loading | Peak with 30 frames | One clip caption |
    |---|---:|---:|---:|
    | Q4 (projector on the GPU) | 18.65 GiB | 18.83 GiB | 17.6 s |
    | IQ3 (projector on the CPU) | 13.58 GiB | 13.61 GiB | 178.4 s |

    Both match Marvin's qualification (18.86 and 13.57 GiB). Q4 with Windows and a display is
    about 20 GiB, within the 22.5 GB limit for 24 GB cards; IQ3 fits 16 GB cards but encodes
    frames on the CPU, ten times slower. Q2 and Q5 were not downloaded and are not measured.
  - llama.cpp reused nothing between the four outputs of one clip (`timings.cache_n` 0, the
    30 frames took about 14.6 s of prompt processing each time), so "All video models" costs
    four full requests per clip, about 70 s with Q4.

## Previous release: 0.2.0 (2026-09-25)

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
- The detail "Hair and hairstyle" is split into **Hair color** (`hair_color`) and **Hairstyle**
  (`hairstyle`) (Petr, 2026-09-25). Saved recipes that omitted `hair` omit both. The character
  defaults omit identity and hair color. Versions before 0.2.0 reject the new IDs and would
  drop the saved detail choices when downgraded.
- Checked live on Marvin (Qwen3.8 27B Q5) with copies of four photos from Petr's character
  set (`scripts/check_video_captions_live.py`): 12/12 captions saved, the trigger once in
  each, hairstyles described and no hair color with `--omit identity hair_color`. Fixes came
  from these runs: no attribute names in the model shapes (the recipe decides), "the woman"
  for later mentions, LTX names the character in its opening shot sentence, and a missing
  token is placed at the first mention of the character type.
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

Normal writes `.txt`, BRIA `.json`, the video models `.wan.txt`, `.wan-i2v.txt` (clips),
`.ltx.txt` and `.h3.txt`.
Since 0.2.0 all of them coexist; a write checks and changes only its own file, and
skip-existing checks only the selected output's file. (Up to 0.1.13 `.txt` and `.json`
excluded each other and conversion archived the other file.) LORA Train reads `.txt` for
its image profiles and `.json` for FIBO. This application does not implement training or
the official trainer's metadata CSV export. What LORA Train needs to read the video model
files, the bridge fix and the per-model training notes are in
[LORA_TRAIN_HANDOFF.md](LORA_TRAIN_HANDOFF.md).

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
profile, from outside the source tree, with a minimal PATH.

Before a release, `python -m scripts.sandbox_test` checks the built installer on a clean
Windows in Windows Sandbox (the Windows feature must be enabled): it installs silently, opens
the app window, imports photos and a clip through the app's API, saves a caption and runs the
llama.cpp runtime without and with the bundled Visual C++ DLLs
(`scripts/sandbox/clean-install-test.ps1`). Results, logs and screenshots go to
`output/sandbox/results`; the script exits non-zero when a check fails. Closing the sandbox
window discards it. It checks localization
assets, import, thumbnails, sidecar writes and validated JSON format conversion.

The user manual (English and Czech PDF) is built from `docs/manual/manual.{en,cs}.html` and
`docs/manual/manual.css`. `node scripts/manual/capture.mjs` retakes the screenshots in
`docs/manual/img/{en,cs}`: it runs `python -m scripts.manual.prepare` (the demo dataset from
`docs/manual/demo`, public-domain prints with their captions, plus a generated clip, and two fresh
profiles under `output/manual`), starts the app from source for each language and imports the
dataset. The local server shown is Marvin (`github.com/petrsajner/marvin`, the recommended local
model in the manual): when nothing listens on 127.0.0.1:8080, the script answers Marvin's model list
(`q5`) there itself for that one screenshot. `node scripts/manual/build.mjs` prints
`dist/Caption-Studio-Manual-<version>-{en,cs}.pdf` with Edge. Update the texts when the interface
changes, then retake the screenshots and rebuild.

GitHub releases (the repository is public since 0.2.9, the first public release): the notes are
`docs/releases/RELEASE-NOTES-<version>.md`, published without their first heading, which becomes the
release title; the screenshots are in `docs/images` (taken from the installed app on the Clover
character dataset, which LORA Train and GIS present too). Assets: the installer, the portable ZIP,
`SHA256SUMS.txt` and both manuals under the stable names `Caption-Studio-Manual-{EN,CS}.pdf` from
`dist\CaptionStudio\manuals`, because README links to `releases/latest/download/…`.

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
