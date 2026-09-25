# Plan: captions for video character LoRAs

Status: plan, not implemented. Written 2026-09-25 for release 0.2.x.

## 1. Goal and scope

Caption Studio gains caption outputs for three video models: **WAN 2.2**, **LTX-2.5** and
**MiniMax H3**. They are used to train character LoRAs that only keep a character's
appearance consistent across a film. Setting, mood, action and camera stay free and are
set later with prompts and reference frames.

Caption Studio only describes. Photos and video clips are prepared beforehand by the user.
The app never copies, converts, crops, trims or renames media. Every caption is a file
next to its media file. LORA Train later picks the files it needs (see section 10).

**Unchanged**:
- one recipe for the whole dataset;
- checked details are described and unchecked details are omitted (learned by the LoRA);
- the Normal `.txt` and BRIA `.json` outputs, including format conversion, archiving
  the other format, skip-existing and validation;
- sidecars in UTF-8 next to the media, with backups in `.caption-backups`, fingerprints
  and detection of external edits;
- batches, pause/continue, drafts, review, history, the inspector and editing;
- local managed, external and cloud models;
- the LORA Train bridge API (`/api/state` keys `version`, `job`, `importing`, `runtime`;
  `/api/import`; `/api/runtime/stop`).

**Out of scope**:
- training;
- media preparation or export;
- changes to LORA Train;
- style, motion or voice LoRAs.

## 2. Files next to each media file

| File | Output | Media | Notes |
|---|---|---|---|
| `name.txt` | Normal (existing) | photos | Model-independent caption. |
| `name.json` | BRIA JSON (existing) | photos | FIBO ImageAnalysis. Mutually exclusive with `name.txt` as today. |
| `name.wan.txt` | WAN 2.2 (new) | photos, clips | Coexists with all other files. |
| `name.ltx.txt` | LTX-2.5 (new) | photos, clips | Coexists with all other files. |
| `name.h3.txt` | MiniMax H3 (new) | photos, clips | Coexists with all other files. |

The model files follow the same rules as the existing sidecars:
- UTF-8 without BOM, text followed by one `\n`;
- written through `storage.write_caption`;
- replaced versions are backed up in `.caption-backups`;
- never overwritten when changed outside the app.

Writing a model file never archives or touches any other file.

`name` is the media file name without its last extension (`Path.with_suffix`). A media
file whose own stem ends in `.wan`, `.ltx` or `.h3` could claim a sibling's caption file:
`a.jpg` and `a.wan.png` would both need `a.wan.txt`. The import rule that already rejects
duplicate stems is generalized. Two media files in one folder that would share **any**
sidecar name are both marked invalid with the message "Two files would share the caption
file {name}. Rename one of them."

Trainers that read these names:
- **ai-toolkit:** `caption_ext: "wan.txt"`. A missing dot is added, so the caption path
  becomes `splitext(media) + ".wan.txt"` (`toolkit/config_modules.py:947-950`,
  `dataloader_mixins.py:348-350`).
- **musubi-tuner:** `caption_extension = ".wan.txt"` (`dataset/datasources.py:298, 715`).
- **diffusion-pipe and SimpleTuner:** these only read `<stem>.txt`. That concerns the
  handoff, not Caption Studio.

## 3. Caption rules

### 3.1 Rules shared by the three model outputs

1. **Identity uses the existing detail policy.** The preset "Character / person" already
   omits `identity`. Everything else stays as the user sets it, and `policy_prompt`
   applies unchanged. No new identity logic is added.
2. **Opening: trigger once, then the class in apposition.** Example:
   `Velmira, a woman, sits …`. After that the caption uses a pronoun and never repeats
   the name. Reasons, verified in trainer code:
   - ai-toolkit prepends the trigger only when the caption does not already contain it
     (case-sensitive substring count, `toolkit/prompt_utils.py:715-747`).
   - Its differential output preservation replaces the trigger with the class by plain
     substring replace (`dataloader_mixins.py:376-383`). That turns
     `Velmira, a woman,` into a harmless `woman, a woman,`, but `Velmira woman` into
     `woman woman`.
   - The musubi LTX fork's `--dop_args replace=` handles the apposition form cleanly.
3. **Where the trigger goes depends on the model.** WAN puts it at the very start. LTX
   puts it right after the opening shot phrase. H3 puts it inside `[Shot 1]` after the
   style and composition. The model writes the literal token `<character>` where the
   character is first named, and the app replaces it (see 4.4).
4. **The trigger should be an invented, readable name** (`Velmira`), not `sks` or `ohwx`.
   In the Qwen and Gemma tokenizers these "rare tokens" split into ordinary fragments
   (`oh|wx`). They also collide with ai-toolkit's substring matching (`sks` is inside
   `asks` and `tasks`). This is a hint in the UI and a warning (see 4.4), not a hard rule.
5. **English only.** All three prompt guides are English. The caption language setting
   does not apply to model outputs; the UI shows it disabled with a note.
6. **Description only, no tags.** The Format select is disabled for model outputs, as it
   already is for BRIA.
7. **No sound description.** These are video-only character LoRAs, and the vision model
   sees frames, not audio.
8. **Stills are described as stills.** There is no motion over time and no camera
   movement, except H3's fixed static-shot sentence (3.4).
9. **Clips add motion over time and camera movement** when the two new details are checked
   (4.2). A prepared clip is assumed to be one continuous shot.

### 3.2 WAN 2.2 (`name.wan.txt`)

Sources:
- Wan's own prompt rewriter builds T2V prompts as subject → action → background →
  camera, 60–200 words (`repos/Wan2.2/wan/utils/system_prompt.py:32-60`).
- The text encoder is umT5 with a 512-token limit.
- Photos train the T2V model. In every trainer, training the I2V-A14B model on stills
  conditions each still on itself and teaches nothing (ai-toolkit
  `wan22_14b_i2v_model.py:121-135`; diffusion-pipe refuses images, `wan.py:291-292`).

Shape: one paragraph of plain sentences in this order:
1. `<character>` and the action;
2. the details that are included (clothing, accessories, hair, expression);
3. the setting;
4. the lighting;
5. shot size and camera angle, and for clips the camera movement.

Photo example (identity omitted, everything else described):

> Velmira, a woman, sits at a café table by the window with her chin resting on one hand.
> She wears a grey wool coat over a white shirt and a thin silver necklace, and her
> shoulder-length dark hair is tucked behind one ear. She looks at the camera with a faint
> smile. The café has wooden tables, and a rainy street is visible through the window.
> Soft daylight falls from the left. Medium close-up at eye level with a shallow depth of
> field.

Clip example:

> Velmira, a woman, sits at a café table by the window looking out at the rain, then turns
> her head toward the camera and smiles. She wears a grey wool coat over a white shirt.
> The café has wooden tables and a rainy street outside. Soft daylight falls from the
> left. Medium close-up at eye level; the camera slowly pushes in.

### 3.3 LTX-2.5 (`name.ltx.txt`)

Sources:
- LTX prompt guide: one flowing paragraph in the present tense, 4–8 sentences, beginning
  with the shot, then the scene, lighting, action, character and camera.
- LTX character-LoRA guidance: describe constant features consistently, and train
  visual-only LoRAs without audio.
- The text encoder is Gemma 4 12B with a 1024-token limit.

Shape: the paragraph opens with shot size and camera angle. The next sentence introduces
`<character>` and the action, followed by the included details, the setting and the
lighting. Clips then add the motion in time order and the camera movement. There is no
audio sentence.

Photo example:

> A medium close-up at eye level with a shallow depth of field. Velmira, a woman, sits at
> a café table by the window, her chin resting on one hand, and looks at the camera with a
> faint smile. She wears a grey wool coat over a white shirt and a thin silver necklace,
> and her shoulder-length dark hair is tucked behind one ear. Wooden tables fill the small
> café, and rain streaks the window behind her. Soft daylight from the left lights her
> face.

Clip example:

> A medium close-up at eye level. Velmira, a woman, sits at a café table and gazes out of
> the rain-streaked window. After a moment she turns her head toward the camera and breaks
> into a slow smile. She wears a grey wool coat over a white shirt. Soft daylight from the
> left lights her face as the camera slowly pushes in.

### 3.4 MiniMax H3 (`name.h3.txt`)

Sources:
- The official prompt skill defines three fields for T2VA/I2VA/FL2VA
  (`repos/MiniMax-H3/.claude/skills/h3-prompt-writing/references/base-en.txt:36-48`).
  `[Shot 1]` opens with the style and the initial composition. Camera movement is written
  as natural English with type, amplitude and speed, for example "The camera holds a
  static shot".
- The field labels are literal text: "Preserve the exact field names" (`SKILL.md:14`).
- All trainers feed the caption verbatim, so labels in a caption reach the model
  (musubi `minimax_h3/text_encoder.py:124-125`; ai-toolkit
  `minimax_h3/src/text_encoder.py:8-10`).
- ai-toolkit's H3 image caption template writes one `[Shot 1]` with no camera motion, and
  both sound fields `N/A` for stills (`ui/src/helpers/captionOptions.ts:62-74`).
- musubi's identity recipe keeps outfit, pose and setting described and leaves appearance
  out (`docs/minimax_h3_advanced.md:130-135`).
- The text encoder is Qwen3-VL with a 512-token limit.

Shape (exact bytes; `\n\n` between the fields):

```text
integrated_multimodal_description: [Shot 1] <body>

overall_soundscape: N/A

non_diegetic_music: N/A
```

The vision model writes only `<body>`, and the app adds the labels, `[Shot 1]` and the
sound fields (4.4). `<body>` is built as follows:
- It opens with the style and the composition, for example "Live-action, photographic, a
  medium close-up at eye level frames `<character>` …".
- Style words come from the guide's list: `Live-action`, `Cinematic`, `2D-animated`,
  `3D CG`, and so on.
- Stills end with "The camera holds a static shot."
- Clips describe the action in time order and the camera movement.
- Both sound fields are always `N/A` (decision D2).

Photo example:

```text
integrated_multimodal_description: [Shot 1] Live-action, photographic, a medium close-up at eye level frames Velmira, a woman, seated at a café table by the window with her chin resting on one hand, looking at the camera with a faint smile. She wears a grey wool coat over a white shirt and a thin silver necklace; her shoulder-length dark hair is tucked behind one ear. Wooden tables fill the café and rain streaks the window behind her, softly out of focus. Soft daylight falls from the left. The camera holds a static shot.

overall_soundscape: N/A

non_diegetic_music: N/A
```

Clip example body:

> Live-action, photographic, a medium close-up at eye level frames Velmira, a woman, seated
> at a café table by the window, gazing at the rain outside. She turns her head toward the
> camera and slowly smiles. She wears a grey wool coat over a white shirt. Wooden tables
> fill the café behind her in soft daylight from the left. The camera pushes in with small
> amplitude at slow speed toward her face.

### 3.5 Media-specific notes (informational only; the app does not change media)

The inspector shows these for clips, so the user can see whether a clip suits a model:

| | WAN 2.2 | LTX-2.5 | MiniMax H3 |
|---|---|---|---|
| Frame rate | 16 fps (A14B), 24 fps (5B) | 24–25 fps | 24 fps |
| Frame counts used by trainers | 4n+1, up to 81 (A14B) | 8n+1, up to 121 | 17n+5 |
| Stills | 1 frame, T2V model | 1 frame | 1 frame, static shot |

## 4. Behavior in the app

### 4.1 Recipe

- **Caption output** gets three options after the existing two:
  - `WAN 2.2 · .wan.txt`
  - `LTX-2.5 · .ltx.txt`
  - `MiniMax H3 · .h3.txt`
- **One output per batch, as today.** A batch creates the selected output. Captions for
  the other models are created by switching the output and running again (decision D5).
- **New field "Character type"** (`character_class`), shown only for model outputs:
  - options `a woman`, `a man`, `a person` (default), and a custom text of up to 40
    characters;
  - it is the class phrase in the opening (3.1) and tells the model which pronouns to use.
- **Trigger word** keeps its field and its limits. For model outputs:
  - the placeholder becomes "e.g. Velmira";
  - the note becomes "Inserted once as 'Velmira, a woman,' where the character is first
    named";
  - an empty trigger is allowed, and the opening is then only the class phrase
    (`A woman sits …`).
- **Main subject name** (`subject`) is hidden for model outputs, because the trigger is the
  name.
- **Format** (tags) and **Caption language** are disabled with the note "Video model
  captions are English descriptions."
- **Target length** applies:
  - WAN and LTX: to the whole caption;
  - H3: to `<body>`.
- **Output note:** `image.jpg → image.wan.txt` (or `.ltx.txt` / `.h3.txt`), with the text
  "Same folder, UTF-8. Other caption files are not changed."
- **Apply defaults for this LoRA type** is unchanged: Character omits `identity`.

### 4.2 Details (attributes)

`training.ATTRIBUTES` gains two entries, flagged `"media": "clip"`:
- `motion`, "Motion over time": "What the main subject does from the start to the end of
  the clip." Instruction: "movement and actions of the main subject over time, in order".
- `camera_motion`, "Camera movement": "Pans, pushes, tracking and other camera moves."
  Instruction: "camera movement with type, amplitude and speed".

They show only when a model output is selected. They default to included, because
`omitted_attributes` lists omitted details only, so old recipes include them automatically.
`policy_prompt` emits them only for clip requests.

`bria.py` must ignore these two IDs. Its mapping only reads the groups it knows (lines
139-170); a test confirms this.

### 4.3 Dataset and batch

- Every row keeps its existing fields for the Normal/BRIA caption.
- New `row["outputs"]` holds one slot per model: `{"wan": Slot, "ltx": Slot, "h3": Slot}`.
  - `Slot` has the fields `caption`, `status`, `error`, `notice`, `exists`, `seconds`,
    `phase` and `generation_history`, with the same meaning and the same `Status` values
    as the row fields.
- A helper `slot(row, output)` returns the row itself for `normal`/`bria_json` and
  `row["outputs"][output]` otherwise. `_run`, `_progress`, `save_row`, `_write_row` and
  `cancel_job` use it, so the Normal/BRIA code path is unchanged.
- `row["fingerprints"]` gains `.wan.txt`, `.ltx.txt` and `.h3.txt`. Before a write:
  - a model output checks only its own file;
  - Normal/BRIA checks `.txt`/`.json` as today.
- **Import (`_scan`):**
  - reads every sidecar that exists;
  - an existing `.h3.txt` that fails validation (4.4) gets slot status `error` with the
    reason and is never overwritten, as invalid BRIA JSON is today;
  - a model file that is not UTF-8 gets the existing legacy-encoding message on that slot.
- **Grid, counters, filters and the inspector** show the slot of the selected output.
  Switching the output changes what is shown and never discards drafts, because each slot
  keeps its own draft.
- **Skip existing captions:**
  - for a model output, skips media whose own model file exists;
  - Normal/BRIA keep today's rule (either `.txt` or `.json`).
- **`regenerate` and overwrite** work per slot, as today.
- `job["output_format"]` records the output, and Continue after a pause uses it.
- **Clips with the Normal or BRIA output are not captioned** (decision D1):
  - they appear dimmed with the label "Video models only" and are left out of selection
    counts;
  - a batch skips them with that notice.

### 4.4 Generation, finishing and validation

**`make_prompt(s, media)`**, where `media` is `image` or `clip`, has a model-output branch.
The Normal/BRIA text stays byte-identical, and a test compares it with the 0.1.13 prompt.
The branch contains:
- the purpose: "Describe this photo for a video-model LoRA training dataset", or for
  clips: "These N images are frames of one continuous video clip in time order (0.0 s,
  0.8 s, …). Describe the clip …";
- the existing lines about visible facts, embedded instructions, no invention, filenames,
  readable text and additional instructions;
- "Write in English.";
- the model's shape from 3.2, 3.3 or 3.4;
- the character reference: "The main character is {class phrase}. Name them only once, as
  the exact token <character>, where they are first mentioned; afterwards use matching
  pronouns. Never write a name for them.";
- for stills: "This is a single still image: do not describe motion over time or camera
  movement." For H3 add: "End with: The camera holds a static shot.";
- the word target (existing wording);
- `policy_prompt(s)` with the clip-only details included only for clips.

**Revision:** `revision_instruction` for model outputs replaces "Preserve this exact trigger
at the beginning" with "Keep the token <character> exactly once." Revision and word
counting work on the model's text **before** it is finished, and history keeps the
finished text.

**Finishing** (`finish_video_caption(text, s, media)` in a new `captioning/video.py`):
1. Apply the existing `clean_caption` cleanup: think blocks, fences, quotes and
   whitespace. The trigger insertion is skipped.
2. For H3, strip an echoed `integrated_multimodal_description:` label or `[Shot 1]` from
   the start of the body.
3. Replace the first `<character>`:
   - with `{trigger}, {class phrase},` when a trigger is set, otherwise with the class
     phrase;
   - collapse `,,` and `, ,`, and a comma before `.`/`;`;
   - capitalize the phrase at the start of a sentence (`A woman sits`).
4. If `<character>` is missing:
   - WAN/LTX: prepend the opening like the existing trigger insertion, with the notice
     "The character name was added at the start.";
   - H3: set `needs_review` with the notice "Put the character name into [Shot 1]
     manually."
5. If `<character>` occurs more than once, replace only the first. Later occurrences
   become the class phrase, and the notice says so.
6. For H3, wrap the body into the exact three-field bytes (3.4). For stills, append the
   static-shot sentence if the body has no "static".
7. Warnings, shown as notices and never blocking:
   - the trigger occurs more than once;
   - the trigger is a substring of another word in the caption (case-sensitive, matching
     ai-toolkit);
   - the trigger contains a space.

**H3 validation** applies to a manual save and to import of an existing `.h3.txt`. The
file must match
`^integrated_multimodal_description: \[Shot 1\] .+\n\noverall_soundscape: .+\n\nnon_diegetic_music: .+$`
(dotall, after the trailing newline is stripped). The error is "H3 captions need the three
fields integrated_multimodal_description, overall_soundscape and non_diegetic_music, with
[Shot 1] first."

**Word counts:** H3 counts words of `<body>` only. The UI word counter uses the same rule.

### 4.5 Inspector

- **Caption editor:** edits the slot of the selected output. The file line shows
  `name.wan.txt` (and so on). Saving validates H3.
- **New line "Caption files":** lists which of `.txt`, `.json`, `.wan.txt`, `.ltx.txt` and
  `.h3.txt` exist for this media. This is read-only.
- **Clips:**
  - `<video controls>` from `/api/media/{id}`;
  - meta line: `1920 × 1080 px · 5.2 s · 30 fps · 156 frames · audio`;
  - the 3.5 notes for the selected model, for example "H3 expects 24 fps; this clip is
    30 fps.";
  - a strip of the frames that were sent to the model.

## 5. Video clips

- **Extensions:** `.mp4`, `.mov`, `.webm`, `.mkv`, `.m4v`, `.avi`. The existing image
  list stays. `provider.EXTENSIONS` splits into `IMAGE_EXTENSIONS` and
  `VIDEO_EXTENSIONS`, with `MEDIA_EXTENSIONS` as their union. The import, the collision
  rule, the folder browser (`folders.py`) and the empty-state text use it.
- **Decoder:** PyAV (`av`), which ships FFmpeg libraries in its Windows wheels. It is
  used only for decoding. It is added to `requirements.txt`/`requirements-lock.txt`,
  bundled by PyInstaller (a hook exists in pyinstaller-hooks-contrib) and its licenses
  are collected by `scripts/licenses.py`. `build.ps1` and `smoke_package.py` check that a
  packaged build decodes a test clip.
- **New module `captioning/media.py`:**
  - `probe(path) -> ClipInfo` returns `width`, `height`, `fps`, `frames`, `duration`,
    `has_audio` and `rotation`. `rotation` comes from the display matrix and is applied to
    thumbnails and frames.
  - `frame_jpeg(path, t, size)` returns one frame as JPEG.
  - `sample_frames(path, n, size) -> list[(t, jpeg)]` returns `n` frames evenly spaced
    between 5% and 95% of the duration.
  - Frames are re-encoded pixels only, like `image_bytes`: no metadata and no paths.
- **Import:**
  - a clip row has `kind: "clip"` and `clip: ClipInfo`; image rows get `kind: "image"`;
  - a file that PyAV cannot open, or that has no video stream, becomes `invalid` with
    "The video cannot be read.";
  - `MAX_IMAGES` counts clips too.
- **Thumbnails:** `/api/image/{id}` returns the middle frame for a clip. The folder browser
  preview does the same. Cards show a "clip" badge and the duration.
- **Playback:** a new `GET /api/media/{id}` streams the original file with range support
  (Starlette `FileResponse`). It is used only by the inspector's `<video>`. If WebView2
  cannot play the format, the frame strip is still shown.
- **Frames sent to the model:**
  - default 6 frames at 768 px on the long side;
  - the payload holds several `image_url` parts followed by the text, and the prompt
    lists their timestamps;
  - a new setting **Frames per clip** (4–12) sits under Analysis settings.
- **Context budget:**
  - The managed runtime starts with `-c 8192` and `--image-min-tokens 1024`
    (`runtime.py:325-329`). Six frames take at least 6,144 tokens, which leaves about
    2,000 tokens for the prompt and the answer.
  - Before release, measure `usage.prompt_tokens` for 6 frames with the real server. If
    it does not fit, lower the managed default to 5 frames, or raise `-c` to 16384 after
    measuring VRAM against the published guidance (decision D4).
  - For external and cloud servers the setting applies as chosen.
- **Timeout:** clip requests use the existing timeout setting, and the notice suggests
  raising it if clips time out.

## 6. Implementation by file

| File | Change |
|---|---|
| `captioning/models.py` | `output_format` adds `"wan"`, `"ltx"`, `"h3"`. New `character_class: str = Field("a person", max_length=40)`. New `clip_frames: int = Field(6, ge=4, le=12)`. `make_prompt(s, media="image")` gets the model branch; Normal/BRIA output stays identical. Helpers `is_video_output(s)` and `OUTPUT_SUFFIX = {"normal": ".txt", "bria_json": ".json", "wan": ".wan.txt", "ltx": ".ltx.txt", "h3": ".h3.txt"}`. |
| `captioning/training.py` | Add `motion` and `camera_motion` with a `media` flag. `policy_prompt(settings, media="image")` leaves clip-only details out for images. |
| `captioning/video.py` (new) | Per-model shape text, `finish_video_caption`, `h3_body`, `validate_h3`, trigger warnings. |
| `captioning/media.py` (new) | PyAV probe, frames and thumbnails (section 5). |
| `captioning/provider.py` | Split the extension sets. `generate` builds multi-frame payloads for clips. `read_response` finishes with `finish_video_caption` for model outputs. `revision_instruction` gets the model-output wording. `image_bytes` stays for images. |
| `captioning/storage.py` | `write_caption` accepts the suffixes in `OUTPUT_SUFFIX`, rejecting anything else as today. |
| `captioning/service.py` | Row `kind`/`clip`/`outputs`; `slot()`; generalized collision rule; `_scan` reads all sidecars and probes clips; per-slot job, save, skip and cancel; H3 validation on save; clips skipped for Normal/BRIA. |
| `captioning/api.py` | `/api/image/{id}` serves clip thumbnails. New `GET /api/media/{id}`. `/api/prompt` accepts the media kind for the preview (image by default, clip when the active row is a clip). |
| `captioning/folders.py` | List clips with middle-frame previews. |
| `ui/index.html` | New output options, Character type field and notes, Frames per clip, Caption files line, video element, frame strip, file types text. |
| `ui/recipe.js` | Show/hide and disable controls per output; clip-only details; notes. |
| `ui/dataset.js` | `slot()` view for grid, counters, filters, inspector, save and history; clip badge, player and meta; "Video models only" rows; H3 word counting. |
| `ui/main.js` | Counters and the run button read the selected output's slots. The button says "Create WAN captions" (and so on). |
| `ui/folder-browser.js` | Clip previews and badge. |
| `ui/style.css` | Clip badge, video element, frame strip, dimmed rows. |
| `ui/locales/*.json` | Every new message in English and Czech. The existing localization tests enforce this. |
| `requirements*.txt`, `scripts/build.ps1`, `scripts/licenses.py`, `scripts/smoke_package.py`, `THIRD_PARTY.md` | PyAV. |
| `README.md`, `docs/HANDOFF.md` | User documentation and release notes. |

## 7. Compatibility

- **Settings:** new fields have defaults, so an old `settings.json` loads unchanged. If an
  older version opens a new `settings.json` with `output_format: "wan"`, `Settings.recover`
  drops the rejected field and falls back to Normal.
- **Session:**
  - old rows get `kind: "image"`, `outputs` built from disk on the next import, and
    `.wan.txt`/`.ltx.txt`/`.h3.txt` fingerprints computed when missing, as the pre-0.1.5
    `.json` fingerprint is today;
  - `valid_row` stays unchanged;
  - older versions ignore the extra keys.
- **LORA Train:**
  - its image profiles keep reading `name.txt`, and its FIBO profile keeps reading
    `name.json`; the new files do not change either;
  - its bridge imports folders through `/api/import`, which now also accepts clips.
  - Separate issue: since 0.1.13 its bridge looks for `launch.json` in
    `%LOCALAPPDATA%\CaptionStudio`, but the file is now in `<program>\data`. The bridge
    has to be fixed in LORA Train.
- **ai-toolkit / musubi:** read the model files through `caption_ext` /
  `caption_extension` (section 2).

## 8. Tests and QA

**Python:**
- `make_prompt` for Normal/BRIA is byte-identical to 0.1.13 (golden strings);
- the model branches for image and clip contain the shape, the English rule and the
  `<character>` rule, and leave out clip details for images;
- `finish_video_caption`: placeholder replacement and punctuation, empty trigger,
  capitalization, missing and repeated placeholder, echoed H3 labels, H3 wrapping and
  exact bytes, the static sentence for stills, trigger warnings;
- `validate_h3` accept and reject cases; H3 word count uses the body only;
- sidecar collision rule (`a.jpg` + `a.wan.png`);
- `_scan` reads all five sidecars; invalid `.h3.txt` becomes an error and is never
  overwritten; legacy encoding per slot;
- per-slot job:
  - WAN run writes only `.wan.txt`, and `.txt`/`.json` bytes are unchanged;
  - skip-existing per output;
  - cancel and pause keep the slot drafts;
  - an external edit of `.wan.txt` blocks only the WAN write;
  - clips are skipped for Normal/BRIA;
- `bria.py` ignores `motion`/`camera_motion`;
- `media.py` against small generated clips (created with PyAV in the test): probe values,
  rotation, frame timestamps, unreadable file;
- API: `/api/media` range response; thumbnails for clips.

**UI suite (Playwright):**
- output switching shows the right slot and controls;
- Character type;
- a WAN batch against the stand-in model server, which returns `<character>` text;
- an H3 manual edit rejected, then accepted;
- a clip row with player, meta and frame strip;
- "Video models only" rows.
`scripts/prepare_ui_fixtures.py` also writes a short test clip.

**Live checks** (manual, not in `build.ps1`): `scripts/check_video_captions_live.py` runs
each model output on copied photos and one clip with the real local model. It reports word
counts, placeholder handling and `usage.prompt_tokens` for clips (D4).

**Package:** `smoke_package.py` imports a clip, creates its thumbnail and writes
`.wan.txt`, `.ltx.txt` and `.h3.txt` in a temporary profile.

## 9. Releases

1. **0.2.0, model captions for photos.**
   - Includes: sections 2–4 without clips, the tests and the documentation.
   - Done when the tests pass and a live run on copied photos gives valid files for all
     three models with the character opening in the right place.
2. **0.2.1, clips.**
   - Includes: section 5, the two clip details, the inspector clip view and the PyAV
     packaging.
   - Done when the tests pass, the packaged build decodes clips, and the D4 measurement is
     recorded.
3. **LORA Train handoff:** `docs/LORA_TRAIN_HANDOFF.md` (section 10), written after 0.2.1.

## 10. LORA Train handoff (written after implementation)

A separate document for LORA Train development, describing exactly what Caption Studio
leaves next to the media:
- all five file names and when each exists;
- encoding, trailing newline and the exact H3 bytes;
- the opening grammar and where the trigger sits per model;
- empty-trigger captions;
- that `name.txt`/`name.json` are model-independent and mutually exclusive, and that model
  files coexist with them;
- which file each training profile should read;
- what to do when a file is missing (skip versus fail, per profile);
- how to detect a caption that belongs to another model;
- how to rebuild a class-only caption for preservation (replace `{trigger}, ` at the
  opening);
- clip metadata that LORA Train must read itself (Caption Studio stores none next to the
  media);
- the bridge fix from section 7.

## 11. Decisions to confirm

- **D1** Clips get no Normal or BRIA caption, because BRIA is an image model.
  *Recommended.*
- **D2** H3 sound fields are always `N/A`, because the LoRAs are video-only and the
  captioning model cannot hear. *Recommended.*
- **D3** Should clips also get a WAN I2V caption (`name.wan-i2v.txt`)? It would be short:
  the opening plus motion and camera only, with no scene, which is the style of Wan's I2V
  rewriter (`system_prompt.py:91`). Only an I2V LoRA trained on clips uses it. *Optional,
  0.2.1.*
- **D4** Managed runtime context: keep `-c 8192` with 5–6 frames, or raise it to 16384
  after measuring VRAM.
- **D5** One output per batch (as today), or one batch that creates all selected model
  files?
- **D6** Normal `.txt` and BRIA `.json` stay mutually exclusive (converting archives the
  other), because LORA Train's image profiles read `.txt`. Should they coexist now that
  LORA Train picks its file?

## 12. Research basis

Local clones read on 2026-09-25:
- ai-toolkit `60d0c28`;
- musubi-tuner `4e7c714` and the AkaneTendo25 LTX fork;
- diffusion-pipe `27eab43`;
- SimpleTuner `afc31c3`;
- Wan2.2, LTX-2 and MiniMax-H3 official repositories;
- DiffSynth-Studio and OneTrainer.

Relevant facts beyond those cited above:
- ai-toolkit reads captions as UTF-8 without stripping a BOM or newlines; `clean_caption`
  is a no-op (`dataloader_mixins.py:100-111, 354`).
- musubi strips captions; a BOM is not removed.
- SimpleTuner splits a multi-line `.txt` into several captions unless
  `disable_multiline_split` is set. This matters for H3 files and belongs in the handoff.
- Wan 2.2 T2V and I2V A14B LoRA weights load into each other. A photo-trained T2V LoRA
  applied to I2V has mixed community reports and no measurements (musubi #416,
  diffusion-pipe #481).
- IPRO (arXiv 2510.14255) measured identity drift in Wan 2.2 I2V without a LoRA.
