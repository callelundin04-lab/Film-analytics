# Dag 1 – Miljö och grundstruktur

**Mål:** i slutet av dagen har du en fungerande Python-miljö, ett GitHub-repo och ett skript som bekräftar att allt hänger ihop. Ingen filmdata ännu — det är dag 2.

**Tid:** 1–2 timmar. Det mesta är väntan på nedladdningar.

**Du behöver:** en Mac och terminalen. Öppna den med `Cmd + Space` → skriv "Terminal" → Enter.

---

## Steg 0 – Läs det här först

Två saker som gör resten begripligt:

**Terminalen** är ett textgränssnitt till din dator. Du skriver ett kommando, trycker Enter, datorn svarar. Prompten (`$` eller `%`) betyder "jag väntar på dig". När inget händer i flera sekunder betyder det oftast att något arbetar — vänta.

**`cd` byter mapp.** Nästan varje kommando nedan förutsätter att du står i projektmappen. Om något beter sig oväntat, kör `pwd` (print working directory) och kontrollera att du står rätt.

---

## Steg 1 – Kontrollera Python

macOS har Python förinstallerat, men ofta en gammal version.

```bash
python3 --version
```

- **Får du `Python 3.10.x` eller högre?** Bra, hoppa till steg 2.
- **Får du något lägre, eller ett felmeddelande?** Ladda ner senaste versionen från [python.org/downloads](https://www.python.org/downloads/), kör installationsfilen, starta om terminalen och kör kommandot igen.

> Om macOS ber dig installera "Command Line Developer Tools" — säg ja. Det tar några minuter och behövs för Git.

---

## Steg 2 – Installera VS Code

VS Code är där du skriver koden. Ladda ner från [code.visualstudio.com](https://code.visualstudio.com/), dra appen till Program-mappen, öppna den.

Installera sedan tillägget för Python:

1. Klicka på fyrkanterna i vänsterkanten (Extensions), eller `Cmd + Shift + X`
2. Sök på **Python**
3. Installera den från Microsoft (den överst, med flest nedladdningar)

Lägg också till **SQLite Viewer** (av Florian Klampfer) medan du är där — då kan du klicka på din databasfil och se innehållet direkt, vilket blir användbart från dag 2.

---

## Steg 3 – Gå till projektmappen

Mappen ligger redan på din dator, i **`Cowork CV och JOBB`** i din hemmamapp. Gå dit:

```bash
cd ~/"Cowork CV och JOBB"/film-analytics
```

> Citattecknen behövs eftersom mappnamnet innehåller mellanslag. Utan dem tror terminalen att du menar flera olika saker. Detta gäller varje gång du skriver sökvägen.
>
> Tips: skriv `cd ~/Cow` och tryck **Tab** — terminalen fyller i resten åt dig.

Kontrollera att allt finns:

```bash
ls -a
```

Du ska se: `.env`, `.env.example`, `.gitignore`, `DAG1.md`, `README.md`, `requirements.txt`, `data/`, `notebooks/`, `src/`

> `ls -a` visar även filer som börjar med punkt. Sådana filer är dolda som standard i macOS — och två av våra viktigaste börjar med punkt.

Öppna nu mappen i VS Code:

```bash
code .
```

Fungerar inte `code`? Öppna VS Code manuellt → File → Open Folder → välj mappen.

---

## Steg 4 – Skapa en virtuell miljö (venv)

Det här är det enda konceptet i dag 1 som är värt att förstå ordentligt.

Ett **venv** är en isolerad Python-installation som bara gäller detta projekt. Alla paket du installerar hamnar i en mapp inuti projektet istället för på hela systemet. Varför det spelar roll: om projekt A behöver pandas 2.0 och projekt B behöver pandas 1.5 skulle de krocka utan venv. Alla professionella Python-projekt använder detta, och en rekryterare som tittar i ditt repo noterar om det saknas.

Skapa det:

```bash
python3 -m venv .venv
```

Inget syns, men en `.venv`-mapp skapas. Aktivera den:

```bash
source .venv/bin/activate
```

Nu ska prompten börja med `(.venv)`. **Det är signalen att du är inne.**

> **Detta måste göras varje gång du öppnar ett nytt terminalfönster.** Glömmer du det hamnar paketen på fel ställe och skripten klagar. `01_check_setup.py` kontrollerar just detta åt dig.
>
> Vill du gå ur: skriv `deactivate`.

Säg åt VS Code att använda samma miljö: `Cmd + Shift + P` → skriv "Python: Select Interpreter" → välj den som har `.venv` i sökvägen.

---

## Steg 5 – Installera paketen

Med `(.venv)` synligt i prompten:

```bash
pip install -r requirements.txt
```

Detta läser `requirements.txt` och installerar allt på listan. Det tar 1–3 minuter och skriver ut mycket text — normalt. Varningar om "pip version" kan du ignorera.

Vad du just installerade och varför:

| Paket | Vad det gör |
|---|---|
| **pandas** | Tabeller i Python. Din motsvarighet till Excel-blad, men programmerbart. Kommer att bli ditt mest använda verktyg. |
| **requests** | Hämtar data från API:er över internet. |
| **SQLAlchemy** | Låter Python skriva till och läsa från databasen. |
| **python-dotenv** | Läser hemliga nycklar ur `.env` istället för att ha dem i koden. |
| **scikit-learn** | Maskininlärning. Används dag 5. |
| **matplotlib** | Snabba diagram medan vi utvecklar (den polerade versionen blir Power BI). |
| **tqdm** | Progressbar, så du ser att något händer när vi hämtar tusentals filmer. |
| **anthropic** | Anropar Claude från din kod. Används dag 4. |

---

## Steg 6 – Hämta TMDB-nyckel och fyll i `.env`

`.env` är filen där hemligheter bor. Den är gitignorerad och hamnar aldrig på GitHub — det är hela poängen. **Att läcka API-nycklar på GitHub är ett av de vanligaste nybörjarmisstagen**, och det syns i din commit-historik för alltid.

Filen finns redan i mappen med platshållare i. Hämta din TMDB-nyckel (gratis, tar 5 minuter):

1. Skapa konto på [themoviedb.org](https://www.themoviedb.org/signup)
2. Verifiera mejladressen
3. Gå till [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
4. Begär en nyckel → välj **Developer** → syftesbeskrivning: *"Personal educational data analysis project"* → godkänn villkoren
5. Kopiera värdet under **API Read Access Token**

Öppna `.env` i VS Code och byt ut platshållaren:

```
TMDB_API_KEY=eyJhbGciOi...din_riktiga_nyckel
ANTHROPIC_API_KEY=din_anthropic_nyckel_här
```

Anthropic-nyckeln lämnar du som den är — vi ordnar den dag 4.

---

## Steg 7 – Kör kontrollskriptet

Sanningens ögonblick:

```bash
python src/01_check_setup.py
```

Skriptet kontrollerar Python-versionen, att du är i venv, att alla paket finns, att `.env` läses, och skapar en liten SQLite-databas som det kör en SQL-fråga mot och sedan raderar.

**Om allt är grönt** avslutas det med *"Allt fungerar. Du är klar med dag 1"*.

**Om något är rött** listas exakt vad som behöver fixas längst ner. Vanligaste orsaken är att `(.venv)` inte syns i prompten — kör `source .venv/bin/activate` och försök igen. Fastnar du: skicka mig hela utskriften och jag felsöker.

Öppna gärna `src/01_check_setup.py` i VS Code och läs igenom den. Den är rikligt kommenterad, och du kommer att känna igen mönstren senare i veckan. SQL-frågan längst ner i steg 4 är samma `SELECT ... FROM ... WHERE ... ORDER BY` som du gick igenom i din SQL-lektion.

---

## Steg 8 – Git och GitHub

Git sparar snapshots av ditt projekt över tid. GitHub lägger dem online så du kan länka till projektet i ditt CV. Länken är i praktiken hela poängen med detta steg.

Kontrollera att Git finns:

```bash
git --version
```

Saknas det installerar macOS det åt dig när du kör kommandot — godkänn dialogen.

Ställ in vem du är (första gången på en ny dator):

```bash
git config --global user.name "Carl Lundin"
git config --global user.email "callelundin04@gmail.com"
```

Skapa din första commit:

```bash
git init
git add .
git commit -m "Dag 1: projektstruktur och miljökontroll"
```

Kontrollera att `.env` **inte** kom med:

```bash
git status --ignored | grep env
```

`.env` ska stå under *"Ignored files"*. Gör den inte det — stoppa och hör av dig innan du pushar.

Lägg upp det på GitHub:

1. Skapa konto på [github.com](https://github.com) om du inte har ett. **Använd ett användarnamn du vill ha på ditt CV** — `carllundin` slår `xXcarl2004Xx`.
2. Klicka **+** uppe till höger → **New repository**
3. Namn: `film-analytics` (eller något du gillar bättre)
4. Välj **Public**
5. **Kryssa INTE** i "Add a README" eller ".gitignore" — vi har redan filer, och det skapar en konflikt
6. Create repository

GitHub visar nu några kommandon. Kör dessa två (byt ut `DITT-ANVÄNDARNAMN`):

```bash
git remote add origin https://github.com/DITT-ANVÄNDARNAMN/film-analytics.git
git branch -M main
git push -u origin main
```

Ber den om lösenord: GitHub accepterar inte ditt vanliga lösenord. Skapa en **Personal Access Token** under Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token → kryssa i `repo` → kopiera. Använd token som lösenord.

Ladda om din GitHub-sida. Koden ligger där. **Det är nu länken finns som ska stå på ditt CV.**

---

## Klar med dag 1

Du har nu:

- Python 3.10+ och VS Code med Python-stöd
- En isolerad venv med åtta paket
- Projektstruktur med gitignore och hemlighetshantering
- En TMDB-nyckel
- Ett verifierat kontrollskript
- Ett publikt GitHub-repo med din första commit

Det låter oglamoröst, men det här är den vanligaste platsen där hobbyprojekt dör. Att du har venv, `.env` och Git rätt uppsatt från början är något som faktiskt syns för den som granskar repot.

**Dag 2:** vi hämtar MovieLens-datasetet, anropar TMDB för tusentals filmer, städar stökig data och bygger det första riktiga databasschemat.

---

## Om något går fel

| Symptom | Trolig orsak |
|---|---|
| `command not found: python3` | Python inte installerat — se steg 1 |
| `command not found: pip` | Venv inte aktiverat — `source .venv/bin/activate` |
| `No module named pandas` | Paket installerade utanför venv. Aktivera, kör steg 5 igen |
| `permission denied` | Du står utanför din hemmamapp. `cd ~/Documents/film-analytics` |
| `(.venv)` syns inte | Nytt terminalfönster. Aktivera igen — varje gång |
| VS Code hittar inte paketen | Fel interpreter valt — se slutet av steg 4 |

Skicka hela felmeddelandet till mig, inte en sammanfattning. Den exakta texten säger nästan alltid vad som är fel.
