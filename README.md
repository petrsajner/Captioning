# Caption Studio 0.1.1

Samostatný lokální Windows nástroj pro přípravu obrazových datasetů pro LoRA.
Nastavení popisku zadáte jednou pro celou dávku. Výsledky se ukládají jako
`obrázek.txt` vedle `obrázek.jpg`, `obrázek.png` apod. v UTF-8 bez BOM.

## Instalace a první spuštění

1. Spusťte `Caption-Studio-Setup-0.1.1-Windows-x64.exe`. Instalace je pro aktuálního
   uživatele, bez správce. Aplikace obsahuje vlastní Python a knihovny; nepotřebuje
   předinstalovaný Python, Node.js, Marvin, CUDA Toolkit ani jiné AI aplikace.
2. Spusťte **Caption Studio** ze Start menu. Průvodce nabídne lokální nebo cloudový režim.
3. **Lokálně:** vyberte model a výpočetní backend, klikněte na **Stáhnout prostředí a model**.
   Aplikace stáhne vlastní llama.cpp, potřebné knihovny, model a obrazový projektor.
   Zobrazí průběh; přerušené stahování lze obnovit. Soubory se ověřují přes SHA-256.
4. **Cloud:** vyberte poskytovatele, vložte jeho API klíč a přesné ID modelu, který
   přijímá obrázky. Tlačítko **Načíst dostupné modely** načte seznam. Vyberte vision
   model; samotná přítomnost modelu v seznamu neznamená, že podporuje obrázky.
5. Uložte nastavení. V lokálním režimu se připravený model spustí automaticky při
   první dávce. Tlačítko **Uvolnit GPU** jej zastaví. Zavření aplikace zastaví její model.

Windows 10/11 x64; desktopové okno vyžaduje Microsoft Edge WebView2 Runtime,
který je na běžných Windows přítomen. Při jeho absenci se otevře výchozí prohlížeč.
V prohlížečovém režimu zůstává proces aplikace spuštěný i po zavření záložky;
pro kontrolovatelné ukončení spusťte `CaptionStudio.exe --browser` z terminálu a použijte Ctrl+C.

**Portable varianta:** rozbalte celý ZIP a spusťte `CaptionStudio.exe`.
Složku `_internal` ponechte u EXE. I tato varianta používá vlastní Python;
nastavení a modely standardně ukládá do uživatelské složky níže.

### Lokální modely a místo

Všechny profily používají obrazový Qwen3.8-27B. Čísla VRAM jsou orientační pro
kontext 8 192 tokenů; závisí i na obsazení GPU, ovladači a velikosti obrázků.

| Profil | Váhy | Orientační VRAM | Poznámka |
|---|---:|---:|---|
| IQ3 | 12,0 GB | 16 GB | Výraznější kvantizace, nižší přesnost |
| Q4 | 16,5 GB | 24 GB | Výchozí profil |
| Q5 | 19,8 GB | 32 GB | Vyšší přesnost vah |

Navíc je potřeba 0,93 GB pro obrazový projektor a asi 2 GB rezervy pro prostředí
a rozbalování. CUDA 13.3 vyžaduje kompatibilní aktuální ovladač NVIDIA. Vulkan
je alternativou pro AMD/Intel/NVIDIA; CPU funguje s dostatkem RAM, ale je pomalé.
Vulkan a CPU profily nejsou v této verzi ověřeny na konkrétním hardwaru.
Cloudový režim nepotřebuje stažení žádného z těchto velkých souborů.

## Příprava sady

1. **Otevřít složku** nebo **Vybrat obrázky**; volitelně zahrňte podsložky nebo
   přidávejte k současné sadě. Tlačítko **Cesta…** přijímá přímo cestu ke složce.
   Výběr složky přímo v aplikaci zobrazuje náhledy obrázků, jejich počet a podsložky.
   Složku otevřete kliknutím, nahoru se vrátíte šipkou; výběr potvrďte tlačítkem
   **Použít tuto složku**. Větší adresáře mají náhledy rozdělené po 80 obrázcích.
2. Zvolte zaměření (obecné / postava / objekt / styl), formát (souvislý popis / tagy),
   jazyk, cílovou délku a volitelné trigger slovo, označení subjektu a vlastní pokyny.
   Trigger se přidává k výstupu automaticky. Cílová délka je pokyn modelu, nikoli tvrdý limit.
3. Zaškrtněte požadované obrázky. **Vybrat vše** vybírá všechny obrázky odpovídající
   aktuálnímu filtru, včetně dalších stránek. Otevření sady standardně vybere vše.
4. Klikněte na **Vytvořit popisky**. Dávka běží postupně po jednom obrázku.
5. Kliknutím na obrázek otevřete náhled a popisek. Text upravte a uložte tlačítkem
   nebo Ctrl+S. **Znovu** regeneruje pouze otevřený obrázek a dovolí přepsat jeho popisek.

**Přeskočit existující popisky** je ve výchozím stavu zapnuté. Vypnutím dovolíte
regenerovat a přepsat i existující `.txt`; před změnou se vytvoří kopie původních
bajtů v `.caption-backups`. Při vypnutém **Automaticky ukládat .txt** výsledky
zůstávají jako návrhy v aplikaci; uložte je jednotlivě po kontrole. Návrhy a otevřená
sada přežijí restart, ale otevření nové sady bez přidání nahradí předchozí pracovní seznam.

Zastavení zruší čekající analýzu a další obrázky; už uložené `.txt` zůstanou zachované.
U cloudového API zrušení místního požadavku nezaručuje zastavení účtování u poskytovatele.
Po chybě pokračuje dávka dalším obrázkem. Chybné obrázky lze vyfiltrovat a spustit znovu.
Po pádu aplikace lze znovu spustit dávku s přeskočením existujících `.txt`.

## Ochrana souborů a soukromí

- Originály se nepřejmenovávají, neupravují ani nekopírují do pracovního datasetu.
  Náhled a vstup pro model vznikají v paměti, se správnou EXIF orientací a bez metadat.
  Průhlednost se pro analýzu skládá na bílou. Vícesnímkové obrázky jsou odmítnuty.
- `foto.jpg` a `foto.png` v téže složce jsou kolize: sdílely by `foto.txt`.
  Aplikace je označí a nezapíše k nim popisek, dokud je uživatel nepřejmenuje.
- Změna `.txt` mimo aplikaci mezi načtením a uložením zablokuje přepsání.
  Načtěte sadu znovu, aby se externí úprava stala novým výchozím stavem.
- Lokální inference komunikuje jen s localhostem. Instalace potřebuje internet.
  Cloudový režim odesílá zmenšenou kopii vybraného obrázku a zadání vybranému API.
- API klíče jsou v místním souboru chráněné Windows DPAPI a oddělené podle adresy API.
  Nezobrazují se zpět v rozhraní a nesdílejí se mezi poskytovateli.
- Webové rozhraní naslouchá jen na 127.0.0.1 a vyžaduje vlastní relaci; není přístupné z LAN.
- U modelových popisů je stále potřeba vizuální kontrola. Požadavky v promptu samy
  nezaručí správnost každého detailu. Aplikace není nástroj pro samotný trénink LoRA.

## Umístění dat

`%LOCALAPPDATA%\CaptionStudio\`

- `settings.json`: globální nastavení bez tajných klíčů
- `keys.json`: šifrované klíče
- `session.json`: cesty a popisky otevřené sady
- `runtime/models`: vlastní stažené váhy a obrazový projektor
- `runtime/llama-b10821-*`: vlastní inference prostředí
- `runtime/model.log`: diagnostika spuštění a inference modelu (může obsahovat lokální zadání)

Instalace nečte a nepoužívá složku Marvina. Modely, nastavení i uživatelské
datasety se při odinstalaci záměrně nemažou. Pro oddělené testovací prostředí lze
nastavit `CAPTION_STUDIO_DATA_DIR` před spuštěním aplikace.

## Vývoj

Pro spuštění ze zdrojů: Python 3.11 x64 a `run.bat`; vytvoří projektovou `.venv`
a nainstaluje závislosti. Testy: `.venv\Scripts\python -m pytest -q`.
Vývojové nástroje: `pip install pytest==9.1.1 pyinstaller==6.22.2` v projektové `.venv`.
Sestavení: `powershell -ExecutionPolicy Bypass -File scripts\build.ps1` (Inno Setup 6).
`requirements-lock.txt` zaznamenává úplné prostředí ověřeného Windows buildu.

`setup_local.py --profile q4 --backend cuda` umožňuje provést stejné stažení
z příkazové řádky. Nespouštějte jej souběžně s instalací uvnitř aplikace.

Architektura: `app.py` (desktop a životní cyklus), `captioning/api.py` (lokální API),
`service.py` (dataset a dávky), `provider.py` (obrazové API), `runtime.py` (stažení
a správa vlastního modelu), `storage.py` (bezpečné zápisy a klíče), `ui/` (rozhraní).

Referenční inspirace pro společné volby popisku: [JoyCaption Alpha Two](https://huggingface.co/spaces/fancyfeast/joy-caption-alpha-two).
Inference této aplikace používá [Qwen3.8 GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
přes [llama.cpp](https://github.com/ggml-org/llama.cpp); nejedná se o zabalený model JoyCaption.
