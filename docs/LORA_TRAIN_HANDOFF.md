# LORA Train handoff: training from Caption Studio captions

For LORA Train development. Written 2026-09-25 against Caption Studio 0.2.1 and LORA Train
`513881b` (2026-09-11); updated 2026-09-26 for Caption Studio 0.2.2, where the LoRA type
(character, object, style, general) decides how every caption names what the LoRA learns
(section 3). Caption Studio only describes photos and clips that the user prepared;
it writes caption files next to them and never trains, converts or trims media. LORA Train
picks the files for the model it trains. Nothing in LORA Train was changed for this document:
everything addressed to LORA Train is a proposal for its own development.

Labels used below:
- **[V]** verified in code at the commits listed in section 11;
- **[D]** from official documentation or model cards;
- **[C]** community reports without measurements;
- **[R]** our recommendation.

## 1. Summary of the work for LORA Train

1. **Fix the Caption Studio bridge.** It looks for `launch.json` in the old data folder and has
   not found a running Caption Studio since 0.1.13 (section 9.1).
2. **Choose the caption file by training profile.** Never fall back from a model file to
   `name.txt` (section 4).
3. **Do not prepend the trigger to model files; check it instead.** For H3 a prepend breaks the
   file's structure (section 5).
4. **Build class-only captions for preservation from the opening** of the LoRA type
   (section 6).
5. **Video profiles read clips themselves**: rotation, true frame count, frame rate and the
   trained window compared with the described clip (section 7).
6. **H3 files are used verbatim.** The official I2VA line is added only when training with a
   first frame (section 7.5).
7. **Qwen-Image 2.1:** the chat template is the trainer's job, and diffusers 0.40 has no
   pipeline for it (section 8.4).
8. **Stop Caption Studio's managed model before training** on the same GPU (section 9.3).

## 2. Files next to each media file

| File | Caption output | Photos | Clips | Content |
|---|---|---|---|---|
| `name.txt` | Normal | yes | no | Model-independent caption (3.1). |
| `name.json` | BRIA JSON (FIBO) | yes | no | FIBO ImageAnalysis (3.1). |
| `name.wan.txt` | WAN 2.2 | yes | yes | WAN text-to-video caption. |
| `name.wan-i2v.txt` | WAN 2.2 I2V | no | yes | Motion and camera only, at most 100 words. |
| `name.ltx.txt` | LTX-2.5 | yes | yes | LTX caption. |
| `name.h3.txt` | MiniMax H3 | yes | yes | Three-field H3 caption (3.4). |

Rules [V]:
- **Name.** The caption path is `Path(media).with_suffix(suffix)`, so only the last extension is
  replaced: `photo.v2.jpg` gets `photo.v2.wan.txt`. Suffixes are always lowercase.
- **Media types.** Photos: `.jpg .jpeg .png .webp .bmp .tif .tiff`, the same set as LORA Train's
  `IMAGE_SUFFIXES`. Clips: `.mp4 .mov .webm .mkv .m4v .avi`.
- **All files coexist.** Writing one never changes another. This holds since 0.2.0; earlier
  versions let `.txt` and `.json` replace each other and moved the older one to
  `.caption-backups`.
- **Only approved captions are on disk.** A file appears when the user saves it, by auto-save
  in a batch or by Save in the inspector. Drafts and captions waiting for review exist only in
  Caption Studio's `session.json`, so a newer unsaved draft can exist next to an older file
  (section 9.2).
- **Encoding.** UTF-8 without BOM, the text followed by exactly one `\n`, LF line endings on
  Windows too. Files are written atomically. LORA Train's `utf-8-sig` read and `.strip()` suit
  them.
- **Backups.** Replaced versions go to `.caption-backups/` in the same folder. Training must
  skip dot folders; LORA Train's top-level scan already does.
- **Hand edits.** Caption Studio never overwrites a file that changed outside the app, but
  anyone can edit the files in another editor. LORA Train must validate what it reads
  (sections 5 and 7.5) instead of assuming the generated form.
- **Unique names.** Caption Studio rejects two media files in one folder that would share any
  caption file name, for example `a.jpg` with `a.png`, or `a.jpg` with `a.wan.png`, with "Two
  files would share the caption file {name}. Rename one of them." Captioned media therefore
  have unique stems per folder. musubi-tuner names its caches by stem as well.
- **Subfolders.** Caption Studio can import a folder recursively. LORA Train's
  `discover_dataset` (`backend/trainer/cache.py:81`) and `scan_dataset`
  (`backend/trainer/dataset.py:9`) read only the top folder.
- **Nothing else is stored next to the media**: no trigger, class, clip metadata or frame list.

## 3. Caption content

Since 0.2.2 the recipe's LoRA type ("What are you training?", `settings.preset`) decides how
every caption output names what the LoRA learns: `name.txt`, the `short_description` of
`name.json` and all video files [V]:

| LoRA type | The caption names it | Later mentions | Details left out by default |
|---|---|---|---|
| `character` | once, `{trigger}, {class},`: `Velmira, a woman, sits …` | `the woman`, she | identity, hair color |
| `object` | once, `{trigger}, {class},`: `Zorbo, a backpack, hangs …` | `the backpack`, it | object appearance (shape, material, colors, markings); logo and text on it |
| `style` | at the start, `{trigger} style, `: `Zorvak style, a woman sits …` | — | medium and technique; color palette and grading |
| `general` | at the start, `{trigger}, `: `ohwx, a woman sits …` | — | none |

- The class is the recipe's type field (`settings.subject_class`, up to 40 characters). Empty
  means `a person` for a character and `an object` for an object.
- A style trigger that already ends in "style" is used as it is (`ink wash style, …`).
- After a style or general trigger the first letter is lowercased, except "I" and words with
  more capitals (`LED`).
- Style captions describe only the content: people generically, never the medium, technique,
  texture, grain or palette.

### 3.1 `name.txt` and `name.json` (model-independent)

- `name.txt` is the Normal output. It can be prose or tags and is in the caption language chosen
  in the recipe. With a trigger it opens as in the table above; in tags the opening is the
  first tag (`Velmira, a woman, sitting, café, …`). LORA Train reads this file today.
- `name.json` is BRIA FIBO ImageAnalysis. Its `short_description` opens the same way, and for a
  character or an object the main subject's `description` in `objects` is the class. LORA
  Train's FIBO profile reads it through `fibo_caption.normalize_caption`.

### 3.2 Video model files: shared rules

- **English prose**, one paragraph (for H3, inside the field structure). No tags and no sound.
- **The recipe decides the details.** The "Character / person" preset omits identity and hair
  color. Face, body, skin, eyes and the color of hair and facial hair are therefore never
  described, and the LoRA learns them. Hairstyle, clothing, accessories, expression, pose,
  setting, lighting and camera are described unless the user omitted them. Clip captions add
  motion over time and camera movement.
- **Opening.** A character or object is named once as `{trigger}, {class},`, for example
  `Velmira, a woman,`. Later mentions are `the woman` or a pronoun. The trigger is up to 100
  characters; the UI suggests one invented, readable word. Style and general captions start
  with their trigger (3.3).
- **Without a trigger** a character or object opening is only the class phrase, capitalized at
  the start of a sentence: `A woman sits …`, `… frames a woman seated …`.
- **Punctuation.** When the opening falls right before `.` or `;`, its trailing comma is
  dropped: `A photo of Velmira, a woman.`
- **Warnings** that Caption Studio shows but does not enforce: the trigger occurs more than
  once, the trigger is part of another word (case-sensitive, as ai-toolkit matches), the trigger
  contains a space.
- **Length.** The target is 20–300 words, default 100; WAN I2V is capped at 100. Even 300 English
  words stay under the 512-token limits of umT5 and Qwen3-VL [R, approximate].

### 3.3 Where the opening sits

| File | Position | Start of a caption |
|---|---|---|
| `.wan.txt` | first words | `Velmira, a woman, sits at a café table by the window …` |
| `.wan-i2v.txt` | first words; then only motion and camera | `Velmira, a woman, looks out of the window, then turns …` |
| `.ltx.txt` | first sentence, after the shot | `A medium close-up at eye level frames Velmira, a woman, as she …` |
| `.h3.txt` | in `[Shot 1]`, after style and composition | `integrated_multimodal_description: [Shot 1] Live-action, photographic, a medium close-up at eye level frames Velmira, a woman, seated …` |

An object sits in the same places as a character. Style and general triggers start every file;
in H3 they start the `[Shot 1]` body. A style caption's H3 body opens with the composition, not
with style words: `[Shot 1] Zorvak style, a medium close-up at eye level frames a woman …`.

Photos are described as stills with no motion; H3 photo captions end with "The camera holds a
static shot." Clips describe the motion in time order and the camera movement, including a
static camera.

### 3.4 H3 exact bytes

```text
integrated_multimodal_description: [Shot 1] <body>

overall_soundscape: N/A

non_diegetic_music: N/A
```

- The fields are separated by `\n\n`, and both sound fields are always `N/A`.
- The labels are literal prompt text in H3: every trainer feeds the caption verbatim, so they
  must stay [V].
- Caption Studio validates this form on save and on import with the regular expression below.
  LORA Train should apply the same check:

```python
H3 = re.compile(
    r"integrated_multimodal_description: \[Shot 1\] (?P<body>.+?)\n\n"
    r"overall_soundscape: .+\n\nnon_diegetic_music: .+",
    re.S,
)
valid = H3.fullmatch(text.strip()) is not None
```

## 4. Which file each training profile reads

| LORA Train profile | File | Media used | Missing or empty file |
|---|---|---|---|
| Existing image profiles (FLUX.2, Klein, Z-Image, Krea 2, Qwen Image 2512, SDXL) | `name.txt` | photos | fail (current behavior) |
| Bria FIBO | `name.json` | photos | fail (current behavior) |
| Qwen-Image 2.1 (planned) | `name.txt` | photos | fail |
| Wan 2.2 T2V (A14B or TI2V-5B) | `name.wan.txt` | photos and clips | fail |
| Wan 2.2 I2V (A14B) | `name.wan-i2v.txt` | clips only; photos ignored | fail |
| LTX-2.5 | `name.ltx.txt` | photos and clips | fail |
| MiniMax H3 | `name.h3.txt` | photos and clips | fail; also fail when 3.4 does not match |

Policy [R]:
- **Fail before caching** and list every missing file. LORA Train already stops with "Image has
  no saved caption". Silently skipping an item changes the dataset without notice.
- **Never fall back from a model file to `name.txt`.** The Normal caption can be in another
  language or in tags, and it has a different opening.
- **Wan I2V uses clips only.** A still teaches the I2V model nothing (8.1), so photos in the
  folder are not training items for this profile.
- **Image profiles ignore clips.** Clip extensions are not in `IMAGE_SUFFIXES`, so this already
  holds.

## 5. Trigger handling

Today `discover_dataset` prepends `f"{trigger_word}, {caption}"` whenever the trigger is not a
substring of the caption (`backend/trainer/cache.py:96-97`) [V].

- **`name.txt`:** keep this behavior.
- **Model files, same trigger in both apps:** nothing is prepended, because the opening already
  contains the trigger.
- **Model files, different trigger:** the prepend produces two names ("Karvel, Velmira, a woman,
  sits …"). For H3 it also puts text before `integrated_multimodal_description:` and breaks the
  format.

Recommended check for model files [R]:
1. Do not prepend anything.
2. The trigger must occur exactly once, case-sensitive and not inside another word:
   `len(re.findall(rf"(?<!\w){re.escape(trigger)}(?!\w)", text)) == 1`. For H3 it must be in the
   body.
3. If the opening of the LoRA type is missing (`{trigger}, {class}` for a character or object,
   `{trigger} style, ` or `{trigger}, ` at the start otherwise), warn: the file was edited by
   hand or written with another type or class, and preservation cannot build its class caption
   (section 6).
4. If the files contain no trigger (Caption Studio ran without one) but LORA Train has one, fail
   with "These captions have no trigger. Set it in Caption Studio and create them again." Do not
   insert it: the class phrase can occur several times, so the right place is ambiguous.
5. If LORA Train has no trigger while the files contain one, training still learns that name.
   Show a notice.

Source of the trigger, type and class: the user enters them in LORA Train. The bridge can prefill
them from Caption Studio's `/api/state` (`settings.trigger`, `settings.preset`,
`settings.subject_class`). These are
the current recipe values, not necessarily the ones the files were written with, so the check
above stays the authority.

If LORA Train ever hands these files to another trainer [V]:
- **ai-toolkit** reads `caption_ext: "wan.txt"`; it adds the missing dot itself. It prepends
  `"{trigger} "` (with a space) only when the case-sensitive substring count is 0, and it
  replaces `[trigger]` placeholders. With a matching trigger it changes nothing.
- **musubi-tuner** reads `caption_extension = ".wan.txt"` and adds nothing. It does not strip a
  BOM.
- **diffusion-pipe and SimpleTuner** only read `<stem>.txt`. diffusion-pipe's `caption_prefix`
  is prepended without a separator.
- **ltx-trainer** `--lora-trigger` always prepends and would double the name, so it must not be
  used with these files.

## 6. Class-only captions for preservation

Differential output preservation (DOP) and prior preservation compare the LoRA with the base
model on captions where the trigger is replaced by the class. The fixed openings make this
exact. The function below returns the caption Caption Studio writes without a trigger; it is
the same rule as `captioning/anchor.py` `class_caption`. `tests/test_lora_types.py` checks it
for all four LoRA types and all text outputs (Normal, WAN, WAN I2V, LTX, H3), with the opening
at the start, mid-sentence, after `[Shot 1]` and before a full stop [V].

```python
import re

DEFAULT_CLASS = {"character": "a person", "object": "an object"}


def class_caption(caption: str, preset: str, trigger: str, subject_class: str = "") -> str:
    """The caption as Caption Studio writes it without a trigger."""
    trigger = trigger.strip().strip(",").strip()
    if not trigger:
        return caption
    if preset in DEFAULT_CLASS:
        cls = subject_class or DEFAULT_CLASS[preset]
        replacements = [(f"{trigger}, {cls},", cls), (f"{trigger}, {cls}", cls)]
    else:
        phrase = trigger
        if preset == "style" and not re.search(r"\bstyle$", trigger, re.I):
            phrase += " style"
        replacements = [(phrase + ", ", "")]
    for old, new in replacements:
        start = caption.find(old)
        if start >= 0:
            rest = new + caption[start + len(old) :]
            # Capitalize where the remaining text starts a sentence or the [Shot 1] body.
            if re.search(r"(?:^|[.!?]\s+|\[Shot 1\]\s+)$", caption[:start]):
                rest = rest[:1].upper() + rest[1:]
            return caption[:start] + rest
    raise ValueError("The caption does not contain the opening of its LoRA type.")
```

| Type | Caption | Class-only caption |
|---|---|---|
| character | `Velmira, a woman, sits at a café table …` | `A woman sits at a café table …` |
| character | `… frames Velmira, a woman, as she turns her head.` | `… frames a woman as she turns her head.` |
| character | `… [Shot 1] Velmira, a woman, stands in a doorway. …` | `… [Shot 1] A woman stands in a doorway. …` |
| object | `A photo of Zorbo, a backpack.` | `A photo of a backpack.` |
| style | `Zorvak style, a woman sits at a café table …` | `A woman sits at a café table …` |
| general | `ohwx, a woman sits at a café table …` | `A woman sits at a café table …` |

For comparison, other trainers do a plain substring replacement [V]:
- ai-toolkit replaces the trigger with its class word: `Velmira, a woman,` becomes a harmless
  `woman, a woman,`, but `sks woman` would become `woman woman`.
- The musubi LTX fork's `--dop_args mode=caption_replace trigger=… class=…` matches whole words
  and suits `trigger class` captions ("sks woman" becomes "woman"), not the apposition.

## 7. Clips

### 7.1 What LORA Train must read itself

Caption Studio shows clip facts in its inspector but stores none next to the media. LORA Train
needs its own probe. What Caption Studio learned doing this with PyAV 18.1 [V]:
- **Rotation.** Phone clips carry a display matrix. PyAV reports it as `frame.rotation`, and
  `image.rotate(frame.rotation, expand=True)` in PIL, which rotates counter-clockwise, matches
  ffmpeg's autorotation. The test fixture `tests/fixtures/rotated-90.mp4` covers this. A decoder
  that returns raw frames shows such clips sideways, so check the decoder LORA Train uses.
- **Frame count.** A clip cut without re-encoding (stream copy) keeps the source header's frame
  count: one test clip had 148 real frames and a header of 361. Take the count from length × frame
  rate when the two disagree, or count while decoding.
- **Size** is the displayed size, after rotation.
- **Frame rate.** Phone clips can have a variable rate, so resample by timestamps.

### 7.2 What a clip caption covers

- The vision model saw frames from the **whole clip**: one every 0.5 s by default (0.25 s or 1 s
  per setting), taken at the middles of equal parts, at most 30 spread over the whole length. The
  caption describes the action from the first to the last second.
- **A training window shorter than the clip does not match its caption.** Typical windows are
  81 frames at 16 fps for Wan A14B (5.1 s), 121 frames at 24 fps for LTX (5.0 s) and at most 345
  frames at 24 fps for H3 (14.4 s). Recommendations [R]:
  - warn when a clip is longer than the profile's window;
  - ask for clips prepared at training length (preparing media is the user's job; neither app
    trims);
  - do not squeeze the whole clip into the window. ai-toolkit's `shrink_video_to_frames` does
    that, which changes the apparent speed; LTX in particular needs training fps to match
    inference fps.
- **I2V windows start at the first frame.** The first frame of the trained window is the
  condition, and `.wan-i2v.txt` describes the motion from the start of the clip. The window
  therefore starts at frame 0 ("head" extraction).

### 7.3 Frame rules per model

| | Wan 2.2 A14B | Wan 2.2 TI2V-5B | LTX-2.5 | MiniMax H3 |
|---|---|---|---|---|
| Frame rate | 16 fps | 24 fps | 24 fps (musubi and SimpleTuner default 25) | 24 fps |
| Frame counts | 4n+1 | 4n+1 | 8n+1 | 17n+5 |
| Usual length | 81 | 121 | up to 121 | 124–345 (5–15 s) in musubi |
| Size multiple | 16 px | 32 px | 32 px | 32 px |
| Stills | 1 frame, T2V model | 1 frame | 1 frame | 1 frame (`--one_frame` in musubi) |

Sources: Wan2.2 configs, ai-toolkit buckets, musubi `datasources.py`, diffusion-pipe models,
ltx-trainer documentation [V/D]. Trainers that get another count round down (Wan and
diffusion-pipe), pad by repeating the last frame (musubi LTX caching) or trim with a warning
(ai-toolkit H3). LORA Train should choose valid counts itself.

### 7.4 Audio

Train video only for all three models [R]. The captions describe no sound, and H3's sound fields
are `N/A`. Defaults that would train audio [V]:
- ai-toolkit's UI sets `do_audio: true` for LTX and H3;
- diffusion-pipe trains H3 audio whenever a clip has an audio track;
- ltx-trainer extracts audio unless `--skip-audio` is given.

The official LTX character guide says `with_audio: false` for visual-only LoRAs [D]. Caption
Studio reports `has_audio` per clip in `/api/state` rows.

### 7.5 H3 files in training

- **T2VA:** use the file content verbatim.
- **With a first frame** (I2VA on the FL2VA checkpoint): prepend the official instruction line
  and one blank line (`base-en.txt:16-34` in the MiniMax-H3 prompt skill) [V]:

  ```text
  For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

  integrated_multimodal_description: [Shot 1] …
  ```

  The musubi documentation treats I2VA and L2VA as FL2VA variants. The released FL2VA base
  supports both, so a LoRA trained on FL2VA also serves first-frame generation [D].
- **Never split lines.** SimpleTuner turns a multi-line `.txt` into several captions unless
  `disable_multiline_split` is set, and OneTrainer picks one line at random. diffusion-pipe and
  musubi keep the whole file. LORA Train reads the whole file today; keep it that way.
- **Validate** with the regular expression in 3.4 and fail on a mismatch.

## 8. Training notes per model

Collected while designing the captions (research on 2026-09-25, local clones in section 11).
These are inputs for LORA Train's own design, not decisions.

### 8.1 Wan 2.2

Model:
- T2V-A14B and I2V-A14B each have two experts. The high-noise expert sets the layout and the
  low-noise expert refines details. They switch at timestep 0.875 for T2V and 0.9 for I2V [D].
- TI2V-5B is one model for both text and first-frame generation: 24 fps, 121 frames, sizes in
  multiples of 32 [D].
- Text encoder: umT5-XXL, padded and truncated at 512 tokens. musubi collapses whitespace [V].

Photos and I2V:
- **Photos train the T2V model.** I2V training on a still conditions it on itself and teaches
  nothing: ai-toolkit's `wan22_14b_i2v` conditions on the first frame, which for a still is the
  image, and diffusion-pipe asserts more than one frame [V]; fal's hosted I2V trainer rejects
  image-only datasets [D].
- **A T2V LoRA loads into I2V-A14B** because the keys match; no LoRA sits on `patch_embedding`,
  the layer whose input channels differ [V]. Whether it holds identity is disputed [C]:
  - musubi discussion #416 has mixed reports;
  - diffusion-pipe #481 says the face "never really matches".
  - Test with low-noise strength 0.8–1.0 and high-noise 0–0.5; high-noise LoRAs can override
    the start frame [C].
- **An I2V LoRA needs clips.** Starting it from the T2V LoRA's weights is possible because the
  keys match [R, untested].
- **Identity drift in I2V without a LoRA** is measured: IPRO (arXiv 2510.14255) reports face
  similarity 0.578 for A14B and 0.379 for TI2V-5B over 600 small-face cases [D]. With a
  character LoRA in I2V, no measurements exist.

Experts in training [V]:
- **ai-toolkit** trains both experts in one run, alternating every `switch_boundary_every` steps
  (10–20 recommended with `low_vram`). `split_multistage_loras` saves `*_high_noise` and
  `*_low_noise` files.
- **musubi** trains both at once (`--dit` low, `--dit_high_noise`, `--timestep_boundary`), which
  gives one LoRA, or one expert at a time with `--min/max_timestep` and
  `--preserve_distribution_shape`.
- **diffusion-pipe and DiffSynth** use separate runs.
- Likeness sits mostly in the low-noise expert, but the high-noise expert shapes face and body
  structure. One tester got better body and face shape from separate runs with low noise at
  shift 1.0 and high noise at shift 5.0 (musubi #455) [C].

Settings and data:
- **ai-toolkit's 24 GB example** (`train_lora_wan22_14b_24gb.yaml`) [V]:
  - transformer `uint4` with the accuracy-recovery adapter `wan22_14b_t2i_torchao_uint4`;
  - text encoder `qfloat8`, `low_vram`;
  - rank 32, LR 1e-4, 2000 steps, `cache_text_embeddings`, `switch_boundary_every: 10`.
- **musubi:** TI2V-5B cannot be trained (Wan 2.2 support is 14B only) [V].
- **Data** [C]: 15–40 varied images for likeness. The official livestream suggested 30–50 images
  plus 10–20 clips at 16 fps and 81 frames, warning that "too much training on static pic will
  make your video static".
- **Caption style:** Wan's own prompt rewriter [V]:
  - T2V: 60–200 words, subject → action → background → camera, no atmosphere prose;
  - I2V: at most 100 words of motion and camera, dropping what the image shows.

  Caption Studio's WAN files follow this.

### 8.2 LTX-2.5

Model [D/V]:
- 22B "dev" transformer, which is the one to train, plus a distilled one.
- Custom Gemma 4 12B text encoder. Do not substitute Google's stock Gemma 4.
- Text is truncated at 1024 tokens (`TOKENIZER_MAX_LENGTH`; `LTX2_GEMMA_MAX_LENGTH` in musubi).
- Cached text embeddings from 2.3 are not valid for 2.5.
- Most 2.3 LoRAs still run on 2.5.

Weights and VAE [V]:
- ai-toolkit loads Comfy split files: the int8 ConvRot transformer, Gemma with its own
  tokenizer, and the convolutional VAE (diffusers has no class for the default diffusion-decoder
  VAE).
- The musubi fork (`--ltx_version 2.5`) and SimpleTuner use the DiffVAE instead.
- Whether the two VAEs share a latent space is unverified.

Video only:
- ai-toolkit: `do_audio: false` [V];
- musubi: `--ltx_mode` (alias `--ltx2_mode`) defaults to video and then builds the transformer
  without audio modules [V];
- official guidance: `with_audio: false` [D].

Timesteps differ by trainer [V]:
- ai-toolkit: `weighted`, uniform sampling with a bell-shaped loss weight and no
  resolution-dependent shift;
- musubi: `shifted_logit_normal` (must be passed explicitly), shift growing linearly from 0.95 at
  1024 tokens to 2.05 at 4096;
- SimpleTuner: static shift 3.0;
- diffusion-pipe: shift 1.

There is no consensus, so this is an A/B point for LORA Train.

Conditioning and frames [V]:
- **First-frame conditioning.** musubi and ltx-trainer use probability 0.1, and the resulting
  LoRA works from text and from a first frame. ai-toolkit's `do_i2v` is on/off per clip: frame 0
  stays clean and is masked out of the loss.
- **Frame rate** enters RoPE position coordinates (ai-toolkit), so train at the fps used for
  generation. The official guide warns of ghosting otherwise [D].
- **Frames and sizes:** frames 8n+1 up to 121; sizes in multiples of 32; stills are F=1.
  ltx-trainer needs `batch_size: 1` to mix stills and clips.

LoRA targets [V]:
- ai-toolkit: every Linear in `transformer_blocks`;
- musubi: the `t2v` preset targets attention only (`to_q/k/v/out.0`);
- the official character guide says to train the feed-forward layers too, which keeps identity
  from drifting [D].

Official character guidance [D]:
- a standard LoRA, not an IC-LoRA;
- 25–50 clips of about 5 s, each one continuous action without hard cuts, with varied settings
  (otherwise the LoRA learns the room);
- a readable made-up trigger;
- about 8k tokens per clip and under 15k; `1280×704×81` is a good default;
- test strengths 0.5–1.0, because at 1.0 a character LoRA can suppress motion.

Defaults [V]:
- rank 32, LR 1e-4;
- 2000 steps in musubi's recommended command, 3000 in ai-toolkit's UI;
- musubi: `--fp8_base --fp8_scaled` and `blocks_to_swap 10`.

### 8.3 MiniMax H3

Model:
- 33B single-stream model [D].
- Two open checkpoints: FL2VA (text, first and last frame) and Ref2VA (reference images).
  ai-toolkit also offers pruned int8 ConvRot variants (`fl2va_pruned`, `ref2va_pruned`) [V].
- 24 fps, 4–15 s [D].
- Text encoder Qwen3-VL-32B [V]:
  - ai-toolkit `max_text_length` 512 (0 means no limit);
  - musubi and diffusion-pipe do not truncate.

**The released checkpoints are CFG-distilled.** Training on the plain flow-matching target pulls
the model out of that space: outputs wash out and follow prompts less. One-frame (photo) training
shows structural damage within about 50 steps [V, musubi `docs/minimax_h3_advanced.md`]. Every
run needs one of these countermeasures:
- **a de-distillation adapter:** ai-toolkit `assistant_lora_path` (its adapters were replaced on
  2026-09-24), musubi `--base_weights`;
- **the guidance loss:** musubi `--h3_guidance_loss_scale` 3–4 and
  `--h3_guidance_loss_sigma_min 0.15`; ai-toolkit has the same mechanism;
- **teacher matching** (musubi);
- **CFG-augmented training** (diffusion-pipe, `cfg = 4`).

**musubi's validated photo identity recipe** (`subject_ref` teacher; 20 images, one frame,
rank 16) [V]:
- LR 3e-4 with 50 warmup steps, about 500 steps;
- `--h3_teacher_condition_sigma_max` stays 1.0; with 0.75 the student never learns the identity;
- `--h3_teacher_condition_sigma_min 0.15`, `--h3_teacher_loss_mag_weight` 0.25–0.5,
  `--h3_teacher_loss_dc_weight` 0.3;
- the teaching loss can plateau near 300 steps, so save and validate intermediate checkpoints.

Data and captions for this recipe:
- **References** per item: 1–9 *other* photos of the character, never the target itself.
- **Student caption:** the trigger plus the scene, with appearance left out. This is exactly
  what `.h3.txt` with identity and hair color omitted contains.
- **Teacher caption.** musubi wraps the student caption automatically. That wrap declares one
  `<Subject i>` per `<Picture i>`, but several photos of one person should be one Subject over
  several Pictures. LORA Train should therefore write `teacher_caption` itself:
  - use the Ref2VA sections `subject_definitions`, `summary`, `retention_analysis`,
    `detailed_description`, `overall_soundscape` and `non_diegetic_music`;
  - keep scene, pose and outfit identical to the student caption.
- **Trigger.** The student's trigger may be `<Subject 1>` itself. With Caption Studio's readable
  trigger, LORA Train can swap the trigger for that token at training time. ai-toolkit's D-OPSD
  mode does the same with `<Picture 1>`/`<Video 1>`; it runs on the Ref2VA architecture only
  (`model_kwargs.dopsd`) [V].

Other notes:
- **Mix in clips.** diffusion-pipe's notes say images alone gradually degrade motion [V].
- **Community reports** [C]:
  - 31 face close-ups captioned "(trigger), 1girl" (rank 16, LR 1e-4, 1000 steps) reproduced a
    face;
  - the Ref2VA base with three reference images already kept a character consistent, and a LoRA
    added little.
- **musubi constraints:** photos need `--one_frame` caches, `--video_only` and batch size 1.
  Mixed photo and clip runs are "expected to work but untested" [V].

### 8.4 Qwen-Image 2.1

Model (released 2026-09-20) [D/V]:
- 7B, 32-layer single-stream block-causal DiT.
- Qwen3-VL-8B text encoder, read at the last decoder layer before its final RMSNorm.
- 64-channel RGBA VAE with 16× spatial compression.
- One checkpoint does text-to-image and editing. Native 2K resolution.

**Captions are plain `name.txt` text.** The trainer adds the chat template (DiffSynth
`diffsynth/pipelines/qwen_image_21.py:133-181`, ai-toolkit
`qwen_image_2/src/pipeline.py:29-34, 104-112`) [V]:

```text
<|im_start|>system
Comprehend and analyze the provided prompt.<|im_end|>
<|im_start|>user
{caption}<|im_end|>
<|im_start|>assistant
```

- The system turn's tokens are dropped from the embeddings. `drop_idx` is the token length of
  the system message rendered by `processor.apply_chat_template`.
- An empty caption becomes a single space, because Qwen has no BOS token.
- Neither trainer truncates the text.

**LORA Train cannot reuse its Qwen Image 2512 path.** That profile calls diffusers'
`_get_qwen_prompt_embeds` (`backend/trainer/next_flow.py:299`), which applies the 2512 template
("Describe the image by detailing the color, shape, size, …", start index 34, 1024 tokens).
diffusers 0.40 in LORA Train's venv has no Qwen-Image 2.1 pipeline [V].

**Alpha channel.** The VAE reads four channels, and ai-toolkit gives photos without alpha an
opaque one when encoding. LORA Train's `image_tensor` converts to RGB
(`backend/trainer/cache.py:117`), so a 2.1 profile must add alpha = 1.0, which is +1 in the VAE's
[-1, 1] range [V].

Captions for other kinds of 2.1 LoRAs:
- **Transparent assets** use the official form "This is an RGBA image with transparency.
  <description>. The image has alpha channel and the background is transparent." [D]. Caption
  Studio fills transparency with white before the vision model sees it, so it would describe a
  white background. This is not needed for characters.
- **Edit LoRAs** need control images and instruction captions ("Generate a group photo of these
  two characters."). This is a different dataset type.

Trainer defaults [V]:
- **DiffSynth example:** `metadata.csv`, `max_pixels` 1048576, LR 1e-4, rank 32, 5 epochs with
  `dataset_repeat` 50.
- **ai-toolkit:** arch `qwen_image_2`, Comfy-Org weights pre-quantized as `convrot8`
  (transformer and text encoder), `timestep_type: shift`, sample guidance 3.0.

For a character, the recipe is the same as for the other image models: Normal output, English,
trigger, identity and hair color omitted.

## 9. Caption Studio integration

### 9.1 Bridge fix (required)

`backend/caption_studio_bridge.py:27-30` resolves the data folder as `CAPTION_STUDIO_DATA_DIR`
or `%LOCALAPPDATA%\CaptionStudio`. Since 0.1.13 Caption Studio keeps its data in a `data` folder
next to the program (`captioning/paths.py`), and `launch.json` (`{"url", "pid"}`) is written
there on each start and removed on exit [V]:

| Caption Studio run | `launch.json` |
|---|---|
| installed | `%LOCALAPPDATA%\Programs\Caption Studio\data\launch.json` |
| source checkout (`run.bat`, `app.py`) | `<repo>\data\launch.json` |
| `CAPTION_STUDIO_DATA_DIR` set | `<that folder>\launch.json` |

Proposed resolution [R]:
- If `CAPTION_STUDIO_DATA_DIR` is set, use only that folder.
- Otherwise try `installed_exe.parent / "data"`, then `source_dir / "data"`.
- Take the first `launch.json` whose process the bridge's existing `_verify_process` accepts.
- The legacy folder is only a data source that a 0.1.13+ build moves once. A stale file there
  would be rejected by the pid check anyway.

### 9.2 API the bridge can rely on

Unchanged since 0.1.x:
- `GET /api/state` keys `version`, `job`, `importing`, `runtime`;
- `POST /api/import` (now also accepts clips);
- `POST /api/runtime/stop`.

Added in 0.2.x and useful to LORA Train [V]:
- `settings.omitted_by_type`, the details left out for each LoRA type since 0.2.3 (every type has
  its own set, `training_details` and `training_defaults` in the state);
- `settings.trigger`, `settings.preset` (the LoRA type), `settings.subject_class` (empty means
  the type's default class) and `settings.output_format`, the recipe's current values;
- `caption_outputs`, a map from output ID to `{suffix, name}`: `normal`, `bria_json`, `wan`,
  `wan_i2v`, `ltx`, `h3`;
- `media_outputs`: `{"image": ["normal", "bria_json", "wan", "ltx", "h3"], "clip": ["wan",
  "wan_i2v", "ltx", "h3"]}`;
- `rows[]` with `path`, `kind` (`image`/`clip`), `clip` (`width`, `height`, `fps`, `frames`,
  `duration`, `has_audio`, `rotation`) and `outputs[output].status`.

Status values: `pending`, `queued`, `processing`, `saved`, `existing`, `skipped`, `draft`,
`review`, `error`, `invalid`. `saved`, `existing` and `skipped` (an existing file a batch left
alone) mean the file on disk is the current caption.
Before training, the bridge can warn about rows of the dataset folder whose chosen output is
`draft`, `review`, `queued` or `processing`, and about a running `job`.

### 9.3 GPU memory

Caption Studio's managed model must not share the GPU with training. It was measured with a
30-frame clip (32,409 prompt tokens, 64k context) [V]:

| Profile | After loading | Peak | Time for one caption |
|---|---|---|---|
| Q4 | 18.65 GiB | 18.83 GiB | 17.6 s |
| IQ3 (image projector on the CPU) | 13.58 GiB | 13.61 GiB | 178.4 s |

- Call `POST /api/runtime/stop` before training, as the bridge already can.
- External caption servers (for example Marvin at `127.0.0.1:8080`) are not Caption Studio's
  runtime. The stop call does not touch them, and LORA Train must not stop them either.

## 10. Caption quality so far (context)

Live runs on 2026-09-25 with copies of Petr's material:

| Captioning model | Material | Result |
|---|---|---|
| Qwen3.8 27B Q5 via Marvin | 4 character photos × 3 models | 12/12 saved; opening and trigger correct after the 0.2.0 fixes |
| Qwen3.8 27B Q5 via Marvin | 3 of Petr's clips (6 s, 12 s, 68 s) × 4 models | 12/12 saved, 16–31 s each; motion and a static camera described |
| Gemini 3.8 Flash (cloud) | the same clips × 4 models | 12/12 in one pass, 14–22 s |
| Gemini 3.8 Flash (cloud) | 4 photos × 3 models | 12/12, 6–9 s; no hair color leaked |

- Hair color and facial-hair color stay out when omitted.
- All video outputs of one clip are four separate requests; llama.cpp reuses no prompt cache
  between them for this hybrid model.

## 11. Sources

Code read locally on 2026-09-25:
- Caption Studio `dd6cd17`/`eb193a7`: `captioning/video.py`, `service.py`, `storage.py`,
  `media.py`, `paths.py`;
- LORA Train `513881b`: `backend/trainer/cache.py`, `dataset.py`, `next_flow.py`, `profiles.py`,
  `backend/caption_studio_bridge.py`;
- ai-toolkit `60d0c28` (2026-09-24);
- musubi-tuner `4e7c714` (2026-09-16) and the AkaneTendo25 `ltx-2` fork `9dc9abc`;
- diffusion-pipe `27eab43`;
- SimpleTuner `afc31c3`;
- DiffSynth-Studio (2026-09-21);
- LTX-2 (2026-08-26);
- MiniMax-H3 (2026-08-15), including `.claude/skills/h3-prompt-writing/references/base-en.txt`;
- Wan2.2 (2026-09-21);
- diffusers 0.40.0 in LORA Train's venv.

Documents:
- LTX-2.5 prompt guide and LoRA blog series (ltx.io, July–August 2026);
- QwenLM/Qwen-Image-2.1 README;
- IPRO, arXiv 2510.14255.

Design background: [VIDEO_LORA_PLAN.md](VIDEO_LORA_PLAN.md). Release notes:
[HANDOFF.md](HANDOFF.md).
