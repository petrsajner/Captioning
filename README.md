# Caption Studio

A standalone Windows application for preparing image captions for LoRA training.
Set a shared recipe, select images or a folder, and save matching UTF-8 captions
beside the originals: `image.txt` or `image.json`.

## Install

1. Run `Caption-Studio-Setup-<version>-Windows-x64.exe`. Installation is per user and
   does not require administrator access, Python, Node.js or another AI application.
   Nothing has to be installed beforehand: the package includes its Python runtime and
   the Visual C++ runtime that the local model needs, and if Windows lacks Microsoft Edge
   WebView2 Runtime (for the application window), the installer downloads and installs it.
2. Launch **Caption Studio** from the Start menu or desktop shortcut.
3. Choose **Local** or **Cloud API** in Setup and save your settings. No graphics card is
   needed for Cloud API; on a computer without an NVIDIA card the setup starts there. The
   local model is optional and runs best on an NVIDIA card.

The interface defaults to English. Choose **Interface language** in Setup to switch
between English and Czech immediately. **Caption language** is a separate recipe
setting: changing the interface never translates your captions or changes their
language. The running version appears next to the application name and in the
desktop title bar.

Windows 10/11 x64 is supported. The desktop window uses Microsoft Edge WebView2;
if it could not be installed (for example without an internet connection during
setup), the application opens your default browser. In browser mode,
closing the tab leaves the application running. Launch with `--browser` from a
terminal and use Ctrl+C to shut it down.

For the portable edition, extract the entire ZIP and run `CaptionStudio.exe`.
Keep its `_internal` directory beside the executable. Both editions include a
private Python runtime and keep all their data in a `data` folder next to
`CaptionStudio.exe`, so a copy can be moved or run from any folder or drive.

## Connect a model

### Download a standalone local runtime

Select a model profile and compute backend, then click **Download runtime and
model**. Caption Studio downloads its own llama.cpp runtime, Qwen model and vision
projector. Downloads resume after interruption and are checked against SHA-256.
The prepared model starts automatically with your first batch. **Release GPU**
stops it; closing Caption Studio also stops the model it owns.

| Profile | Model download | Measured GPU memory | Card | Use |
|---|---:|---:|---:|---|
| Q2 | 9.8 GB | 13.0 GiB | 16 GB | Smallest; images analyzed on the graphics card |
| IQ3 | 12.0 GB | 13.6 GiB | 16 GB | Lower precision; images analyzed on the processor, about 3 minutes per 30-frame clip caption |
| Q4 | 16.5 GB | 18.9 GiB | 24 GB | Default; about 18 s per 30-frame clip caption |
| Q5 | 19.8 GB | — | 32 GB | Higher weight precision |

All profiles use Qwen3.8-27B with a 64k context (`-c 65536`, Q8 cache, `--fit off`) and
llama.cpp b10935, the same files and placements as Marvin. The measured memory comes
from Marvin's qualification on an RTX 5090 and excludes other programs. Allow another
0.93 GB download for the vision projector and roughly 2 GB for runtime downloads and
extraction. A new runtime release replaces the older one after it is downloaded. CUDA
13.3 needs a compatible NVIDIA driver. Vulkan and CPU are offered but have not been tested
on every supported hardware configuration. CPU inference is slow.

### Use an existing local server

Click **Find local servers** to check common localhost addresses for Ollama,
LM Studio, llama.cpp, Unsloth and compatible servers. Select a result, choose an
image-capable model and save. If a key is required, enter **Local API key** and click
**Load models**. For a custom port, choose **Existing local server** and enter its
base API address, such as `http://127.0.0.1:1234/v1`.

Discovery reads model lists; it does not scan disks, download models, start or stop
external processes. Port labels are hints, and a model appearing in a list does
not establish image support. The original application must keep its server running.
Local keys are stored separately for each exact API address.

### Cloud API

Select a provider, enter its API key and an image-capable model ID. **Load available
models** can help find the ID. OpenRouter, Gemini and other compatible image Chat
Completions APIs can be used. Cloud mode needs no local model download or powerful
GPU. Selected images are sent to the chosen provider and billed under its terms.

## Prepare a dataset

1. **Open folder** or **Select images**. Optionally include subfolders or append to
   the open dataset. The folder browser shows thumbnails, an expandable tree,
   breadcrumbs, Back/Forward, Up, Home and Refresh. Shortcuts: Alt+Left/Right,
   Alt+Up, Ctrl+L and F5.
2. Choose what you are training, the caption output, the trigger and, for a character
   or an object, its type; then the caption format, caption language and additional
   instructions.
3. Under **Choose what to include in the caption**, check details you want to
   change with prompts. Leave out details you want the LoRA to capture.
4. Select images and click **Create captions**. Captions are processed one at a time.
5. Click an image to review or edit its caption. Each caption file of the image has
   its own tab (`.txt`, `.json`, `.wan.txt`, `.wan-i2v.txt`, `.ltx.txt`, `.h3.txt`). Save with
   **Save caption** or Ctrl+S. **Regenerate** creates the open tab's caption again
   and allows replacing it.

Checked details are described when visible; unchecked details are omitted. The
model receives an explicit instruction for every detail in every output. Each LoRA type
has its own details, and **Apply defaults for this LoRA type** leaves out the ones in bold:

| Type | Details |
|---|---|
| Character / person, General | **Identity**, **Hair color** (character only), Hairstyle, Clothing, Accessories, Pose and action, Facial expression, Environment, Lighting, Composition and camera, Visual style |
| Object / product | **Object appearance**, **Logo and text on the object**, Variant and state, Placement and orientation, Use and interaction, Environment, Lighting, Composition and camera, Medium |
| Visual style | What is depicted, Pose and action, Environment, Light situation, Composition and camera, **Medium and technique**, **Color palette and grading** |

Clips add **Motion over time** and **Camera movement** for every type. Every type keeps its
own choices: switching to another type shows that type's details, and switching back
restores what you chose for it. Hair color and hairstyle are separate details: a
character's hair color usually belongs to the LoRA while its hairstyle (loose, ponytail,
bangs) stays free for prompts. For an object with several colorways that should stay
promptable, say so in the additional instructions; **Variant and state** then names the
colorway. Existing recipes keep their choices when upgraded; a style recipe that left out
"Visual style" now leaves out both medium and palette.

### What you are training

**What are you training?** decides how every caption output names what the LoRA learns:

| Type | Fields | A caption starts | Learned by the LoRA (default details left out) |
|---|---|---|---|
| Character / person | Character name, Character type (`a woman`) | `Velmira, a woman, sits…`, later "the woman" or "she" | face and body, hair color |
| Object / product | Object name, Object type (`a backpack`) | `Zorbo, a backpack, hangs…`, later "the backpack" or "it" | the object's shape, material, colors and markings; its logo and text |
| Visual style | Style name | `Zorvak style, a woman sits…` | medium, technique, brushwork, texture; palette and grading |
| General dataset | Trigger word (optional) | `ohwx, a woman sits…` | nothing in particular |

For a character or an object the model writes a placeholder where it first names the
subject and never sees the trigger; Caption Studio writes the trigger and the type there,
so the trigger appears exactly once. People who hold or use an object are described in
their own right. Style captions describe only the content, people generically, and never
the medium or technique (words such as painting, illustration or photo). A style name that
already ends in "style" is used as it is. The type is written as entered, so write it in
the caption language; video model captions are English.

### Normal captions

Normal mode saves `.txt` descriptions or tags. The word count is a soft target,
including the trigger. Complete captions up to 120% of the target are kept.
Longer captions are sent back to the model for a shorter version of the same text.
After two unsuccessful revision attempts, the shortest complete version is kept
with a notice, even if still over the target. Text is never sliced to meet a count.

Caption Studio does not send an output-token cap. Old `max_tokens` settings are
ignored. A provider's stop reason alone does not turn a complete caption into an
error. Suspected incomplete endings are offered for automatic completion. If no
complete result can be obtained, the received draft is retained as **To review**
and existing captions are preserved. Connection problems pause the batch; **Continue**
resumes remaining images without repeating completed work.

**Model responses** keeps the original and revised texts available for inspection
or reuse in the editor. Stopping during a revision retains the response received so far.

### Video model captions (WAN 2.2, LTX-2.5, MiniMax H3)

For LoRAs of video models. Photos and video clips (`.mp4`, `.mov`, `.webm`,
`.mkv`, `.m4v`, `.avi`) can be in the same dataset. Every model gets its own caption
file next to the media, in the shape its prompts use:

| Output | File | For | Shape |
|---|---|---|---|
| WAN 2.2 | `name.wan.txt` | photos, clips | Plain sentences: the character and action, details, setting, lighting, shot |
| WAN 2.2 I2V | `name.wan-i2v.txt` | clips | Only the motion and the camera movement, at most 100 words; the first frame shows the rest |
| LTX-2.5 | `name.ltx.txt` | photos, clips | One present-tense paragraph that opens with the shot |
| MiniMax H3 | `name.h3.txt` | photos, clips | The official three fields; a photo is a static `[Shot 1]`; sound is `N/A` |

**All video models** creates every file that applies in one batch. Normal and BRIA
describe photos only; clips show "Video models only" there.

**Clips.** Caption Studio reads prepared clips and never changes them. The model receives
one frame every 0.5 s (Settings → Analysis settings: 0.25, 0.5 or 1 s), at most 30
frames of about one megapixel each, each labeled with its time; longer clips get 30
frames spread evenly. The details **Motion over time** and **Camera movement** appear for
the video models and describe what happens over the clip. The inspector plays the clip,
shows its size, length, frame rate and audio, the frames sent to the model, and what the
selected model trains on. For cloud APIs the frames are compressed further if a request
would exceed 18 MB. The captions are English
descriptions; caption language and tags do not apply. A character or an object is named
once as described above, for example `Velmira, a woman, sits by the window…`: at the very
start for WAN, after the opening shot for LTX and inside `[Shot 1]` for H3. Style and
general captions start with the trigger, for H3 inside `[Shot 1]`; for a style LoRA H3
opens with the composition instead of style words. An invented, readable trigger works
better than tokens such as `sks`, which trainers also find inside other words. H3 files
are validated for their three fields when saved. The details chosen in the recipe apply
as usual.

ai-toolkit and musubi-tuner read these files with `caption_ext: "wan.txt"` or
`caption_extension = ".wan.txt"`. See [docs/VIDEO_LORA_PLAN.md](docs/VIDEO_LORA_PLAN.md)
for the rules and their sources.

### BRIA JSON (FIBO)

BRIA mode saves structured `.json` sidecars using BRIA's published image-analysis
field layout. It describes the subject, objects, scene, lighting, composition and
other selected details in named fields. Keys stay English; descriptive values use
the recipe's caption language. The trigger goes into `short_description`, the same way
as in Normal captions; for a character or an object, the main subject's description in
`objects` is its type.

The normal word target does not apply to JSON, and there is no application output-token
cap. Responses are parsed and validated, then repaired automatically when needed.
An unrepaired response remains a reviewable draft. Manual saves are validated too.
Required descriptive fields intentionally omitted by the recipe may be empty;
optional fields can be omitted. The include/omit policy also applies to summaries
and free-text fields.

The output is a JSON sidecar, not a training job or trainer-specific CSV export.
The official FIBO training pipeline may require additional dataset packaging.
See [BRIA's schema](https://github.com/Bria-AI/FIBO/blob/main/src/fibo_inference/vlm/gemini_api.py),
[fine-tuning guide](https://github.com/Bria-AI/FIBO/blob/main/src/fine_tuning/README.md)
and [caption normalizer](https://github.com/Bria-AI/FIBO/blob/main/src/fibo_inference/parse_caption.py).

## Files and privacy

- Every output has its own file next to the image: `.txt`, `.json`, `.wan.txt`,
  `.ltx.txt` and `.h3.txt`. They coexist, and saving one never changes another; a
  trainer picks the file for the model it trains. **Skip existing captions** checks
  only the selected output's file.
- Replaced captions are backed up byte for byte. Changes made outside the application
  block an overwrite of that file until the dataset is reloaded. Images that would
  share a caption file, such as `photo.jpg` and `photo.png`, or `photo.jpg` and
  `photo.wan.png`, are reported before writing.
- Turn off **Save captions automatically** to keep results as drafts. The current
  dataset and drafts persist across restarts. Opening a new dataset without append
  replaces the current working list.
- Original images and clips are unchanged. The model receives an oriented, resized copy
  with EXIF metadata removed, or re-encoded frames of a clip. Multi-frame images are not
  supported.
- Local inference uses localhost. Downloads require internet. Cloud inference sends
  selected image copies and the recipe to the configured provider.
- API keys are encrypted with Windows DPAPI and separated by provider/server address.
  The local application API listens on `127.0.0.1` and requires a session token.

Data is stored in the `data` folder next to `CaptionStudio.exe`:

| Location | Contents |
|---|---|
| `settings.json` | Recipe, connections and interface language, without keys |
| `keys.json` | Encrypted API keys |
| `session.json` | Current dataset, captions and model response history |
| `runtime/models` | Downloaded weights and vision projector |
| `runtime/llama-b10935-*` | Downloaded inference runtime |
| `runtime/model.log` | Model diagnostics; may contain local prompts |
| `logs/generation.jsonl` | Request stages and counts, without captions, images or keys |

Models, settings and datasets survive uninstall. For an isolated profile, set
`CAPTION_STUDIO_DATA_DIR` before launch. If the program folder cannot be written to,
data is kept in `%LOCALAPPDATA%/CaptionStudio` instead and the application says so.

Versions before 0.1.13 kept data in `%LOCALAPPDATA%/CaptionStudio`. The first start
of a newer installed or portable copy moves it into its `data` folder once. On the
same drive everything moves instantly. On another drive, settings, keys and the
session move and the application explains how to move the downloaded model. Saved
API keys are tied to your Windows account; on another computer, enter them again.

If a saved settings, key or session file cannot be used, for example after a
manual edit, the original is kept beside it as `<name>.damaged-<id>`. The
application starts with every value it can still use and reports the kept file once.

## Development

Use Python 3.11 x64 and `run.bat` to create the project environment and run from
source. `run.bat` installs the validated runtime pins from `requirements-lock.txt`
and reinstalls them when that file changes; `requirements.txt` lists only the direct
dependencies. Tests, linting, type checking and packaging tools are pinned in
`requirements-dev.txt`. Tool settings live in `pyproject.toml`. UI formatting uses Prettier,
pinned in `package.json`; Node.js is needed only for development, not by the application.

```powershell
.venv/Scripts/python -m pip install -r requirements-dev.txt
npm ci
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m mypy
.venv/Scripts/python -m pytest -q
npm run format:check
npm test
npm run test:ui
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

Building requires Inno Setup 6. The build produces an installer, portable ZIP and
SHA-256 manifest in `dist/`. It does not bundle model weights. The optional
`setup_local.py --profile q4 --backend cuda` performs runtime download from the CLI;
run only one download operation per profile at a time.

Implementation, comments and diagnostics use English. Czech text lives in
`ui/locales/cs.json` and `installer/locales/cs.isl`; `ui/locales/en.json` holds
English language data. Caption text is never passed through interface localization.
See [the development handoff](docs/HANDOFF.md) for architecture and verification.

[JoyCaption Alpha Two](https://huggingface.co/spaces/fancyfeast/joy-caption-alpha-two)
inspired the shared caption workflow. This application uses its own batch engine
and [Qwen GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) through
[llama.cpp](https://github.com/ggml-org/llama.cpp); JoyCaption weights are not bundled.
