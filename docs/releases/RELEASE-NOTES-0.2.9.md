# Caption Studio 0.2.9 — LoRA captions that know what you are training

**Caption Studio turns a folder of images and video clips into training captions for every major
image and video model — from one recipe, in one batch, on your own GPU or in the cloud.** It knows
whether you are training a character, a product or a visual style, writes the name the LoRA should
learn exactly once where it belongs, describes what must stay promptable and deliberately leaves out
what the LoRA has to learn. One dataset gets a separate, correctly shaped caption file for FLUX.2,
Qwen-Image, SDXL, BRIA FIBO, WAN 2.2, LTX-2.5 and MiniMax H3 — side by side, never overwriting each
other. It is a standalone Windows app: install, pick a model, open a folder, done.

![Caption Studio with the Clover character dataset](https://raw.githubusercontent.com/petrsajner/Captioning/main/docs/images/Caption-Studio-Clover.jpg)

_The Clover dataset: the same character goes on to LORA Train and GIS (both coming soon)._

---

## Captions that know what you are training

Most captioners describe everything they see. That is exactly wrong for a LoRA: whatever the caption
describes stays tied to the prompt, and whatever it leaves out is what the LoRA learns. Caption Studio
makes that choice explicit.

**Four LoRA types, four ways of naming.** A character is written once where she first appears and later
as "the woman" or "she":

> Clover, a woman, has long, wavy hair worn loose and flowing to the side. She wears a bright red wrap
> dress with a V-neckline, short flutter sleeves, and a knot tied at the waist. Her arms are extended
> outward and her head is tilted upward with a smile, looking toward the sky…

Notice what is missing: her face and hair color. Those are what the LoRA learns; the hairstyle, the dress
and the square stay free for your prompts.

- **Products and styles get their own grammar.** A product is `Zorbo, a backpack, …`, with the people
  who hold it described generically. A style opens with `Zorvak style, …` and then describes only the
  content, never the medium or the technique, so the look belongs to the name. A general dataset gets a
  plain description with an optional trigger.
- **ON/OFF details per type.** Each type has its own set: face and hair color vs. hairstyle, clothing,
  pose and expression for a character; appearance, logo and text, variant and state for a product;
  medium and technique, palette and grading for a style. ON = free to change in future prompts,
  OFF = fixed in the LoRA. **Apply defaults for this LoRA type** gives the proven starting point, and
  every type remembers its own choices.
- **Readable image text, additional instructions** and a **preview of the exact instructions** the
  model receives.

## One dataset, every model

| You train | Caption output | File |
|---|---|---|
| FLUX.2, FLUX.2 Klein, Z-Image, Krea 2, Qwen-Image, SDXL, any `.txt` trainer | Normal (description or tags, English or Czech) | `name.txt` |
| BRIA FIBO | Structured JSON, validated and repaired automatically | `name.json` |
| WAN 2.2 text-to-video | Subject, action, setting, light and shot | `name.wan.txt` |
| WAN 2.2 image-to-video | Only the motion and the camera — the start frame shows the rest | `name.wan-i2v.txt` |
| LTX-2.5 | One present-tense paragraph that opens with the shot | `name.ltx.txt` |
| MiniMax H3 | The three official fields, starting with `[Shot 1]` | `name.h3.txt` |

**All video models** writes every file that applies in one batch. The files coexist: creating one never
changes another, so one folder serves several trainers.

![Every video model's caption file for the same image, next to the character's detail switches](https://raw.githubusercontent.com/petrsajner/Captioning/main/docs/images/Caption-Studio-Video-Models.jpg)

_The same Clover image with its WAN 2.2, LTX-2.5 and MiniMax H3 captions; on the left, face and hair color
are OFF (learned by the LoRA) while hairstyle, clothing, pose and the rest stay ON (promptable)._

## Video clips, understood over time

Photos and clips (MP4, MOV, WEBM, MKV, M4V, AVI) live in the same dataset. For a clip the model sees a
frame every 0.5 s (up to 30, each labelled with its time) and the recipe adds **Motion over time** and
**Camera movement**. The review panel plays the clip, shows exactly the frames the model saw and what the
selected video model trains on (for example WAN 2.2 at 16 fps, up to 81 frames).

## Run the model where you want

- **Marvin — recommended.** Our local Qwen3.8 27B harness
  ([github.com/petrsajner/marvin](https://github.com/petrsajner/marvin)) runs the same vision model on
  profiles measured for 16, 24 and 32 GB cards. Start Marvin and Caption Studio finds it with one click:
  free, private, one model for both apps.
- **Cloud API** — OpenRouter, OpenAI, Google Gemini or any compatible API. No graphics card needed;
  keys are stored encrypted for your Windows account.
- **Any local server** — Ollama, LM Studio, llama.cpp, vLLM, Unsloth; **Find local servers** checks the
  usual addresses for you.
- **Its own model** — one click downloads Qwen3.8 27B with its vision projector and a llama.cpp runtime
  (CUDA, Vulkan or CPU); resumable and SHA-256 verified.

## Built for real datasets

- Up to 20,000 files per dataset, thumbnails, filters (without captions, errors, to review) and search.
- A tab for every caption file of an image, word count, **Ctrl+S**, regenerate one image, and the full
  history of model responses.
- The word count is a soft target: captions up to 120 % are kept, longer ones are shortened by the
  model — **never cut mid-sentence**. Cut-off endings are completed; anything uncertain stays a draft
  **to review** instead of overwriting a good file.
- Replaced captions are backed up byte for byte; files changed outside the app are never overwritten;
  a lost connection pauses the batch and **Continue** picks up where it stopped.
- Originals are never touched; the model gets a resized copy without EXIF metadata.
- English and Czech interface; English or Czech captions.

## How it compares

We went through more than twenty captioning tools in September 2026: TagGUI, JoyCaption and its GUIs,
BooruDatasetTagManager, VisionCaptioner, Qwen3-VL Captioner, LoRA Dataset Studio, the captioners built
into kohya_ss, OneTrainer, ai-toolkit, FluxGym, musubi-tuner and the LTX-2 trainer, Flimmer, the ComfyUI
caption nodes and the cloud services. Several of them are excellent at one thing — TagGUI and
BooruDatasetTagManager at editing tags, ai-toolkit at captioning video with sound. **None of them does
what Caption Studio does as a whole**, and most of the list below we found nowhere else:

| | Caption Studio | Best of the rest |
|---|---|---|
| Separate caption files for several models side by side (`.txt`, FIBO `.json`, WAN T2V and I2V, LTX, H3) | ✓ | One file per image; ai-toolkit adds a MiniMax preset |
| What to describe vs. what the LoRA learns, switchable per detail and per LoRA type | ✓ | Fixed presets per type (Flimmer, LoRA Dataset Studio, fal) |
| The name written once where the subject first appears | ✓ | Trigger prepended to the caption |
| Caption quality: soft length target, completed endings, drafts to review, byte-exact backups, no overwrite of files edited elsewhere | ✓ | Skip finished files, retry |
| Cloud API, any local server with auto-discovery, or its own model with measured VRAM profiles | ✓ all three | One or two of them |
| Video clips with motion and camera movement, shaped per video model | ✓ | ai-toolkit, VisionCaptioner, BooruDatasetTagManager (frames) |
| A real Windows installer, nothing else to install | ✓ | BooruDatasetTagManager, LoRA Dataset Studio |

## Part of one pipeline

**Caption Studio → LORA Train → GIS.** LORA Train and GIS are coming soon. The Clover dataset in the
picture is captioned here, trained into a LoRA in LORA Train (which reads these caption files straight
from the folder, one file per training profile) and used for generation in GIS.

## Download

| File | What it is |
|---|---|
| `Caption-Studio-Setup-0.2.9-Windows-x64.exe` | Installer — recommended. Per user, no admin rights, Start menu shortcuts including the manuals; installs WebView2 if Windows lacks it. |
| `Caption-Studio-0.2.9-Windows-x64-Portable.zip` | Portable edition — extract anywhere and run `CaptionStudio.exe`. |
| `Caption-Studio-Manual-EN.pdf`, `Caption-Studio-Manual-CS.pdf` | User manual in English and Czech (also installed with the app). |
| `SHA256SUMS.txt` | Checksums of the installer and the ZIP. |

Windows 10 or 11, 64-bit. Nothing else to install: Python, the Visual C++ runtime and everything the app
needs are included. A graphics card is optional (see the manual for the supported cards). The files are
not code-signed yet, so Windows SmartScreen may ask you to confirm: **More info → Run anyway**.
