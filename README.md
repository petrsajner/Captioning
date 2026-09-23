# Caption Studio

A standalone Windows application for preparing image captions for LoRA training.
Set a shared recipe, select images or a folder, and save matching UTF-8 captions
beside the originals: `image.txt` or `image.json`.

## Install

1. Run `Caption-Studio-Setup-<version>-Windows-x64.exe`. Installation is per user and
   does not require administrator access, Python, Node.js or another AI application.
2. Launch **Caption Studio** from the Start menu or desktop shortcut.
3. Choose **Local** or **Cloud API** in Setup and save your settings.

The interface defaults to English. Choose **Interface language** in Setup to switch
between English and Czech immediately. **Caption language** is a separate recipe
setting: changing the interface never translates your captions or changes their
language. The running version appears next to the application name and in the
desktop title bar.

Windows 10/11 x64 is supported. The desktop window uses Microsoft Edge WebView2;
if unavailable, the application opens your default browser. In browser mode,
closing the tab leaves the application running. Launch with `--browser` from a
terminal and use Ctrl+C to shut it down.

For the portable edition, extract the entire ZIP and run `CaptionStudio.exe`.
Keep its `_internal` directory beside the executable. Both editions include a
private Python runtime and store data in the same user profile by default.

## Connect a model

### Download a standalone local runtime

Select a model profile and compute backend, then click **Download runtime and
model**. Caption Studio downloads its own llama.cpp runtime, Qwen model and vision
projector. Downloads resume after interruption and are checked against SHA-256.
The prepared model starts automatically with your first batch. **Release GPU**
stops it; closing Caption Studio also stops the model it owns.

| Profile | Model download | Approximate VRAM | Use |
|---|---:|---:|---|
| IQ3 | 12.0 GB | 16 GB | Smaller download, lower precision |
| Q4 | 16.5 GB | 24 GB | Default |
| Q5 | 19.8 GB | 32 GB | Higher weight precision |

All profiles use Qwen3.8-27B. Allow another 0.93 GB for the vision projector and
roughly 2 GB for runtime downloads and extraction. Memory estimates assume a short
context; other GPU workloads and image sizes affect availability. CUDA 13.3 needs
a compatible NVIDIA driver. Vulkan and CPU are offered but have not been tested
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
2. Choose the dataset type, caption format, caption language, optional trigger,
   subject name and additional instructions.
3. Under **Choose what to include in the caption**, check details you want to
   change with prompts. Leave out details you want the LoRA to capture.
4. Select images and click **Create captions**. Captions are processed one at a time.
5. Click an image to review or edit its caption. Save with **Save caption** or Ctrl+S.
   **Regenerate** processes that image again and allows replacing its caption.

Checked details are described when visible; unchecked details are omitted. The
model receives an explicit instruction for every detail in both output modes.
**Apply defaults for this LoRA type** omits identity for character/object datasets
or style for style datasets, and includes the other details. Merely changing the
dataset type does not overwrite your choices. Existing recipes retain their
original include/omit meaning when upgraded.

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

### BRIA JSON (FIBO)

BRIA mode saves structured `.json` sidecars using BRIA's published image-analysis
field layout. It describes the subject, objects, scene, lighting, composition and
other selected details in named fields. Keys stay English; descriptive values use
the recipe's caption language. The trigger is inserted into `short_description`.

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

- **Skip existing captions** applies to both `.txt` and `.json`. To convert a caption,
  regenerate it or turn skipping off. After the new format is saved successfully,
  the other sidecar is archived in `.caption-backups` to avoid conflicting captions.
- Replaced captions are backed up byte for byte. Changes made outside the application
  block an overwrite until the dataset is reloaded. Duplicate image stems, such as
  `photo.jpg` and `photo.png` in the same folder, are reported before writing.
- Turn off **Save captions automatically** to keep results as drafts. The current
  dataset and drafts persist across restarts. Opening a new dataset without append
  replaces the current working list.
- Original images are unchanged. The model receives an oriented, resized copy with
  EXIF metadata removed. Multi-frame images are not supported.
- Local inference uses localhost. Downloads require internet. Cloud inference sends
  selected image copies and the recipe to the configured provider.
- API keys are encrypted with Windows DPAPI and separated by provider/server address.
  The local application API listens on `127.0.0.1` and requires a session token.

Data is stored in `%LOCALAPPDATA%/CaptionStudio`:

| Location | Contents |
|---|---|
| `settings.json` | Recipe, connections and interface language, without keys |
| `keys.json` | Encrypted API keys |
| `session.json` | Current dataset, captions and model response history |
| `runtime/models` | Downloaded weights and vision projector |
| `runtime/llama-b10821-*` | Downloaded inference runtime |
| `runtime/model.log` | Model diagnostics; may contain local prompts |
| `logs/generation.jsonl` | Request stages and counts, without captions, images or keys |

Models, settings and datasets survive uninstall. For an isolated profile, set
`CAPTION_STUDIO_DATA_DIR` before launch.

If a saved settings, key or session file cannot be used, for example after a
manual edit, the original is kept beside it as `<name>.damaged-<id>`. The
application starts with every value it can still use and reports the kept file once.

## Development

Use Python 3.11 x64 and `run.bat` to create the project environment and run from
source. `run.bat` installs the validated runtime pins from `requirements-lock.txt`
and reinstalls them when that file changes; `requirements.txt` lists only the direct
dependencies. Tests, linting, type checking and packaging tools are pinned in
`requirements-dev.txt`. Tool settings live in `pyproject.toml`.

```powershell
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m mypy
.venv/Scripts/python -m pytest -q
node --test tests/localization.test.cjs
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
