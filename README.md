# Caption Studio 0.1.6

Samostatný lokální Windows nástroj pro přípravu obrazových datasetů pro LoRA.
Nastavení popisku zadáte jednou pro celou dávku. Výsledky se ukládají jako
`obrázek.txt` (Normal) nebo `obrázek.json` (BRIA FIBO) vedle obrázku v UTF-8 bez BOM.

## Instalace a první spuštění

1. Spusťte `Caption-Studio-Setup-0.1.6-Windows-x64.exe`. Instalace je pro aktuálního
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

Číslo právě běžící verze je viditelné v záhlaví vedle názvu Caption Studio a v titulku
desktopového okna.

### Připojení k již běžícímu lokálnímu modelu

V **Nastavení → Lokálně** klikněte na **Najít lokální servery**. Vyhledávání zkusí
modelové API na běžných loopback adresách: porty 11434 (Ollama), 1234 (LM Studio),
8080 (llama.cpp), 8000/8888 (Unsloth a další servery) a 8091 (Caption Studio).
Kontroluje také ručně zadanou lokální adresu. Popisky aplikací jsou vodítka podle
obvyklého portu, nikoli zaručená identifikace procesu. Hledání jen čte seznam modelů;
žádný server ani model nestahuje, nespouští nebo nepřepíná.

Vyberte nalezený server, poté ID modelu s podporou obrázků. Pokud server vyžaduje
klíč, vložte jeho **lokální API klíč** a použijte **Načíst modely**. Klíč se ukládá
šifrovaně a odděleně pro každou přesnou adresu serveru, nezávisle na cloudových klíčích.
Volbu potvrďte přes **Uložit a pokračovat**. Prázdný seznam znamená, že je třeba
nejprve zpřístupnit model v jeho původní aplikaci. Seznam modelů sám neověřuje vision.

Pro vlastní port zvolte **Existující lokální server** a zadejte jeho základní API
adresu (např. `http://127.0.0.1:1234/v1`). Původní aplikace musí server udržovat
spuštěný; Caption Studio externí proces neukončuje. Používá jeho standardní obrazové
Chat Completions API a respektuje serverové nastavení uvažování. U rozpoznaného llama.cpp s podporou enable_thinking aplikace vypne uvažování pouze
v captionovacím požadavku. Nastavení původního serveru se nepřepisuje.

Volba **Vlastní prostředí Caption Studio** nadále používá vlastní stažení, spuštění
a správu Qwenu. Mezi těmito dvěma způsoby připojení lze přepínat. Přímé připojení
k souborům GGUF ani prohledávání disků součástí této funkce není.

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

### Co má LoRA převzít a co chcete měnit promptem

U identity, vlasů, oblečení, doplňků, pózy, výrazu, pozadí, světla, kompozice
a stylu jsou dvě přímé volby:

- **Učit s LoRA:** tyto detaily se do popisku nezahrnou. Cílem je podpořit jejich
  spojení s označením subjektu/triggerem a s vlivem naučené LoRA.
- **Měnit promptem:** viditelné detaily se výslovně popíšou, aby měly samostatné
  textové podmínění a daly se později měnit zadáním.

Příklad postavy: identita **Učit s LoRA**, oblečení/účes/póza/pozadí **Měnit promptem**.
Popis obsahuje trigger a měnitelné vlastnosti konkrétního snímku, ne popis obličeje.
Tlačítko doporučeného rozdělení nastaví pro postavu/objekt učení identity, pro
styl učení stylu; ostatní atributy ponechá popisované. Pouhé přepnutí typu datasetu
vaše jednotlivé volby nepřepisuje.

Nejde o masku tréninkového lossu ani příkaz zmrazit váhy. LoRA se stále učí z celých
obrázků. Popisek nemůže zakázat naučení pozadí nebo garantovat změnu oblečení;
variabilní vlastnosti musí být různorodé i ve vstupních obrázcích. Vynechání rysu
také samo o sobě nezaručí jeho správné naučení. Popisovací model dostává přesnou
politiku pro každý atribut, nadřazenou obecnému presetu a volným doplňujícím pokynům.
Výstup stále vyžaduje vizuální kontrolu, zejména volné textové části JSON.

Staré nastavení „Vynechat stálé rysy identity“ se převede na **Identita → Učit s LoRA**.
Staré vypnuté zahrnutí osvětlení/kompozice se převede na jejich vynechání. Nové
nastavení používá přímo seznam atributů, které se mají spojit s LoRA.

### Normal / BRIA JSON

**Normal** zachovává popis nebo tagy, cílový počet slov a `.txt` soubory.
**BRIA JSON (FIBO)** vytváří strukturu podle veřejného BRIA `ImageAnalysis`:
`short_description`, `objects`, `background_setting`, `lighting`, `aesthetics`,
`photographic_characteristics`, `style_medium`, `text_render`, `context`, `artistic_style`.
Klíče jsou anglické, jazyk popisných hodnot určuje zvolený jazyk. Trigger se přidá
do `short_description`, nikoli před otevírací složenou závorku.

JSON prochází parsováním a kontrolou povolených polí i jejich typů. Neplatný
výstup se automaticky opravuje. Pokud oprava nepomůže, zůstane jako opravitelný návrh. Při ručním
uložení se struktura kontroluje znovu. Povinné řetězce pro vynechané atributy
mohou být prázdné; upstream FIBO normalizátor prázdné hodnoty odstraňuje.
BRIA nevyužívá tagový formát ani celkový cílový počet slov. Aplikace neposílá
žádný max_tokens ani jiný strop délky generované odpovědi. Neúplný JSON se pokusí
automaticky doplnit; při neúspěchu zůstane celý přijatý návrh ke kontrole.

JSON se ukládá jako `.json`, což rozpoznává skener projektu **LORA Train** jako
FIBO. Jeho vlastní FIBO trénovací backend zatím není dokončený; vytvořený sidecar
neznamená, že už lze FIBO trénink spustit. Oficiální BRIA trainer navíc používá
`metadata.csv` s JSON řetězcem ve sloupci caption; tento export není součástí aplikace.

Zdroje formátu: [BRIA ImageAnalysis](https://github.com/Bria-AI/FIBO/blob/main/src/fibo_inference/vlm/gemini_api.py),
[FIBO fine-tuning](https://github.com/Bria-AI/FIBO/blob/main/src/fine_tuning/README.md),
[normalizace caption](https://github.com/Bria-AI/FIBO/blob/main/src/fibo_inference/parse_caption.py).

### Měkký cíl délky a zachování odpovědí

V Normal režimu je počet slov pouze orientační. Aplikace nepředává modelu žádný
limit výstupních tokenů; staré uložené max_tokens ignoruje a při uložení nastavení
je odstraní. Ani přijaté či ručně ukládané popisky neořezává podle počtu znaků.

Hotový popisek do **120 % požadovaného počtu slov** (včetně triggeru) ponechá.
Při překročení požádá stejný model o zkrácení stejného textu, bez další analýzy
obrázku. Slova počítá aplikace. Pokud model ani po dvou pokusech nepřipraví kratší
použitelnou verzi, zachová celou nejkratší dokončenou odpověď s informační poznámkou.
Delší text není chyba a nikdy se mechanicky neustřihne.

Podezřelé nedokončené věty se automaticky doplňují i tehdy, když API hlásí stop.
Samotný finish_reason=length už nezpůsobí selhání: je-li text dokončený, použije se.
Pokud nedokončený text nejde opravit, dostane stav **Ke kontrole**, zůstane jako
návrh a nepřepíše existující popisek. Skutečně prázdná odpověď, odmítnutí služby,
chyba spojení nebo chyba souboru se stále zobrazí pravdivě. Detekce dokončení je
heuristika, nikoli záruka jazykové bezchybnosti.

U obrázku je **Odpovědi modelu** s původním textem i dalšími verzemi. Vybranou verzi
lze vrátit do editoru. Při zastavení během zkracování se již přijatá odpověď zachová
jako návrh. Při práci vidíte, zda aplikace popisuje, zkracuje nebo dokončuje text.
Diagnostika v `%LOCALAPPDATA%\CaptionStudio\logs\generation.jsonl` zaznamenává fázi,
ukončení poskytovatele a počty slov/tokenů. Nezapisuje obrázky, texty popisků,
prompty ani API klíče; vlastní odpovědi jsou v lokální pracovní relaci.

Při výpadku modelového serveru, připojení nebo problému s přístupem se dávka
pozastaví. Neoznačí všechny zbývající obrázky jako vadné. Po obnovení připojení
tlačítko **Pokračovat** zpracuje jen dosud nezpracované položky; hotové neopakuje.

### Zpracování

1. **Otevřít složku** nebo **Vybrat obrázky**; volitelně zahrňte podsložky nebo
   přidávejte k současné sadě. Tlačítko **Cesta…** přijímá přímo cestu ke složce.
   Výběr složky přímo v aplikaci zobrazuje náhledy obrázků, jejich počet a podsložky.
   Vlevo je rozbalovací strom automaticky otevřený k aktuálnímu adresáři.
   Šipka u uzlu rozbaluje podsložky, kliknutí na název složku otevře.
   Tlačítka **Zpět**, **Vpřed**, **O složku výš**, **Domů** a **Obnovit** doplňuje
   klikací cesta po jednotlivých složkách. Zkratky: Alt+←/→ historie, Alt+↑ rodič,
   Ctrl+L zadání cesty, F5 obnova. Ve stromu fungují kurzorové šipky a Enter.
   Chybná cesta zachová otevřenou složku i historii. Výběr potvrďte tlačítkem
   **Použít tuto složku**. Větší adresáře mají náhledy rozdělené po 80 obrázcích.
2. Zvolte zaměření (obecné / postava / objekt / styl), formát (souvislý popis / tagy),
   jazyk, cílovou délku a volitelné trigger slovo, označení subjektu a vlastní pokyny.
   Trigger se přidává k výstupu automaticky. Cílová délka je pokyn modelu, nikoli tvrdý limit.
3. Zaškrtněte požadované obrázky. **Vybrat vše** vybírá všechny obrázky odpovídající
   aktuálnímu filtru, včetně dalších stránek. Otevření sady standardně vybere vše.
4. Klikněte na **Vytvořit popisky**. Dávka běží postupně po jednom obrázku.
5. Kliknutím na obrázek otevřete náhled a popisek. Text upravte a uložte tlačítkem
   nebo Ctrl+S. **Znovu** regeneruje pouze otevřený obrázek a dovolí přepsat jeho popisek.

**Přeskočit existující popisky** je ve výchozím stavu zapnuté a platí pro `.txt` i
`.json`, i pokud je zvolený jiný výstupní formát. Pro převod použijte **Znovu**
nebo přeskočení vypněte. Před změnou se vytvoří kopie původních
bajtů v `.caption-backups`. Při vypnutém **Automaticky ukládat popisky** výsledky
zůstávají jako návrhy v aplikaci; uložte je jednotlivě po kontrole. Návrhy a otevřená
sada přežijí restart, ale otevření nové sady bez přidání nahradí předchozí pracovní seznam.

Po úspěšném uložení nového formátu se původní opačný sidecar přesune do zálohy,
aby nezůstaly soupeřící `.txt` a `.json` (LoRA Studio upřednostňuje `.txt`).
Při generování pouhého návrhu se původní soubor ponechá až do ručního uložení.
Editor vždy ukazuje příponu právě upravovaného popisku; samotná změna globálního
formátu nepřepisuje již vytvořený obsah. Změny souborů mimo aplikaci zablokují zápis.

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
