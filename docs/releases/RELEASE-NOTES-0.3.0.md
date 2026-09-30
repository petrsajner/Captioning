# Caption Studio 0.3.0 — switches that keep their word

**Every detail switch now does what it says, on every model we recommend, and the app tells you which
models to use.** Before this release a switched-off detail could still slip into a caption, and nobody
knew which models followed the switches at all. For 0.3.0 every switch of every LoRA type was measured
on eight models, switched off and on one at a time, with every caption judged blind against its image.
The rules that failed were rewritten and measured again until they held.

## What changed for you

**Exact caption rules.** Each detail tells the model precisely what the caption must contain when it is
on and what it must never contain when it is off, and shortening follows the same rules. Clear leaks of
switched-off details fell from 194 in 840 captions to almost none; four more fixes close the last gaps:

- with the pose off, nothing the person holds or carries is named (umbrellas, wands and bags leaked before);
- with an object's background off, not even the stand or sill it rests on;
- hair color on a black-and-white photo is given as a tone;
- identity names at least one feature of the face or body, not only a moustache.

**Switches offered per model.** A switch a model cannot follow is greyed out at the LoRA type's default,
with the reason next to it; your recipe keeps its choice and gets it back with a model that can follow
it. GPT, Claude, Gemini, Qwen Max, Grok, GLM FlashX and local Qwen follow every switch except two of a
style LoRA: no model reliably leaves out a print's content or background, so those stay described. Muse
Spark does not describe a character's hair color reliably. An unknown model gets the strictest offer.

**The palette is back** for style LoRAs: every recommended model describes it when asked.

**Recommended models.** The cloud settings show the measured models, recommended ones by quality in a
green zone and the ones we advise against in a red zone, each with its quality, seconds per caption and
price per 100 captions. "Use this model" fills in the right ID for your provider.

| # | Model | Clear errors / 10 | s / caption | $ / 100 |
|---|---|---|---|---|
| 1 | GPT 6.1 Sol | 0.0 | ~9 | ~1.50 |
| 2 | Claude Opus 5.5 | 0.0 | ~13 | ~3.90 |
| 3 | Gemini 3.8 Flash | 0.4 | ~12 | ~0.85 |
| 4 | Qwen 3.8 Max | 0.7 | ~61 | ~2.95 |
| 5 | Grok 4.7 | 0.7 | ~43 | ~3.45 |
| 6 | Muse Spark 1.3 | 0.7 | ~44 | ~2.25 |
| 7 | GLM 5.3 FlashX | 1.9 | ~14 | ~0.36 |

We advise against GLM 5V Turbo, MiMo 2.6 Flash and Pro, DeepSeek V4.1 Flash and Kimi K3.

**Local Qwen reasons.** While it looks at the image, local Qwen (Marvin or the managed runtime) now
reasons, and it shortens without reasoning: about half the clear errors, about 23 s per caption on an
RTX 5090. A local server that cannot reason gets a notice and the strictest switch offer.

**Faster, cheaper cloud rewrites.** Shortening and completing a caption use the least reasoning the
provider accepts (OpenRouter minimal, Google none, OpenAI low). Blind A/B checks found the same quality;
Opus rewrites twice as fast, Qwen Max's from 117 to 15 seconds.

**Recommended length.** Below the length slider, the shortest reliable caption length for your model and
the number of switched-on details: about 40 words for a character on GPT, Claude, Qwen Max and Grok,
60 on Gemini, Muse, GLM FlashX and local Qwen.
It is a note, never a limit.

**Clearer problems.** A provider error shows the provider's own message (an 18+ confirmation, exhausted
credit). An answer that is not a caption, such as a message to the user or stray markup, is kept to
review, and reasoning blocks some models return in the text are removed.
