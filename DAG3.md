# Dag 3 – Datamodellering: vyer och stjärnschema

**Mål:** göra om databasen från "så som datan råkade komma till oss" till "så som datan ska användas". I slutet av dagen har du ett stjärnschema, fem analysvyer och 18 automatiska datakvalitetskontroller.

**Tid:** 1–1,5 timmar. Ingen väntan idag — allt körs lokalt på sekunder.

**Förkunskaper:** dag 2 klar, och `(.venv)` synlig i prompten.

---

## Först: en viktig upptäckt om Power BI

**Power BI Desktop finns inte för macOS**, och Microsoft har inga planer på en Mac-version. Det är värt att veta nu snarare än på dag 6.

Vi kör därför **Power BI Service** — webbversionen på `app.powerbi.com`, som fungerar i Safari eller Chrome och är gratis med ett Microsoft-konto. Du laddar upp datan som Excel och bygger rapporten i webbläsaren.

Det innebär en begränsning: **ingen Power Query och ingen avancerad DAX i webbversionen.** Och just därför är dagens arbete extra viktigt — vi gör alla transformationer i SQL istället. Det låter som en nödlösning men är faktiskt den arkitektur som föredras i professionella miljöer: tung logik hör hemma i databasen, inte i rapportverktyget. Är transformationen i SQL kan alla verktyg använda den; är den i Power Query är den inlåst i en enda .pbix-fil.

Så på CV:t blir det inte en ursäkt utan en styrka: *"transformationslogik i SQL-vyer, rapportlagret enbart för visualisering."*

---

## Steg 1 – Kör datamodelleringen

```bash
python src/04_build_views.py
```

Tar ett par sekunder. Du ska se fyra avsnitt: datumdimensionen, stjärnschemat, analysvyerna, och sedan exempel läst ur vyerna — bland annat vilka filmer MovieLens-användarna och TMDB-publiken är mest oense om.

---

## Steg 2 – Vad är en vy?

En **vy** är en sparad SQL-fråga som beter sig som en tabell.

```sql
CREATE VIEW dim_genre AS
SELECT movieId AS movie_key, genre FROM movie_genres;
```

Efter det kan du skriva `SELECT * FROM dim_genre` precis som mot en tabell. Skillnaden:

| | Tabell | Vy |
|---|---|---|
| Lagrar data | Ja | Nej |
| Tar plats på disk | Ja | Nästan ingen |
| Uppdateras när källan ändras | Nej, måste laddas om | Ja, automatiskt |
| Snabbhet vid läsning | Snabb | Kör frågan varje gång |

Poängen är inte att spara plats. Poängen är att **komplexiteten skrivs en gång.**

Tänk på definitionen av "snittbetyg". Skriver du den för hand i tjugo olika frågor kommer några av dem att skilja sig — någon glömmer filtrera bort filmer med tre betyg, någon annan räknar med filmer utan årtal. Då har du två rapporter som visar olika siffror för samma sak, och ingen vet vilken som stämmer. Det är ett av de vanligaste och mest förtroendeskadande problemen i verklig BI-verksamhet.

Ligger definitionen i en vy finns det bara ett svar, och ändrar du definitionen ändras allt samtidigt.

---

## Steg 3 – Stjärnschemat

Det här är dagens viktigaste koncept, och det du sannolikt får frågor om i en intervju för en BI-roll.

```
              dim_date
                  |
   dim_genre — fact_ratings — dim_movie
```

**Faktatabellen** i mitten innehåller mätvärden och nycklar, och har många rader. Här: ett betyg per rad, 100 836 rader.

**Dimensionstabellerna** runt omkring innehåller beskrivningar, och har få rader. Vem, vad, när.

Det avgörande beslutet i all dimensionell modellering är **grovheten** — engelska *grain*: exakt vad representerar en rad i faktatabellen? Här: *en användares betyg på en film vid ett tillfälle.* Kan du inte svara på den frågan om din faktatabell är modellen fel, och alla siffror som kommer ur den blir opålitliga på sätt som är svåra att upptäcka.

**Varför just denna form?** Power BI, Tableau och Looker är alla byggda med antagandet att datan ser ut så här. Ger du dem ett stjärnschema fungerar filtrering, aggregering och tidsjämförelser direkt. Ger du dem en enda bred tabell eller ett trassel av kopplingar får du fel summor och långsamma rapporter.

### Datumdimensionen

Titta på `dim_date` i skriptet. Det är den enda **tabellen** vi skapar idag, inte en vy — eftersom vi genererar rader som inte finns någon annanstans: en rad per dag mellan första och sista betyget, med år, kvartal, månad, veckodag och helgflagga uträknade i förväg.

Två skäl att alltid ha en:

- **Du slipper räkna om.** "Gruppera per kvartal" blir `GROUP BY quarter` istället för uttryck kring `strftime`.
- **Tomma perioder syns.** Fanns inga betyg i mars försvinner mars helt om du grupperar direkt på betygsdatumet. En tidsserie som hoppar över tomma månader ser ut som om ingenting hände — istället för att visa att ingenting hände, vilket ofta är det intressanta.

Den genereras med en **rekursiv CTE**, som är värd att titta närmare på:

```sql
WITH RECURSIVE dagar(d) AS (
    SELECT start_d FROM gränser        -- startvärde
    UNION ALL
    SELECT date(d, '+1 day') FROM dagar   -- refererar sig själv
    WHERE  d < (SELECT slut_d FROM gränser)  -- stoppvillkor
)
```

Den bygger en tabell genom att upprepa sig själv: börja med startdatumet, lägg till en dag, upprepa till stoppvillkoret. Samma idé som en loop, men i SQL. Glömmer du stoppvillkoret kör den för alltid.

---

## Steg 4 – Datakvalitetskontroller

```bash
python src/05_quality_checks.py
```

Du ska få ungefär **15 PASS, 3 WARN, 0 FAIL**.

Varningarna är förväntade och beskriver luckor i källdatan, inte fel i din pipeline: några filmer saknar årtal, några saknar tmdbId, och en del filmer har inga betyg alls. Det är så MovieLens ser ut.

**Får du något FAIL: stanna.** Skriptet skriver ut vad som är fel och avslutar med felkod. Bygg inte vidare på data som inte klarar kontrollerna.

### Varför detta är värt en egen fil

En analys byggd på trasig data ser exakt lika övertygande ut som en analys byggd på korrekt data. Diagrammen blir lika snygga, snitten lika prydliga. Skillnaden märks först när någon fattar ett beslut på fel underlag — och då är det för sent.

Därför testar man data, precis som man testar kod. Varje kontroll formulerar ett påstående och verifierar det. De fyra kategorierna är värda att komma ihåg, för de återkommer i all datakvalitetsarbete:

| Kategori | Frågan den ställer | Exempel härifrån |
|---|---|---|
| Referentiell integritet | Pekar allt på något som finns? | Betyg på en film som inte existerar |
| Unikhet | Finns dubbletter där det inte får finnas? | Samma användare betygsätter samma film två gånger |
| Värdeintervall | Är värdena fysiskt möjliga? | Betyg utanför 0,5–5,0, film från år 1650 |
| Täckning | Hur mycket data har vi faktiskt? | Andel filmer utan synopsis |

Den fjärde är den man oftast glömmer, och den som oftast biter. Att 60 procent av dina filmer saknar budgetdata är inget *fel* — men bygger du en rapport om lönsamhet utan att veta det drar du slutsatser om en fjärdedel av datan och tror att du talar om helheten.

**Att kunna säga "jag byggde in datakvalitetskontroller i pipelinen" är ovanligt hos juniora sökande.** De flesta portfolioprojekt hoppar rakt till visualisering. Nämn detta i intervjun.

---

## Steg 5 – Övningar

Öppna databasen:

```bash
sqlite3 data/film.db
```

```sql
.mode column
.headers on
```

**1.** Titta på vilka vyer som finns:

```sql
SELECT name, type FROM sqlite_master WHERE type IN ('view','table') ORDER BY type, name;
```

**2.** Se hur en vy faktiskt är definierad — nyttigt när du glömt vad något gör:

```sql
SELECT sql FROM sqlite_master WHERE name = 'v_rating_gap';
```

**3.** Vilka fem filmer har högst `revenue_multiple`? Använd `v_movie_stats` och filtrera bort `NULL`.

**4.** Vilken veckodag betygsätts det mest? Kräver en `JOIN` mellan `fact_ratings` och `dim_date`.

**5.** Skapa din **egen vy** som heter `v_min_vy` och visar filmer från 2010-talet med minst 20 betyg, sorterade på snittbetyg. Använd `CREATE VIEW v_min_vy AS ...` och läs sedan från den.

**6.** Ta bort din vy igen: `DROP VIEW v_min_vy;`

Övning 5 är den viktiga — det är först när du skapar en egen vy som det klickar att en vy bara är en namngiven fråga.

<details>
<summary><b>Facit</b></summary>

**3.**
```sql
SELECT   title, budget, revenue, revenue_multiple, avg_rating
FROM     v_movie_stats
WHERE    revenue_multiple IS NOT NULL
ORDER BY revenue_multiple DESC
LIMIT 5;
```

**4.**
```sql
SELECT   d.weekday_name,
         COUNT(*)                AS antal,
         ROUND(AVG(f.rating), 3) AS snitt
FROM     fact_ratings AS f
JOIN     dim_date     AS d ON d.date_key = f.date_key
GROUP BY d.weekday, d.weekday_name
ORDER BY antal DESC;
```

**5.**
```sql
CREATE VIEW v_min_vy AS
SELECT   title, release_year, rating_count, avg_rating
FROM     v_movie_stats
WHERE    decade = 2010 AND rating_count >= 20
ORDER BY avg_rating DESC;

SELECT * FROM v_min_vy LIMIT 10;
```

Lägg märke till att vyn bygger på en annan vy. Det är helt tillåtet och mycket vanligt — man lagerar vyer ovanpå varandra: stjärnschema underst, analysvyer i mitten, rapportspecifika vyer överst.

</details>

Glöm inte `.quit` för att lämna sqlite3.

---

## Steg 6 – Committa

```bash
git add .
git commit -m "Dag 3: stjärnschema, analysvyer och datakvalitetskontroller"
git push
```

---

## Klar med dag 3

Du har nu:

- Ett stjärnschema: `fact_ratings`, `dim_movie`, `dim_genre`, `dim_date`
- Fem analysvyer som paketerar dag 2:s frågor
- En genererad datumdimension med kvartal, månad och veckodag
- 18 automatiska datakvalitetskontroller med tydlig PASS/WARN/FAIL

**Databasen är nu färdig som analysunderlag.** Allt du bygger härefter läser från den.

**Dag 4 – det roliga:** vi låter en LLM läsa varje filmsynopsis och returnera strukturerad data som inte finns i någon databas: tema, ton, tempo, känsloläge. Det blir nya kolumner i `dim_movie`, och därmed nya sätt att skära datan som varken MovieLens eller TMDB kan erbjuda.

Innan dess behöver du en API-nyckel från `console.anthropic.com` med lite krediter på. Kom ihåg att Claude Code-abonnemanget inte räcker — API-anrop från egen kod faktureras separat. Minsta påfyllning är 5 USD och vi kommer att använda under en dollar.

---

## Felsökning

| Felmeddelande | Orsak och lösning |
|---|---|
| `no such table: ratings` | Kör `src/02_load_movielens.py` först |
| `no such table: tmdb_movies` | Kör `src/03_fetch_tmdb.py` först |
| `database is locked` | `data/film.db` är öppen i SQLite Viewer. Stäng fliken |
| `ModuleNotFoundError: No module named 'db'` | Kör från projektroten, inte från `src/` |
| Vyerna finns men är tomma | `v_genre_stats` kräver ≥100 betyg per genre och `v_rating_gap` ≥50 per film. Hämtade du bara ett fåtal filmer från TMDB blir de tomma — kör `python src/03_fetch_tmdb.py` igen |
| `FAIL` på "Rader i fact_ratings ≠ ratings" | Kör `src/04_build_views.py` igen, vyerna är ur synk |
