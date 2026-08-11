"""
03_fetch_tmdb.py
----------------
Dag 2, del 2: hämtar metadata från TMDB för filmerna i databasen.

Kör med:  python src/03_fetch_tmdb.py
Eller:    python src/03_fetch_tmdb.py --limit 500     (färre filmer, snabbare test)
          python src/03_fetch_tmdb.py --limit 0       (alla filmer med tmdbId)

MovieLens ger oss betyg men nästan ingen information om filmerna. TMDB ger
synopsis, budget, intäkter, speltid och publikbetyg. Synopsis är särskilt
viktig — det är texten som LLM:en läser på dag 4.

Tre saker i det här skriptet är värda att förstå, eftersom de återkommer i
allt arbete mot externa API:er:

  1. Skriptet är ÅTERUPPTAGBART. Avbryter du med Ctrl+C och kör igen
     fortsätter det där det slutade istället för att börja om.
  2. Det RESPEKTERAR servern. En kort paus mellan anrop, och om servern
     säger "för snabbt" (429) väntar det och försöker igen.
  3. Det SPARAR RÅSVARET som JSON. Vill du använda ett fält vi inte
     plockade ut idag finns det kvar i databasen — du slipper hämta om.
"""

import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv
from tqdm import tqdm

import db

BAS_URL = "https://api.themoviedb.org/3/movie/{}"

# TMDB tillåter cirka 50 anrop per sekund. Vi ligger långt under, dels av
# artighet, dels för att en blockerad nyckel kostar mer tid än den sparar.
PAUS = 0.06  # sekunder mellan anrop → ~16 anrop/sekund

OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


SCHEMA = """
CREATE TABLE IF NOT EXISTS tmdb_movies (
    tmdbId            INTEGER PRIMARY KEY,
    movieId           INTEGER,
    tmdb_title        TEXT,
    original_language TEXT,
    release_date      TEXT,
    runtime           INTEGER,
    budget            INTEGER,
    revenue           INTEGER,
    vote_average      REAL,
    vote_count        INTEGER,
    popularity        REAL,
    tagline           TEXT,
    overview          TEXT,      -- synopsis: används av LLM:en på dag 4
    raw_json          TEXT,      -- hela svaret, för framtida behov
    fetched_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (movieId) REFERENCES movies(movieId)
);

-- Filmer som inte gick att hämta. Vi loggar dem istället för att försöka
-- i all evighet, men sparar orsaken så vi kan se vad som hände.
CREATE TABLE IF NOT EXISTS tmdb_failures (
    tmdbId     INTEGER PRIMARY KEY,
    movieId    INTEGER,
    reason     TEXT,
    failed_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tmdb_movieid ON tmdb_movies(movieId);
"""


def hämta_nyckel() -> str:
    """Läser TMDB-nyckeln ur .env och avbryter med tydligt fel om den saknas."""
    load_dotenv(db.ROOT / ".env")
    nyckel = os.getenv("TMDB_API_KEY", "").strip()

    if not nyckel or nyckel.startswith("din_"):
        print(f"{FAIL} TMDB_API_KEY saknas i .env")
        print("    Kontrollera att du sparade filen med Cmd + S.")
        sys.exit(1)

    return nyckel


def att_hämta(conn, limit: int) -> list[tuple[int, int]]:
    """
    Hämtar listan av filmer vi ännu inte har TMDB-data för.

    Sorterad efter antal betyg, mest betygsatta först. Anledningen: har du
    inte tid att hämta allt vill du ha de filmer som faktiskt förekommer i
    betygsdatan, inte obskyra filmer med ett enda betyg.

    De två NOT IN-satserna är det som gör skriptet återupptagbart — vi
    frågar efter det som saknas, inte efter allt.
    """
    sql = """
        SELECT      m.tmdbId, m.movieId
        FROM        movies AS m
        LEFT JOIN   ratings AS r ON r.movieId = m.movieId
        WHERE       m.tmdbId IS NOT NULL
          AND       m.tmdbId NOT IN (SELECT tmdbId FROM tmdb_movies)
          AND       m.tmdbId NOT IN (SELECT tmdbId FROM tmdb_failures)
        GROUP BY    m.movieId
        ORDER BY    COUNT(r.rating) DESC
    """
    if limit > 0:
        sql += f" LIMIT {limit}"

    return conn.execute(sql).fetchall()


def hämta_en(session: requests.Session, tmdb_id: int) -> tuple[dict | None, str | None]:
    """
    Hämtar en film. Returnerar (data, None) vid lyckat anrop,
    eller (None, orsak) vid fel.

    Försöker om vid 429 (för många anrop) och vid tillfälliga serverfel,
    med väntetid som fördubblas varje gång. Detta mönster heter
    exponential backoff och är standard i all API-integration.
    """
    for försök in range(4):
        try:
            svar = session.get(BAS_URL.format(tmdb_id), timeout=20)
        except requests.RequestException as fel:
            time.sleep(2 ** försök)
            if försök == 3:
                return None, f"nätverksfel: {type(fel).__name__}"
            continue

        if svar.status_code == 200:
            return svar.json(), None

        if svar.status_code == 404:
            # Filmen finns inte längre hos TMDB. Meningslöst att försöka igen.
            return None, "404 hittades inte"

        if svar.status_code == 401:
            print(f"\n{FAIL} 401 Unauthorized – nyckeln är felaktig eller saknar behörighet.")
            sys.exit(1)

        if svar.status_code == 429:
            # Servern ber oss sakta ner. Respektera Retry-After om den finns.
            vänta = int(svar.headers.get("Retry-After", 2 ** försök))
            time.sleep(vänta)
            continue

        # 500-fel osv: tillfälligt, värt ett nytt försök
        time.sleep(2 ** försök)

    return None, f"gav upp efter 4 försök (senast {svar.status_code})"


def plocka_fält(data: dict, movie_id: int) -> tuple:
    """
    Plockar ut de fält vi vill ha ur TMDB:s svar.

    TMDB använder 0 för "vi vet inte" i budget och revenue, vilket är
    farligt: räknar du snittbudget får du ett kraftigt underskattat värde.
    Vi gör om 0 till NULL så att SQL:s AVG() hoppar över dem istället.
    """
    def noll_till_null(v):
        return v if v else None

    return (
        data["id"],
        movie_id,
        data.get("title"),
        data.get("original_language"),
        data.get("release_date") or None,
        noll_till_null(data.get("runtime")),
        noll_till_null(data.get("budget")),
        noll_till_null(data.get("revenue")),
        noll_till_null(data.get("vote_average")),
        noll_till_null(data.get("vote_count")),
        data.get("popularity"),
        data.get("tagline") or None,
        data.get("overview") or None,
        json.dumps(data, ensure_ascii=False),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Hämtar filmdata från TMDB.")
    parser.add_argument("--limit", type=int, default=2000,
                        help="Max antal filmer att hämta. 0 = alla. Standard 2000.")
    args = parser.parse_args()

    nyckel = hämta_nyckel()

    print("\n  TMDB → SQLite\n")

    with db.connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()

        if db.table_count(conn, "movies") == 0:
            print(f"{FAIL} Tabellen movies är tom.")
            print("    Kör 'python src/02_load_movielens.py' först.")
            sys.exit(1)

        redan = db.table_count(conn, "tmdb_movies")
        if redan:
            print(f"    {redan:,} filmer finns redan – fortsätter där vi slutade.")

        jobb = att_hämta(conn, args.limit)

        if not jobb:
            print(f"{OK} Inget nytt att hämta. Allt är redan gjort.")
            db.show_summary(conn)
            return

        print(f"    {len(jobb):,} filmer att hämta.")
        print(f"    Uppskattad tid: ~{len(jobb) * PAUS / 60:.0f} min. "
              f"Ctrl+C avbryter tryggt.\n")

        # En Session återanvänder TCP-kopplingen mellan anrop istället för
        # att öppna en ny varje gång. Märkbart snabbare vid tusentals anrop.
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {nyckel}",
            "accept": "application/json",
        })

        lyckade = misslyckade = 0

        try:
            # tqdm ritar progressbaren. Den lindar helt enkelt runt listan
            # och räknar hur långt loopen kommit.
            for tmdb_id, movie_id in tqdm(jobb, unit=" film", ncols=76):
                data, orsak = hämta_en(session, tmdb_id)

                if data:
                    conn.execute(
                        """INSERT OR REPLACE INTO tmdb_movies
                           (tmdbId, movieId, tmdb_title, original_language,
                            release_date, runtime, budget, revenue, vote_average,
                            vote_count, popularity, tagline, overview, raw_json)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        plocka_fält(data, movie_id))
                    lyckade += 1
                else:
                    conn.execute(
                        """INSERT OR REPLACE INTO tmdb_failures
                           (tmdbId, movieId, reason) VALUES (?,?,?)""",
                        (tmdb_id, movie_id, orsak))
                    misslyckade += 1

                # Spara var 50:e film. Avbryter du mitt i förlorar du
                # som mest 50 filmer istället för hela körningen.
                if (lyckade + misslyckade) % 50 == 0:
                    conn.commit()

                time.sleep(PAUS)

        except KeyboardInterrupt:
            print("\n\n    Avbrutet. Det som hämtats är sparat.")
            print("    Kör skriptet igen för att fortsätta.")

        finally:
            conn.commit()

        print(f"\n{OK} {lyckade:,} filmer hämtade.")
        if misslyckade:
            print(f"    {misslyckade:,} misslyckades (loggade i tmdb_failures).")

        db.show_summary(conn)
        kontrollera(conn)


def kontrollera(conn) -> None:
    """Läser tillbaka och visar att datan faktiskt är användbar."""
    print("\n  Högst intäkt bland de hämtade filmerna:\n")

    rader = conn.execute("""
        SELECT   m.title, t.budget, t.revenue,
                 ROUND(CAST(t.revenue AS REAL) / t.budget, 1) AS multipel
        FROM     tmdb_movies AS t
        JOIN     movies      AS m ON m.movieId = t.movieId
        WHERE    t.revenue IS NOT NULL AND t.budget IS NOT NULL
        ORDER BY t.revenue DESC
        LIMIT 5
    """).fetchall()

    if not rader:
        print("    (ingen budget/intäktsdata ännu)")
    else:
        print(f"    {'Titel':<30} {'Budget':>13} {'Intäkt':>15} {'x':>6}")
        print(f"    {'-' * 30} {'-' * 13} {'-' * 15} {'-' * 6}")
        for titel, budget, revenue, multipel in rader:
            print(f"    {titel[:30]:<30} {budget:>13,} {revenue:>15,} {multipel:>6}")

    # Synopsis är råvaran för dag 4 — kontrollera att vi har dem
    antal = conn.execute(
        "SELECT COUNT(*) FROM tmdb_movies WHERE overview IS NOT NULL").fetchone()[0]
    print(f"\n{OK} {antal:,} filmer har synopsis – det är underlaget för dag 4.")


if __name__ == "__main__":
    main()
