# Caption Studio — handoff 2026-09-06

## Aktualizace 0.1.5 — záměr captioningu a BRIA FIBO JSON (2026-09-11)

Uživatel požádal nahradit nejasné vynechání identity přímými volbami toho, co má
LoRA převzít a co má zůstat měnitelné promptem. Každý z 10 atributů má Učit s LoRA
(vynechat jeho detaily z captionu) / Měnit promptem (detaily popsat). UI výslovně
vysvětluje, že jde o caption conditioning, nikoli loss masku nebo záruku fixace či
nenaučení. Proměnlivé atributy vyžadují variabilitu datasetu. Ze stejného seznamu
`training.ATTRIBUTES` se skládají ovladače, souhrn a modelové instrukce.
Volné pokyny a preset nesmějí přebít tento plán. Doporučené rozdělení se aplikuje
jen tlačítkem; změna typu datasetu uživatelské volby automaticky neresetuje.
Staré omit_identity/lighting/composition se přečtou při migraci; ukládá se learn_attributes.

Přepínač Normal / BRIA JSON (FIBO). Normal zachovává `.txt`, věty/tagy a cílovou
délku. BRIA používá `.json`, datové typy a názvy podle veřejného BRIA ImageAnalysis
(`src/fibo_inference/vlm/gemini_api.py`), včetně volitelných skóre z fine-tuning
example. Vynechané povinné popisné řetězce jsou prázdné; optional fields se mohou
vynechat. Původní BRIA parser prázdné hodnoty odstraňuje. Trigger jde do
short_description. JSON se validuje při generování i každém uložení; odmítá
neznámá pole, špatné typy, duplicitní klíče a NaN. Modelové instrukce zakazují
únik vynechaných atributů do shrnutí či jiných polí; navíc se odstraní jednoznačně
mapovaná strukturovaná pole. Volné textové popisy pořád vyžadují vizuální kontrolu.

Uživatel jako cílový trainer určil `C:\Users\Petr\Documents\LORA Train`.
Jeho aktuální read-only skener čte TXT před JSON a JSON s short_description/objects
označí fibo_json. Proto při explicitním nahrazení/regenerování aplikace nejprve
uloží validovaný cílový formát a pak druhý sidecar přesune do `.caption-backups`.
Při skip-existing se přeskočí kterýkoliv existující formát, při draft-only se
původní soubor nemění. Fingerprint se kontroluje pro oba soubory. Při chybě
archivace zůstává hlášená chyba; aplikace netvrdí úspěšné dokončení převodu.
Po chybě JSON lze návrh opravit v editoru. Samotná změna globálního výstupu
nemění formát již načteného popisku v editoru; UI ukazuje jeho příponu.

Do LORA Train nebylo zasahováno. FIBO trénovací backend tam zůstává plánovaný.
Ověřen byl jeho skutečný scan_dataset nad naším vytvořeným `.json`: 1 obrázek,
1 fibo_json, 0 chyb. Oficiální BRIA trainer chce metadata.csv; tento export
nebyl požadován pro zdejší trainer a není implementovaný.

Ověření: 42 automatických testů; 7 browser kontrol (volby → souhrn → skutečné
zadání, BRIA ovladače, import JSON, viditelná chyba vadného JSON, uložení a reload).
Živý Gemini test nad veřejným pytorch/hub dog.jpg: learned identity vynechala
barvu/specializovaný vzhled psa, described identity zahrnula bílou barvu, uši,
oči; BRIA JSON respektoval vynechání identity a osvětlení a prošel strukturální
validací. První test s limitem 700 tokenů skončil neúplným výstupem bez zápisu;
další tři testy s limitem 4096 prošly (6,3 / 6,4 / 7,0 s). BRIA vyžaduje alespoň
3072 výstupních tokenů; ostatní modelové parametry se nemění. GPU byla obsazená
jinou prací, která nebyla přerušena. Žádné soukromé datasetové fotografie ani
uživatelské pokyny nebyly použity v cloudovém testu. API klíč byl pouze v paměti.

Pomocné testy: `python -m scripts.check_training_live --live` (placené volání
uživatelem nakonfigurovaného cloudu, jen opt-in), `scripts/check_training_ui.js`.
Výsledky v `output/training-live/report.json`, `output/training-ui-result.txt`,
snímek `output/playwright/training-final.png`. Build `output/build-0.1.5-final.log`.
Test zabaleného EXE zahrnuje i odmítnutí chybného JSON a archivaci konkurenčního TXT.
Verze 0.1.5 byla nainstalována a spuštěna. Instalace zachovala kontrolní součty
uživatelských settings.json a šifrovaného keys.json; samotné staré nastavení se
mapuje v paměti na nové volby a uloží novou podobu až při změně nastavení.
Log instalace `output/install-0.1.5.log`. Cizí tréninkové procesy nebyly zastaveny.

Zdroje: https://github.com/Bria-AI/FIBO/blob/main/src/fibo_inference/vlm/gemini_api.py
https://github.com/Bria-AI/FIBO/blob/main/src/fibo_inference/parse_caption.py
https://github.com/Bria-AI/FIBO/blob/main/src/fine_tuning/README.md

## Aktualizace 0.1.4 — najít lokální servery a viditelná verze (2026-09-08)

Uživatel schválil pouze připojení k existujícím lokálním serverům; nepřidávat import
souborů GGUF ani hledání modelových souborů na disku. Zachovat vlastní stažení
modelu pro čisté PC. Uživatel současně potvrdil úspěšné cloudové generování přes
Gemini i OpenRouter; jejich generovací payload ani cloudová konfigurace se nemění.

V lokálním nastavení je Najít lokální servery: read-only GET `/v1/models` na
127.0.0.1, porty 11434, 1234, 8080, 8000, 8888, 8091 + případná vlastní lokální URL.
Nejde o plošný port scan, hledání na LAN ani start/download procesů. Každá kontrola
má celkový limit 3,5 s, neprovádí redirecty a omezuje velikost odpovědi. Názvy
aplikací u výsledků jsou výslovně vodítka podle obvyklého portu. HTTP 401/403 je
kandidát vyžadující klíč, nikoli prokázaná kompatibilita nebo vision podpora.

Nové `local_source` rozlišuje managed/external. Staré nastavení s vlastní URL
migruje na external; standardní adresa na managed. Vlastní prostředí vždy používá
svůj endpoint/alias a původní řízení generování. Externí připojení používá zvolenou
URL/model a standardní parametry, serveru nenutí llama.cpp chat_template_kwargs.
Klíče pro lokální servery jsou oddělené přes `local:<přesná URL>` v DPAPI KeyStore.
Discovery neposílá klíč na jiný endpoint. Žádné API nevrací plaintext klíčů.

Verze je viditelná v hlavní hlavičce vedle názvu, v titulku webové stránky i
v titulku nativního okna. Zdroj je společné `captioning.__version__`.

Ověření: 27 testů včetně migrace starého nastavení, ochrany cloudového klíče,
scope lokálních klíčů, odmítnutí ne-loopback adres, redirectů a neplatných model
listů; dále čistý profil zabaleného EXE. Reálný oddělený Qwen server na 8080
se záměrně zvolenou testovací autentizací: discovery našlo uzamčený server,
UI přijalo testovací klíč, načetlo `qa-qwen-vision` a po uložení vytvořilo 2 UTF-8
sidecary (2,8 s / 3,0 s, 0 chyb). Testovací server měl vypnuté uvažování ve své
vlastní konfiguraci. Ukončení Caption Studio jej ponechalo běžet (health HTTP 200).
Teprve testovací helper jej následně zastavil. Živé Ollama/LM Studio/Unsloth instance
nebyly na tomto PC při testu dostupné; jejich endpoint varianty ověřeny simulací.

Helper `python -m scripts.serve_test_model` je jen opt-in lokální test, není součástí
instalátoru a aplikace ho nevolá. Snímky `output/playwright/local-server-connected.png`
a `local-server-captions.png`; build `output/build-0.1.4.log`. Distribuce 0.1.4 v dist/.
Uživatel výslovně povolil restart a instalaci. Verze 0.1.4 byla nainstalována;
kontrolní součty jeho settings.json a šifrovaného keys.json zůstaly po instalaci
nezměněné. Čistý profil instalovaného EXE prošel ověřením. Log `output/install-0.1.4.log`.

## Aktualizace 0.1.3 — jednotná ikona aplikace (2026-09-08)

Uživatel požádal nahradit výchozí Python ikonu zástupce zeleným C z hlavičky.
Původní `.brand-icon` CSS/HTML bylo vyrenderováno prohlížečem při 12x měřítku
na průhledné pozadí (`ui/brand-icon.png`). Nejde o ořez uživatelského screenshotu.
`scripts/icon_from_logo.py` z tohoto assetu balí ICO s velikostmi
16/20/24/32/40/48/64/128/256 px (`ui/caption-studio.ico`).

Ikona je vložená do PyInstaller EXE, do instalačního EXE a nastavuje se přes
pywebview `start(icon=...)` pro titulkový pruh včetně spuštění ze zdrojů.
Desktop a Start menu mají explicitní IconFilename na instalované ICO;
favicon používá stejný PNG asset. Původní logo v hlavičce se nemění.

Desktop uživatele je přesměrovaný na OneDrive. Existující Caption Studio.lnk
byl nalezen přes systémovou známou složku plochy a jeho původní IconLocation
bylo prázdné (výchozí ikona EXE). První uživatelem hlášené nevytvoření zástupce
nebylo reprodukováno; podle uživatele další instalace zástupce vytvořila.
Nezaměňovat tuto historii s prokázanou příčinou chybějícího loga v EXE.

Distribuce: verze 0.1.3, build `output/build-0.1.3.log`, instalátor a portable ZIP
v `dist/`, kontrolní součty `dist/SHA256SUMS.txt`.

## Aktualizace 0.1.2 — plná navigace výběru složky

Uživatel odmítl omezenou náhradu systémového dialogu: vlevo byly pouze kořeny
disků, nešlo přejít na sousední větev bez nového průchodu celou cestou a malé
tlačítko ↑ nebylo dostatečně zřejmé. Výběr složky nyní obsahuje:

- Strom složek vlevo, načítaný po úrovních; automaticky rozbalená cesta k aktuální
  složce, zvýrazněný výběr, zachování rozbalených vedlejších větví.
- Klikací breadcrumb cestu pro přímý skok na libovolného předka.
- Viditelně popsané Zpět, Vpřed, O složku výš, Domů, Obnovit. Historie se mění
  jen po úspěšném přechodu; chyba cesty zachová předchozí složku a historii.
- Alt+←/→, Alt+↑, Ctrl+L, F5; šipky, Home/End a Enter ve stromu.
- Ochranu proti přepsání nově psané cesty ještě dobíhajícím načítáním.
  Klávesové zkratky fungují i po přerenderování kliknuté breadcrumb položky.

Řadič výběru přesunut z `ui/app.js` do `ui/folder-browser.js`. Backend vrací
breadcrumb segmenty a má samostatné čtení jediné úrovně `/api/folder-tree`.
To nestahuje obrázky, negeneruje popisky ani neprochází rekurzivně celý disk.

Ověření: 21 backend testů a 12 skutečných UI kontrol ve `scripts/check_navigation.js`.
Kontroly zahrnují sourozence, rodiče, breadcrumb předka, historii, větvení historie,
klávesnici ve stromu, disabled rodiče v kořeni, neplatnou cestu bez ztráty kontextu,
zachování rozbalené vedlejší větve při obnově, viditelný JPEG náhled a konečný import.
Výsledek `output/navigation-check-result.txt`; snímek `output/playwright/navigation-final.png`.
Build `output/build-0.1.2-final.log`. Distribuční verze 0.1.2, samostatný instalátor
a portable ZIP v `dist/`. Runtime a inference se touto úpravou nemění.

## Aktualizace 0.1.1 — obrázky při výběru složky

Uživatel hlásil zdánlivě prázdnou složku při výběru datasetu. Příčinou byl
`tkinter.filedialog.askdirectory`, který ukazuje pouze adresáře a skrývá soubory.
Tlačítko Otevřít složku nyní otevírá prohlížeč uvnitř aplikace: náhledy a názvy
obrázků, celkový počet, podsložky, disky, zadání cesty a návrat do nadřazené složky.
Potvrzuje se právě prohlížený adresář, včetně volby rekurze. Náhledy jsou stránkované
po 80; nečitelný obrázek zůstane viditelný s náhradním zobrazením. Samotné prohlížení
nemění dataset ani soubory. Systémový dialog zůstává jen pro výběr jednotlivých souborů.

Nový modul `captioning/folders.py`, autentizované `/api/folders` a `/api/folder-image`,
UI v `ui/app.js`, `ui/index.html`, `ui/folders.css`. Starý výběr adresáře odstraněn.
Ověřeno 19 testy, skutečnými vykreslenými náhledy koček/psa před potvrzením i po
importu, a čistým profilem zabaleného EXE bez vývojových cest. Náhled opravy:
`output/playwright/folder-preview.png`. Build `output/build-0.1.1.log`, instalace
`output/install-0.1.1.log`. Nový instalátor a portable ZIP v `dist/`, SHA v SHA256SUMS.txt.

Níže je původní záznam 0.1.0.

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
