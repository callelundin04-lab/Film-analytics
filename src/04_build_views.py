"""
04_build_views.py
-----------------
Dag 3: bygger datamodellen — ett stjärnschema plus analysvyer.

Kör med:  python src/04_build_views.py

Fram till nu har databasen speglat hur datan RÅKADE komma till oss: en tabell
per CSV-fil. Det är rätt för inläsning, men fel för analys. Nu bygger vi om
den till hur den ska ANVÄNDAS.

Två begrepp gör hela dagen:

  VY (VIEW)  – en sparad SQL-fråga som beter sig som en tabell. Den lagrar
               ingen data; den kör frågan varje gång du läser från den.
               Ändras underliggande data ändras vyn automatiskt.

  STJÄRNSCHEMA – en faktatabell i mitten (många rader, mätvärden) omgiven av
               dimensionstabeller (få rader, beskrivningar). Det är standarden
               för BI-verktyg, och Power BI förutsätter i praktiken denna form.

           dim_date          dim_movie
                  \\             /
                   fact_ratings
                  /
           dim_genre
"""

import sys

import db

OK = "\033[92m✓\033[0m"


def rubrik(text: str) -> None:
    print(f"\n{'=' * 58}\n  {text}\n{'=' * 58}")


# ===============================================================
# DIMENSIONSTABELL: datum
# ===============================================================
# Denna måste vara en riktig TABELL, inte en vy — vi genererar rader som
# inte finns någon annanstans. Alla BI-verktyg vill ha en datumdimension,
# eftersom den låter dig gruppera på år, kvartal och månad utan att räkna
# om något, och den innehåller även datum där inget hände (viktigt för att
# en tidsserie inte ska hoppa över tomma månader).

DIM_DATE = """
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key    TEXT PRIMARY KEY,   -- 'YYYY-MM-DD'
    year        INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    month_name  TEXT    NOT NULL,
    day         INTEGER NOT NULL,
    weekday     INTEGER NOT NULL,   -- 0 = söndag i SQLite
    weekday_name TEXT   NOT NULL,
    is_weekend  INTEGER NOT NULL
);

-- En rekursiv CTE genererar en rad per dag mellan första och sista betyget.
-- WITH RECURSIVE bygger en tabell genom att upprepa sig själv: börja med
-- startdatumet, lägg till en dag, upprepa till slutdatumet är nått.
INSERT INTO dim_date
WITH RECURSIVE
  gränser AS (
    SELECT MIN(date(timestamp, 'unixepoch')) AS start_d,
           MAX(date(timestamp, 'unixepoch')) AS slut_d
    FROM   ratings
  ),
  dagar(d) AS (
    SELECT start_d FROM gränser
    UNION ALL
    SELECT date(d, '+1 day') FROM dagar
    WHERE  d < (SELECT slut_d FROM gränser)
  )
SELECT
    d,
    CAST(strftime('%Y', d) AS INTEGER),
    (CAST(strftime('%m', d) AS INTEGER) + 2) / 3,
    CAST(strftime('%m', d) AS INTEGER),
    CASE strftime('%m', d)
        WHEN '01' THEN 'januari'   WHEN '02' THEN 'februari'
        WHEN '03' THEN 'mars'      WHEN '04' THEN 'april'
        WHEN '05' THEN 'maj'       WHEN '06' THEN 'juni'
        WHEN '07' THEN 'juli'      WHEN '08' THEN 'augusti'
        WHEN '09' THEN 'september' WHEN '10' THEN 'oktober'
        WHEN '11' THEN 'november'  ELSE 'december'
    END,
    CAST(strftime('%d', d) AS INTEGER),
    CAST(strftime('%w', d) AS INTEGER),
    CASE strftime('%w', d)
        WHEN '0' THEN 'söndag'  WHEN '1' THEN 'måndag'
        WHEN '2' THEN 'tisdag'  WHEN '3' THEN 'onsdag'
        WHEN '4' THEN 'torsdag' WHEN '5' THEN 'fredag'
        ELSE 'lördag'
    END,
    CASE WHEN strftime('%w', d) IN ('0', '6') THEN 1 ELSE 0 END
FROM dagar;
"""


# ===============================================================
# STJÄRNSCHEMAT
# ===============================================================

STAR = """
DROP VIEW IF EXISTS fact_ratings;
DROP VIEW IF EXISTS dim_movie;
DROP VIEW IF EXISTS dim_genre;

-- FAKTATABELL: en rad per betyg. Grovheten ("grain") är det viktigaste
-- beslutet i all dimensionell modellering: exakt vad representerar en rad?
-- Här: en användares betyg på en film vid ett tillfälle.
CREATE VIEW fact_ratings AS
SELECT
    r.userId                            AS user_key,
    r.movieId                           AS movie_key,
    date(r.timestamp, 'unixepoch')      AS date_key,
    r.rating                            AS rating
FROM ratings AS r;

-- DIMENSION: film. En rad per film, allt beskrivande på ett ställe.
-- Här slås MovieLens och TMDB ihop, så att den som bygger rapporten
-- inte behöver veta att datan kom från två olika källor.
CREATE VIEW dim_movie AS
SELECT
    m.movieId                                   AS movie_key,
    m.title                                     AS title,
    m.year                                      AS release_year,
    (m.year / 10) * 10                          AS decade,
    t.runtime                                   AS runtime_min,
    t.original_language                         AS language,
    t.budget                                    AS budget,
    t.revenue                                   AS revenue,
    -- ROI = avkastning. CAST behövs, annars gör SQLite heltalsdivision.
    CASE WHEN t.budget > 100000 AND t.revenue IS NOT NULL
         THEN ROUND(CAST(t.revenue AS REAL) / t.budget, 2)
    END                                         AS revenue_multiple,
    t.vote_average                              AS tmdb_score,
    t.vote_count                                AS tmdb_votes,
    t.overview                                  AS overview,
    t.tagline                                   AS tagline,
    CASE WHEN t.tmdbId IS NOT NULL THEN 1 ELSE 0 END AS has_tmdb_data
FROM      movies      AS m
LEFT JOIN tmdb_movies AS t ON t.movieId = m.movieId;

-- DIMENSION: genre. En bryggtabell, eftersom en film kan ha flera genrer.
CREATE VIEW dim_genre AS
SELECT movieId AS movie_key, genre
FROM   movie_genres;
"""


# ===============================================================
# ANALYSVYER
# ===============================================================
# Dessa paketerar frågorna du skrev för hand på dag 2. Poängen med en vy är
# att komplexiteten skrivs EN gång och sedan används av alla. Vill du ändra
# hur "snittbetyg" definieras ändrar du på ett ställe istället för i tjugo
# rapporter — och slipper upptäcka att två rapporter räknade olika.

ANALYSIS = """
DROP VIEW IF EXISTS v_movie_stats;
DROP VIEW IF EXISTS v_genre_stats;
DROP VIEW IF EXISTS v_decade_stats;
DROP VIEW IF EXISTS v_rating_gap;
DROP VIEW IF EXISTS v_ratings_over_time;

-- En rad per film, med betygsstatistik påkopplad.
CREATE VIEW v_movie_stats AS
SELECT
    d.movie_key,
    d.title,
    d.release_year,
    d.decade,
    d.runtime_min,
    d.budget,
    d.revenue,
    d.revenue_multiple,
    d.tmdb_score,
    COUNT(f.rating)                    AS rating_count,
    ROUND(AVG(f.rating), 3)            AS avg_rating,
    MIN(f.rating)                      AS min_rating,
    MAX(f.rating)                      AS max_rating,
    d.overview
FROM      dim_movie    AS d
LEFT JOIN fact_ratings AS f ON f.movie_key = d.movie_key
GROUP BY  d.movie_key;

-- En rad per genre. HAVING filtrerar EFTER grupperingen, vilket krävs
-- när villkoret gäller ett aggregat (här: antal betyg).
CREATE VIEW v_genre_stats AS
SELECT
    g.genre,
    COUNT(DISTINCT g.movie_key)     AS movie_count,
    COUNT(f.rating)                 AS rating_count,
    ROUND(AVG(f.rating), 3)         AS avg_rating,
    ROUND(AVG(m.revenue_multiple), 2) AS avg_revenue_multiple,
    ROUND(AVG(m.runtime_min), 0)    AS avg_runtime
FROM      dim_genre    AS g
JOIN      dim_movie    AS m ON m.movie_key = g.movie_key
LEFT JOIN fact_ratings AS f ON f.movie_key = g.movie_key
GROUP BY  g.genre
HAVING    COUNT(f.rating) >= 100;

-- Utveckling per årtionde.
CREATE VIEW v_decade_stats AS
SELECT
    m.decade,
    COUNT(DISTINCT m.movie_key)  AS movie_count,
    COUNT(f.rating)              AS rating_count,
    ROUND(AVG(f.rating), 3)      AS avg_rating,
    ROUND(AVG(m.runtime_min), 0) AS avg_runtime,
    ROUND(AVG(m.tmdb_score), 2)  AS avg_tmdb_score
FROM      dim_movie    AS m
LEFT JOIN fact_ratings AS f ON f.movie_key = m.movie_key
WHERE     m.decade IS NOT NULL
GROUP BY  m.decade;

-- Där MovieLens-användarna och TMDB:s publik är oense.
-- MovieLens är 0–5, TMDB 0–10, så vi dubblar MovieLens för jämförbarhet.
-- Positiv gap = MovieLens gillar filmen mer än TMDB-publiken.
CREATE VIEW v_rating_gap AS
SELECT
    m.movie_key,
    m.title,
    m.release_year,
    COUNT(f.rating)                                     AS rating_count,
    ROUND(AVG(f.rating) * 2, 2)                         AS movielens_score,
    m.tmdb_score                                        AS tmdb_score,
    ROUND(AVG(f.rating) * 2 - m.tmdb_score, 2)          AS gap
FROM     dim_movie    AS m
JOIN     fact_ratings AS f ON f.movie_key = m.movie_key
WHERE    m.tmdb_score IS NOT NULL
GROUP BY m.movie_key
HAVING   COUNT(f.rating) >= 50;

-- Betygsaktivitet över tid. Här används datumdimensionen.
CREATE VIEW v_ratings_over_time AS
SELECT
    dd.year,
    dd.quarter,
    dd.month,
    dd.month_name,
    COUNT(f.rating)         AS rating_count,
    ROUND(AVG(f.rating), 3) AS avg_rating
FROM     dim_date    AS dd
JOIN     fact_ratings AS f ON f.date_key = dd.date_key
GROUP BY dd.year, dd.month;
"""


def bygg() -> None:
    with db.connect() as conn:
        if db.table_count(conn, "ratings") == 0:
            print("Tabellen ratings är tom. Kör src/02_load_movielens.py först.")
            sys.exit(1)

        rubrik("DIMENSION – datum")
        conn.executescript(DIM_DATE)
        antal = db.table_count(conn, "dim_date")
        span = conn.execute(
            "SELECT MIN(date_key), MAX(date_key) FROM dim_date").fetchone()
        print(f"{OK} dim_date: {antal:,} dagar ({span[0]} → {span[1]})")

        rubrik("STJÄRNSCHEMA")
        conn.executescript(STAR)
        for vy in ("fact_ratings", "dim_movie", "dim_genre"):
            print(f"{OK} {vy:<16} {db.table_count(conn, vy):>8,} rader")

        rubrik("ANALYSVYER")
        conn.executescript(ANALYSIS)
        for vy in ("v_movie_stats", "v_genre_stats", "v_decade_stats",
                   "v_rating_gap", "v_ratings_over_time"):
            print(f"{OK} {vy:<22} {db.table_count(conn, vy):>8,} rader")

        conn.commit()
        visa_exempel(conn)


def visa_exempel(conn) -> None:
    """Läser ur vyerna så du ser att de faktiskt ger vettiga svar."""

    rubrik("Genrer med högst snittbetyg")
    print(f"\n  {'Genre':<14} {'Filmer':>7} {'Betyg':>7} {'Snitt':>7} {'Speltid':>8}")
    print(f"  {'-'*14} {'-'*7} {'-'*7} {'-'*7} {'-'*8}")
    for g, mc, rc, avg, rt in conn.execute("""
            SELECT genre, movie_count, rating_count, avg_rating, avg_runtime
            FROM v_genre_stats ORDER BY avg_rating DESC LIMIT 8"""):
        print(f"  {g:<14} {mc:>7,} {rc:>7,} {avg:>7} {rt or '?':>8}")

    rubrik("Störst oenighet: MovieLens gillar mer än TMDB")
    print(f"\n  {'Titel':<34} {'ML':>6} {'TMDB':>6} {'Gap':>6}")
    print(f"  {'-'*34} {'-'*6} {'-'*6} {'-'*6}")
    for t, ml, tmdb, gap in conn.execute("""
            SELECT title, movielens_score, tmdb_score, gap
            FROM v_rating_gap ORDER BY gap DESC LIMIT 5"""):
        print(f"  {t[:34]:<34} {ml:>6} {tmdb:>6} {gap:>+6}")

    print(f"\n  ...och där TMDB gillar mer än MovieLens:\n")
    for t, ml, tmdb, gap in conn.execute("""
            SELECT title, movielens_score, tmdb_score, gap
            FROM v_rating_gap ORDER BY gap ASC LIMIT 5"""):
        print(f"  {t[:34]:<34} {ml:>6} {tmdb:>6} {gap:>+6}")

    rubrik("Utveckling per årtionde")
    print(f"\n  {'Årtionde':>9} {'Filmer':>8} {'Snitt':>7} {'Speltid':>8}")
    print(f"  {'-'*9} {'-'*8} {'-'*7} {'-'*8}")
    for dec, mc, rc, avg, rt, tmdb in conn.execute("""
            SELECT * FROM v_decade_stats ORDER BY decade"""):
        print(f"  {str(dec) + 's':>9} {mc:>8,} {avg or '?':>7} {rt or '?':>8}")


if __name__ == "__main__":
    print("\n  Bygger datamodell")
    bygg()
    print(f"\n{OK} Klart. Nästa steg: python src/05_quality_checks.py\n")
