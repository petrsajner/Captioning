# Caption Studio — handoff 2026-09-06

## Zadání a závazná hranice

Samostatná Windows aplikace pro dávkové popisky LoRA datasetů. Společný recept,
výběr souborů/složky, vlastní lokální vision model a volitelné cloudové API.
Uživatel výslovně upřesnil, že Marvin (`QWEN local`) je pouze vývojový vzor:
čistá instalace musí vytvořit vlastní prostředí a stáhnout vlastní modely.
Žádná produkční cesta na Marvina, import jeho kódu ani sdílení jeho runtime není použito.

## Dodaná verze

0.1.0. Privátní Python 3.11, FastAPI/HTTPX/Pillow, pywebview + WebView2.
Sestavený Inno Setup instalátor a ZIP s portable adresářem jsou v `dist/`.
Nainstalováno pro aktuálního uživatele do `%LOCALAPPDATA%\Programs\Caption Studio`.
Vlastní data/modely v `%LOCALAPPDATA%\CaptionStudio`.

Výchozí model Qwen3.8-27B UD-Q4_K_M byl skutečně stažen z Hugging Face
(16 464 440 224 bajtů) spolu s mmproj-F16 (927 607 488 bajtů).
Pin modelu i SHA-256 jsou v `captioning/runtime.py`, ověření v `runtime/verified.json`.
Vlastní llama.cpp b10821 CUDA 13.3 byl skutečně stažen, rozbalen a spuštěn.
Váhy z Marvina nebyly použity ani kopírovány.

## Ověření

- 17 automatických testů: sidecary UTF-8, diakritika, zálohy, externí úpravy
  před i během inference, kolize názvů včetně nevybraného sourozence, rekurzivní import,
  poškozené obrázky, chyby dávky, skip, návrhy a obnova, okamžité i průběžné zrušení,
  sestavení obrazového payloadu, neúplné odpovědi, cloudové chyby bez úniku klíče,
  DPAPI odděleně pro endpointy, izolace lokálního API, navazující stahování,
  SHA-256 a odmítnutí zip traversal.
- Skutečný browser workflow: otevření adresáře dvou fotografií, oba viditelné
  náhledy, dávka, hotové popisky, ruční úprava, záloha a opakovaný skip.
- Qwen na RTX 5090: dva obrázky v prvním běhu 2,4 s a 3,1 s (model už byl načtený).
  Instalovaná zabalená aplikace také spustila vlastní model a regenerovala popisek
  za 2,7 s. Kontext 8192, obrazový projektor, následně minimum 1024 obrazových tokenů.
- Skutečné desktopové okno instalované aplikace bylo vizuálně zkontrolováno přes
  computer-use: galerie, detail, editor a nativní výběr složky. Výběr složky se
  otevřel z bundlovaného procesu; samotný výběr testovacího datasetu byl ověřen
  polem Cesta. Automatizační nástroj nedokázal zaměřit pomocný systémový dialog.
- Zavření okna přes Alt+F4 ukončilo vlastní llama-server a vrátilo paměť GPU
  z přibližně 20,8 GB na přibližně 2,9 GB používaných jinými aplikacemi.
- Instalátor instalace i aktualizace exit 0, bez restartu/správce.
- `scripts/smoke_package.py`: skutečný instalovaný EXE v prázdném profilu,
  pracovním adresáři bez zdrojů, bez PYTHONPATH/PYTHONHOME a s PATH pouze System32.
  Zobrazení UI, výchozí průvodce, import obrázku, JPEG náhled a zápis `.txt` prošly.
- Portable ZIP prošel kontrolou CRC; obsahuje 1280 položek.
- Finální build: `output/final-build.log`; neblokující varování se týká nedostupného
  Android backendu pywebview při Windows buildu a dvou deprecation hlášení testů.
- Finální přeinstalovaný balíček po úpravě promptu prošel znovu reálnou dávkou:
  2 uložené popisky, 0 chyb, 2,5 s a 3,1 s. Ověřeny přesné soubory UTF-8 bez BOM.
  Výsledky jsou v `output/live-smoke.json`; snímek UI v `output/playwright/final.png`.

Finální distribuční součty SHA-256:

```text
7affb4a0e3c27a03a130d1299a7cf2614baf1fc2efca5e8f96151f5aa96332f6  Caption-Studio-Setup-0.1.0-Windows-x64.exe
37b4891641a599dda24b8c00445e4b3cbcec306e20e80c3bfaf489f3b6986e0e  Caption-Studio-0.1.0-Windows-x64-Portable.zip
```

Testovací fotografie (jen v `output/test-dataset`, nejsou součástí distribuce):
https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/coco_sample.png
https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg
Snímky browser UI jsou v `output/playwright/`, průběh instalace v `output/install-final.log`.

## Limity a další práce

- Živé cloudové volání nebylo provedeno: uživatel bude zadávat klíč v nastavení.
  Cloud používá kompatibilní `/models` a `/chat/completions` s obrazovým vstupem.
  Seznam může obsahovat textové modely; není to důkaz vision podpory. Parametry
  konkrétních cloudových modelů se liší. Při doplňování providerů ověřit jejich
  aktuální primární dokumentaci a reálný obrazový požadavek.
- Vulkan/CPU ani IQ3/Q5 nebyly ověřeny na jiném hardwaru; VRAM v UI je odhad.
- Modelové popisky nejsou zaručeně bezchybné: reálné fotografie byly rozpoznány,
  ale některé formulace polohy/emoce vyžadují kontrolu. Ve finálním promptu je navíc
  pokyn vynechávat nejisté detaily, estetické soudy a výplň pro dosažení délky.
- Při opětovném vývoji vycházet ze zdrojů, nepřepisovat ručně zabalené `_internal/ui`.
- Bez code signing. Modely a uživatelská data přežijí odinstalaci.
- Síťové stahování je záměrně explicitní akce v setupu; nespouštět souběžně
  instalační CLI a GUI nad stejným profilem.

## Reprodukce buildu

`scripts/build.ps1` provede testy, sběr licencí, PyInstaller, Inno Setup,
portable ZIP a SHA-256 součty. Úplné závislosti jsou v `requirements-lock.txt`.
Žádný vzdálený Git repozitář nebyl nastaven ani nebyl proveden push.
