# Dag 2 – ETL: från rådata till databas

**Mål:** en SQLite-databas med 9 742 filmer, 100 836 betyg och riktig metadata från TMDB. I slutet av dagen kan du ställa frågor till din egen databas med SQL.

**Tid:** 1,5–2 timmar, varav ~15 minuter är väntan på TMDB.

**Innan du börjar:** öppna terminalen i VS Code och kontrollera att `(.venv)` syns i prompten. Gör den inte det: `source .venv/bin/activate`.

---

## Vad du faktiskt bygger idag

**ETL** står för Extract, Transform, Load, och är den vanligaste arbetsuppgiften för en dataanalytiker. Nästan all data du någonsin får kommer att vara stökig, spridd över flera källor och i fel format. ETL är arbetet med att göra den användbar.

```
EXTRACT     hämta rådata          (zip från MovieLens, JSON från TMDB)
TRANSFORM   städa och strukturera (bryt ut årtal, dela genrer, hantera nollor)
LOAD        skriv till databasen  (SQLite med primärnycklar och index)
```

Att du kan säga "jag har byggt en ETL-pipeline" och faktiskt förklara vad du gjorde är exakt vad som efterfrågas i annonser för BI- och dataanalytikerroller.

**Datakällorna:**

| Källa | Ger oss | Storlek |
|---|---|---|
| MovieLens (ml-latest-small) | 100 836 betyg från 610 användare på 9 742 filmer | ~1 MB |
| TMDB API | Synopsis, budget, intäkter, speltid, publikbetyg | ~2 000 anrop |

> Det finns en MovieLens-version med 25 miljoner betyg. Vi använder den lilla: 1 MB istället för 1 GB, allt går sekunder istället för minuter, och du lär dig inte en enda ny sak av den stora. Skalar du upp senare är det en enda ändrad URL.

---

## Steg 1 – Kör MovieLens-inläsningen

```bash
python src/02_load_movielens.py
```

Det tar ungefär tio sekunder. Du ska se fyra faser skrivas ut: EXTRACT, TRANSFORM, LOAD, KONTROLL. Sista raden ska vara en topplista med de mest betygsatta filmerna — *Forrest Gump*, *The Shawshank Redemption* och *Pulp Fiction* i någon ordning.

Fick du fel istället? Hoppa till felsökningstabellen längst ner.

---

## Steg 2 – Förstå vad som hände

Det här steget är viktigare än att köra kommandot. **Öppna `src/02_load_movielens.py` i VS Code och läs igenom den** — den är skriven för att läsas, inte bara köras. Här är de tre besluten som är värda att förstå.

### Årtalet satt fast i titeln

MovieLens lagrar titlar så här:

```
Toy Story (1995)
City of Lost Children, The (Cité des enfants perdus, La) (1995)
Babylon 5                                    ← inget årtal alls
```

Årtalet är inbakat i texten. Vill du fråga "vilka filmer gjordes på 90-talet?" går det inte — du kan inte jämföra en textsträng med `> 1990`. Så vi bryter ut det:

```python
df["year"] = df["title"].str.extract(r"\((\d{4})\)\s*$")[0]
```

Mönstret `\((\d{4})\)\s*$` betyder: en parentes, fyra siffror, en parentes, i slutet av strängen. Just `$` är avgörande — utan den skulle den andra titeln ovan kunna matcha på fel ställe.

Filmer utan årtal får `NULL`. **Vi hittar inte på ett värde.** Ett påhittat årtal är värre än inget årtal, eftersom det tystnar problemet istället för att visa det.

### Genrer i en enda sträng

```
Adventure|Animation|Children|Comedy|Fantasy
```

Detta är oanvändbart för analys. Vill du veta snittbetyget för animerade filmer måste du söka efter delsträngar, vilket är både långsamt och opålitligt. Så vi gör om det till en **kopplingstabell** med en rad per kombination:

| movieId | genre |
|---|---|
| 1 | Adventure |
| 1 | Animation |
| 1 | Children |

Det heter **normalisering** och är själva grundidén i relationsdatabaser. Efteråt är frågan en enkel `WHERE genre = 'Animation'`.

Detta är också precis den sortens modelleringsbeslut du kommer att få frågor om i en intervju för en BI-roll. Att du kan förklara varför en kopplingstabell är bättre än en kommaseparerad kolumn väger mer än att du kan syntaxen.

### Primärnycklar, foreign keys och index

Titta på `SCHEMA`-variabeln i skriptet:

```sql
CREATE TABLE ratings (
    userId    INTEGER NOT NULL,
    movieId   INTEGER NOT NULL,
    rating    REAL    NOT NULL,
    FOREIGN KEY (movieId) REFERENCES movies(movieId)
);
```

Tre saker som gör detta till en riktig databas och inte bara en samling tabeller:

- **PRIMARY KEY** — garanterar att `movieId` är unik i `movies`. Databasen vägrar spara en dubblett.
- **FOREIGN KEY** — garanterar att varje betyg pekar på en film som existerar. Utan detta kan du få betyg på film 99999 som aldrig funnits, och det upptäcker du först när en rapport ser fel ut.
- **INDEX** — gör `JOIN` och `WHERE` dramatiskt snabbare. Utan index måste databasen läsa varenda rad; med index hoppar den direkt till rätt ställe. På 100 000 rader märks det, på 100 miljoner är det skillnaden mellan en sekund och en halvtimme.

---

## Steg 3 – Hämta från TMDB

Kontrollera först att nyckeln fungerar:

```bash
python src/01_check_setup.py
```

Står det `✓ TMDB_API_KEY hittad` är du klar. Står det att den inte är satt: du glömde spara `.env` med **Cmd + S**.

Kör sedan hämtningen:

```bash
python src/03_fetch_tmdb.py
```

Det hämtar de **2 000 mest betygsatta filmerna** och tar cirka två minuter. En progressbar visar hur långt det gått.

Vill du testa i mindre skala först, eller hämta allt:

```bash
python src/03_fetch_tmdb.py --limit 50    # snabbtest
python src/03_fetch_tmdb.py --limit 0     # alla ~9 700 filmer, ~10 min
```

**Skriptet är återupptagbart.** Trycker du Ctrl+C, tappar wifi eller stänger locket är det som hämtats sparat. Kör du igen fortsätter det där det slutade. Det är därför du kan avbryta utan att bli nervös — och det är ett mönster du bör bygga in i allt som pratar med externa API:er.

### Tre saker i skriptet som är värda att titta på

**Återupptagbarheten** ligger i SQL-frågan, inte i någon smart Python-logik:

```sql
WHERE m.tmdbId NOT IN (SELECT tmdbId FROM tmdb_movies)
  AND m.tmdbId NOT IN (SELECT tmdbId FROM tmdb_failures)
```

Vi frågar efter det som *saknas*. Har vi redan filmen kommer den inte med i listan.

**Exponential backoff** — om TMDB svarar `429 Too Many Requests` väntar skriptet och försöker igen, med dubbelt så lång väntetid varje gång. Ett skript som bara kraschar vid 429 är ett skript du inte kan lita på.

**Noll är inte samma sak som okänt.** TMDB skriver `budget: 0` när de inte vet budgeten. Låter du det stå kvar som 0 och räknar snittbudget får du ett kraftigt fel svar, eftersom hundratals nollor drar ner snittet. Vi gör om 0 till `NULL`, och då hoppar SQL:s `AVG()` över dem automatiskt.

Den sista är den sortens detalj som skiljer en analys som stämmer från en som ser rimlig ut men är fel. Håll ögonen öppna för den i all data du någonsin får.

---

## Steg 4 – Titta i databasen

Installerade du **SQLite Viewer** på dag 1 kan du klicka på `data/film.db` i VS Codes filträd och bläddra i tabellerna direkt. Gör det — att se datan med egna ögon fångar fel som ingen utskrift avslöjar.

Du ska ha fem tabeller:

| Tabell | Innehåll |
|---|---|
| `movies` | 9 742 filmer med titel, år, imdbId, tmdbId |
| `ratings` | 100 836 betyg |
| `movie_genres` | ~22 000 film-genre-kopplingar |
| `tmdb_movies` | ~2 000 filmer med synopsis, budget, intäkter |
| `tmdb_failures` | Filmer som inte kunde hämtas (oftast borttagna ur TMDB) |

---

## Steg 5 – Skriv egna SQL-frågor

Nu blir det din tur. Detta är dagens viktigaste övning — det är här SQL går från lektion till verktyg.

Öppna en SQL-prompt mot din databas:

```bash
sqlite3 data/film.db
```

Ställ in läsbar utskrift (klistra in båda raderna):

```sql
.mode column
.headers on
```

Testa att det fungerar:

```sql
SELECT title, year FROM movies LIMIT 5;
```

> Semikolon i slutet är obligatoriskt — utan det tror sqlite3 att frågan fortsätter på nästa rad. Skriv `.quit` för att gå ur.

### Övningar

Försök själv innan du tittar på facit. Du klarar fler än du tror.

**1.** Hur många filmer har fler än 100 betyg?

**2.** Vilka fem genrer har högst snittbetyg? Kräver en `JOIN` mellan tre tabeller och en `GROUP BY`.

**3.** Vilket årtionde har flest filmer i datasetet? Tips: `(year / 10) * 10` avrundar nedåt till närmaste tiotal.

**4.** Vilken film har högst intäkt i förhållande till sin budget? Kom ihåg att filtrera bort rader där budget är `NULL`.

**5.** Finns det filmer där MovieLens-användarna och TMDB:s publik är oense? Jämför `AVG(r.rating) * 2` (MovieLens är 0–5, TMDB 0–10) med `t.vote_average`. Kräver minst 50 betyg för att vara meningsfullt.

Övning 5 är den intressanta — den är i praktiken en förhandsvisning av en av dashboardens huvudfrågor på dag 6.

<details>
<summary><b>Facit</b> – öppna först när du försökt</summary>

**1.**
```sql
SELECT COUNT(*) FROM (
    SELECT movieId FROM ratings GROUP BY movieId HAVING COUNT(*) > 100
);
```

**2.**
```sql
SELECT   g.genre,
         COUNT(r.rating)         AS antal_betyg,
         ROUND(AVG(r.rating), 3) AS snitt
FROM     movie_genres AS g
JOIN     ratings      AS r ON r.movieId = g.movieId
GROUP BY g.genre
HAVING   COUNT(r.rating) > 500
ORDER BY snitt DESC
LIMIT 5;
```

`HAVING` filtrerar *efter* grupperingen, `WHERE` filtrerar *före*. Utan `HAVING` toppas listan av nischgenrer med tre betyg.

**3.**
```sql
SELECT   (year / 10) * 10 AS artionde, COUNT(*) AS antal
FROM     movies
WHERE    year IS NOT NULL
GROUP BY artionde
ORDER BY antal DESC;
```

**4.**
```sql
SELECT   m.title, t.budget, t.revenue,
         ROUND(CAST(t.revenue AS REAL) / t.budget, 1) AS multipel
FROM     tmdb_movies AS t
JOIN     movies      AS m ON m.movieId = t.movieId
WHERE    t.budget IS NOT NULL AND t.revenue IS NOT NULL
  AND    t.budget > 100000
ORDER BY multipel DESC
LIMIT 10;
```

`CAST(... AS REAL)` behövs eftersom två heltal dividerade ger heltal i SQLite — utan den blir svaret avrundat till 13 istället för 13,1. Villkoret `budget > 100000` sållar bort mikrobudgetfilmer som annars ger absurda multiplar.

**5.**
```sql
SELECT   m.title,
         ROUND(AVG(r.rating) * 2, 2) AS movielens,
         t.vote_average              AS tmdb,
         ROUND(AVG(r.rating) * 2 - t.vote_average, 2) AS skillnad
FROM     movies      AS m
JOIN     ratings     AS r ON r.movieId = m.movieId
JOIN     tmdb_movies AS t ON t.movieId = m.movieId
WHERE    t.vote_average IS NOT NULL
GROUP BY m.movieId
HAVING   COUNT(r.rating) >= 50
ORDER BY skillnad DESC
LIMIT 10;
```

</details>

---

## Steg 6 – Committa

```bash
git add .
git commit -m "Dag 2: ETL-pipeline för MovieLens och TMDB"
git push
```

Kontrollera att databasen **inte** följde med:

```bash
git status --ignored | grep -E "film.db|raw"
```

`data/film.db` och `data/raw/` ska stå som ignorerade. **Datafiler hör inte hemma i Git** — de är stora, ändras vid varje körning, och den som klonar ditt repo ska kunna återskapa dem genom att köra dina skript. Att repot innehåller *koden som producerar* datan snarare än datan själv är en medveten designprincip, inte en begränsning.

---

## Klar med dag 2

Du har nu:

- En ETL-pipeline i två steg, körbar från grunden med två kommandon
- Ett normaliserat databasschema med primärnycklar, foreign keys och index
- ~2 000 filmer med synopsis — råvaran för AI-lagret på dag 4
- Erfarenhet av verkliga dataproblem: årtal i textfält, rör-separerade listor, nollor som betyder okänt

**Dag 3:** vi bygger SQL-vyer som gör de tunga frågorna till enrads-anrop, och förbereder datamodellen så att Power BI kan läsa den direkt.

---

## Felsökning

| Felmeddelande | Orsak och lösning |
|---|---|
| `ModuleNotFoundError: No module named 'db'` | Du körde från `src/`-mappen. Kör alltid från projektroten: `python src/02_load_movielens.py` |
| `ModuleNotFoundError: No module named 'pandas'` | Venv inte aktiverad. `source .venv/bin/activate` |
| `Nedladdningen misslyckades` | Ingen internetanslutning, eller GroupLens ligger nere. Skriptet skriver ut instruktioner för manuell nedladdning. |
| `TMDB_API_KEY saknas i .env` | Filen inte sparad. Öppna `.env`, tryck Cmd + S. |
| `401 Unauthorized` | Fel nyckel. Använd **API Read Access Token**, inte "API Key (v3 auth)". |
| `no such table: movies` | Kör `02_load_movielens.py` innan `03_fetch_tmdb.py`. |
| `database is locked` | Du har `data/film.db` öppen i SQLite Viewer. Stäng fliken och kör om. |
| Skriptet verkar hänga | TMDB-hämtningen tar ett par minuter. Rör sig progressbaren alls går det bra. |

Fastnar du: skicka hela felmeddelandet, inte en sammanfattning.
