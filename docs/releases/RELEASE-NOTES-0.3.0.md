# Caption Studio 0.3.0 — precise captions, proven on today's models

**Caption Studio turns a folder of images and video clips into training captions for every major
image and video model — from one recipe, in one batch, on your own GPU or in the cloud.** It knows
whether you are training a character, a product or a visual style, writes the name the LoRA should learn
exactly once, describes what must stay promptable and deliberately leaves out what the LoRA has to learn.

![Caption Studio 0.3.0 with the Clover character dataset](https://raw.githubusercontent.com/petrsajner/Captioning/main/docs/images/Caption-Studio-Clover.jpg)

_The Clover dataset: the same character goes on to LORA Train and GIS (both coming soon)._

- **Four LoRA types, four ways of naming.** `Clover, a woman, …` for a character, `Zorbo, a backpack, …`
  for a product, `Zorvak style, …` for a style, a plain description for a general dataset.
- **ON/OFF per detail.** What the caption describes stays free for your prompts; what it leaves out
  (a face, a logo, a medium) is what the LoRA learns.
- **One dataset, every model.** Side-by-side caption files for FLUX.2, Qwen-Image, SDXL and any `.txt`
  trainer, BRIA FIBO JSON, WAN 2.2 (text and image to video), LTX-2.5 and MiniMax H3; video clips with
  motion and camera movement.
- **Local or cloud.** Marvin (our local Qwen3.8 27B), any local server, its own downloaded model, or
  OpenRouter, OpenAI and Google. A real Windows installer, nothing else to install.

---

## New in 0.3.0: tested until the captions are exact

The goal of this release: **precise captions for the widest range of images, on most of today's
models.** A caption for LoRA training is only useful if it describes exactly what you switched on and
never what you switched off — one stray "red hair" teaches the LoRA the wrong thing. So instead of
trusting the instructions, we measured them.

| | |
|---|---|
| Captions generated | **more than 7,700** |
| Checks of a caption against its image | **more than 8,200**, each by an independent reviewer, blind to the instructions it was written from |
| Models | **13**: local Qwen3.8 27B (Marvin) and 12 cloud models from OpenAI, Anthropic, Google, Alibaba, xAI, Meta, Z.ai, Xiaomi, DeepSeek and Moonshot |
| LoRA types | character, general, product, style |
| Test images | about 70: portraits and full figures in color, black-and-white and sepia; a product in the studio, outdoors and in hands; Japanese woodblock prints |
| Detail switches | every one, switched off and on one at a time, on two independent photo sets |

Every failure went back into the instructions, and every change was measured again, round after
round, until it held — and until it did not make the captions less accurate elsewhere.

**Exact caption rules.** Each detail now tells the model precisely what the caption must contain when
it is on and what it must never contain when it is off, and shortening follows the same rules. In the
first measurement 194 of 840 captions described something that was switched off; with the new rules the
recommended models follow every switch they are offered. The last gaps were closed one by one: with the
pose off, nothing the person holds is named (an umbrella, a wand, a bag); with a product's surroundings
off, not even the stand it rests on; hair color in a black-and-white photo is given as a tone; a
close-up's pose is the turn of the head.

**Switches that tell the truth.** A switch a model cannot follow is not offered to it: it is greyed out
at the LoRA type's default with the reason next to it, and your recipe keeps its choice for a model that
can follow it. GPT, Claude, Gemini, Qwen Max, Grok, GLM FlashX and local Qwen follow every switch
except two of a style LoRA — no model reliably leaves the content or background out of a print, so
those stay described. An unknown model gets the strictest offer.

**The palette is back** for style LoRAs: every recommended model describes it when asked.

## Which model to use

The settings now show every model we measured, the recommended ones by quality in a green zone and the
ones we advise against in a red zone, with seconds per caption and price per 100 captions. **Use this
model** fills in the right ID for your provider.

![The measured models in Caption Studio's settings](https://raw.githubusercontent.com/petrsajner/Captioning/main/docs/images/Caption-Studio-Models.jpg)

| # | Model | Clear errors per 10 captions | Seconds per caption | $ per 100 captions |
|---|---|---|---|---|
| 1 | GPT 6.1 Sol | 0.0 | ~9 | ~1.50 |
| 2 | Claude Opus 5.5 | 0.0 | ~13 | ~3.90 |
| 3 | Gemini 3.8 Flash | 0.4 | ~12 | ~0.85 |
| 4 | Qwen 3.8 Max | 0.7 | ~61 | ~2.95 |
| 5 | Grok 4.7 | 0.7 | ~43 | ~3.45 |
| 6 | Muse Spark 1.3 | 0.7 | ~44 | ~2.25 |
| 7 | GLM 5.3 FlashX | 1.9 | ~14 | ~0.36 |

_Measured on the 55 hardest shots with 40-word captions, September 2026. We advise against GLM 5V Turbo,
MiMo 2.6 Flash and Pro, DeepSeek V4.1 Flash and Kimi K3._

**Local Qwen now reasons.** While it looks at the image, local Qwen (Marvin or the managed runtime)
reasons, and it shortens without reasoning: about half the clear errors, about 23 s per caption on an
RTX 5090, still free and private. A local server that cannot reason gets a notice and the strictest
switch offer.

**Faster, cheaper cloud rewrites.** Shortening and completing a caption use the least reasoning each
provider accepts (OpenRouter minimal, Google none, OpenAI low). Blind A/B checks found the same quality;
Claude rewrites twice as fast, Qwen Max from 117 to 15 seconds.

**The shortest reliable length.** Below the length slider Caption Studio shows the shortest caption that
still describes everything you switched on, for your model: about 40 words for a character on GPT,
Claude, Qwen Max and Grok, 60 on Gemini, Muse, GLM FlashX and local Qwen. It is a note, never a limit.

**Clearer problems.** A provider error shows the provider's own message (an 18+ confirmation, an
exhausted credit). An answer that is not a caption — a message to the user, stray markup — is kept to
review instead of saved, and reasoning some models leave in the text is removed.

## Download

| File | What it is |
|---|---|
| `Caption-Studio-Setup-0.3.0-Windows-x64.exe` | Installer — recommended. Per user, no admin rights, Start menu shortcuts including the manuals; installs WebView2 if Windows lacks it. Updates keep your settings, keys and session. |
| `Caption-Studio-0.3.0-Windows-x64-Portable.zip` | Portable edition — extract anywhere and run `CaptionStudio.exe`. |
| `Caption-Studio-Manual-EN.pdf`, `Caption-Studio-Manual-CS.pdf` | User manual in English and Czech (also installed with the app). |
| `SHA256SUMS.txt` | Checksums of the installer and the ZIP. |

Windows 10 or 11, 64-bit. Nothing else to install: Python, the Visual C++ runtime and everything the app
needs are included. A graphics card is optional (see the manual for the supported cards). The files are
not code-signed yet, so Windows SmartScreen may ask you to confirm: **More info → Run anyway**.
