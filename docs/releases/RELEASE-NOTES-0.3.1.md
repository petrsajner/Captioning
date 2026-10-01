# Caption Studio 0.3.1 — every switch as measured: green, orange or greyed

**Caption Studio turns a folder of images and video clips into training captions for every major
image and video model — from one recipe, in one batch, on your own GPU or in the cloud.** It knows
whether you are training a character, a product or a visual style, writes the name the LoRA should learn
exactly once, describes what must stay promptable and deliberately leaves out what the LoRA has to learn.

![Caption Studio with the Clover character dataset](https://raw.githubusercontent.com/petrsajner/Captioning/main/docs/images/Caption-Studio-Clover.jpg)

---

## New in 0.3.1: we recommend, we do not forbid

0.3.0 greyed out switches it should have offered: with a cloud provider chosen but no model yet, every
model got the strictest offer, identity and accessories included. 0.3.1 replaces the yes/no offer with
what we measured.

**Green, orange, greyed.** Every detail switch is measured on every model in the table: how many test
captions followed it when you switch it.

| | Character, object, general | Visual style |
|---|---|---|
| **Green**: offered as usual | more than 85 % | more than 70 % |
| **Orange**: offered, the note says how often it held — check the captions | 50–85 % | 30–70 % |
| **Greyed**: stays at the LoRA type's default, with the reason | below 50 % | below 30 % |

A style is judged more loosely: a stray boat in a landscape matters less than a stray hair color in a
character. Your recipe keeps every choice, and a greyed switch returns with a model that can follow it.

**What the recommended models do.** GPT 6.1 Sol, Claude Opus 5.5 and Gemini 3.8 Flash: every switch
green. Orange: Qwen 3.8 Max (a style's background), Grok 4.7 (a style's content and background), Muse
Spark 1.3 (a character's hair color), GLM 5.3 FlashX (a style's content and background) and local Qwen (a
style's content and background). Nothing is greyed for them. The models we advise against follow the
switches better than their caption errors suggest: DeepSeek and MiMo Pro only describe a character's face
less reliably (orange); GLM 5V and MiMo Flash do not leave out what a style print depicts (greyed). The
settings show each model's orange and greyed switches next to its numbers.

**Every model can be chosen.** **Use this model** is on the models we advise against too, and it sets the
model at once. A model that is not in the table gets every switch.

**Measured again, and checked.** The style's background is a switch again (0.3.0 always described it):
every model was measured on a second set of prints, and the four models we advise against got a switch test
of their own. Every new test caption now records the prompt it really got, and only captions whose prompt
carried the switch as measured count; the older measurements were checked the same way against the code
they were made with.

**A rewrite that answers with a message is not saved.** One model answered a shortening with "please paste
the caption" and that text became the caption. Now Caption Studio keeps the caption it asked to shorten.

**Shorter length note.** Below the length slider: "The word count is a soft target."

## Download

| File | What it is |
|---|---|
| `Caption-Studio-Setup-0.3.1-Windows-x64.exe` | Installer — recommended. Per user, no admin rights, Start menu shortcuts including the manuals; installs WebView2 if Windows lacks it. Updates keep your settings, keys and session. |
| `Caption-Studio-0.3.1-Windows-x64-Portable.zip` | Portable edition — extract anywhere and run `CaptionStudio.exe`. |
| `Caption-Studio-Manual-EN.pdf`, `Caption-Studio-Manual-CS.pdf` | User manual in English and Czech (also installed with the app). |
| `SHA256SUMS.txt` | Checksums of the installer and the ZIP. |

Windows 10 or 11, 64-bit. Nothing else to install. The files are not code-signed yet, so Windows
SmartScreen may ask you to confirm: **More info → Run anyway**.
