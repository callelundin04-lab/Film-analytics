"""
05_quality_checks.py
--------------------
Dag 3: datakvalitetskontroller.

Kör med:  python src/05_quality_checks.py

Varför detta finns: en analys som bygger på trasig data ser precis lika
övertygande ut som en analys som bygger på korrekt data. Diagrammen blir
lika snygga, snitten lika prydliga. Skillnaden syns först när någon fattar
ett beslut på fel underlag.

Därför testar man data, precis som man testar kod. Varje kontroll nedan
formulerar ett PÅSTÅENDE om datan och verifierar det:

  FAIL – bryter mot något som måste gälla. Åtgärda innan du går vidare.
  WARN – avvikelse som kan vara helt normal, men som du bör känna till.
  PASS – påståendet håller.

Att kunna säga "jag byggde in datakvalitetskontroller i pipelinen" är
ovanligt hos juniora sökande och märks i en intervju.
"""

import sys
from datetime import date

import db

GRÖN, RÖD, GUL, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

resultat: list[tuple[str, str, str]] = []


def kontroll(namn: str, sql: str, conn, *, max_ok: int = 0,
             varning: bool = False, detalj: str = "") -> None:
    """
    Kör en SQL-fråga som räknar ANTAL PROBLEMRADER.

    Frågan ska returnera ett enda tal. 0 betyder att allt är bra.
    max_ok låter dig acceptera ett visst antal, t.ex. kända luckor i källdatan.
    """
    antal = conn.execute(sql).fetchone()[0]

    if antal <= max_ok:
        status, färg = "PASS", GRÖN
        text = "inga avvikelser"  # detalj är bara relevant när något avviker
    elif varning:
        status, färg = "WARN", GUL
        text = f"{antal:,} rader – {detalj}" if detalj else f"{antal:,} rader"
    else:
        status, färg = "FAIL", RÖD
        text = f"{antal:,} rader – {detalj}" if detalj else f"{antal:,} rader"

    resultat.append((status, namn, text))
    print(f"  {färg}{status}{RESET}  {namn:<44} {text}")


def rubrik(text: str) -> None:
    print(f"\n{'-' * 74}\n  {text}\n{'-' * 74}")


def main() -> None:
    print("\n  Datakvalitetskontroll\n")

    with db.connect() as conn:
        if db.table_count(conn, "movies") == 0:
            print("Databasen är tom. Kör src/02_load_movielens.py först.")
            sys.exit(1)

        # -----------------------------------------------------------
        rubrik("Referentiell integritet – pekar allt på något som finns?")

        kontroll(
            "Betyg som pekar på okänd film",
            """SELECT COUNT(*) FROM ratings r
               LEFT JOIN movies m ON m.movieId = r.movieId
               WHERE m.movieId IS NULL""",
            conn, detalj="föräldralösa betyg")

        kontroll(
            "Genrer som pekar på okänd film",
            """SELECT COUNT(*) FROM movie_genres g
               LEFT JOIN movies m ON m.movieId = g.movieId
               WHERE m.movieId IS NULL""",
            conn)

        kontroll(
            "TMDB-rader som pekar på okänd film",
            """SELECT COUNT(*) FROM tmdb_movies t
               LEFT JOIN movies m ON m.movieId = t.movieId
               WHERE m.movieId IS NULL""",
            conn)

        # -----------------------------------------------------------
        rubrik("Unikhet – finns dubbletter där det inte får finnas?")

        kontroll(
            "Dubbletter av movieId",
            """SELECT COUNT(*) FROM (
                 SELECT movieId FROM movies GROUP BY movieId HAVING COUNT(*) > 1)""",
            conn)

        kontroll(
            "Samma användare har betygsatt samma film flera gånger",
            """SELECT COUNT(*) FROM (
                 SELECT userId, movieId FROM ratings
                 GROUP BY userId, movieId HAVING COUNT(*) > 1)""",
            conn, detalj="dubbla betyg")

        # -----------------------------------------------------------
        rubrik("Värdeintervall – är värdena fysiskt möjliga?")

        # MovieLens använder 0.5 till 5.0 i halvsteg
        kontroll(
            "Betyg utanför 0,5–5,0",
            "SELECT COUNT(*) FROM ratings WHERE rating < 0.5 OR rating > 5.0",
            conn)

        # Första filmen någonsin gjordes 1888. Marginal framåt för
        # filmer som annonserats men inte släppts.
        nästa_år = date.today().year + 2
        kontroll(
            "Produktionsår utanför 1874–%d" % nästa_år,
            f"""SELECT COUNT(*) FROM movies
                WHERE year IS NOT NULL AND (year < 1874 OR year > {nästa_år})""",
            conn)

        kontroll(
            "Negativ budget eller intäkt",
            """SELECT COUNT(*) FROM tmdb_movies
               WHERE budget < 0 OR revenue < 0""",
            conn)

        kontroll(
            "Nollor kvar i budget/intäkt (ska vara NULL)",
            """SELECT COUNT(*) FROM tmdb_movies
               WHERE budget = 0 OR revenue = 0""",
            conn,
            detalj="0 betyder 'okänt' hos TMDB och ska lagras som NULL")

        kontroll(
            "Orimlig speltid (under 5 eller över 500 min)",
            """SELECT COUNT(*) FROM tmdb_movies
               WHERE runtime IS NOT NULL AND (runtime < 5 OR runtime > 500)""",
            conn, varning=True, detalj="kontrollera manuellt")

        # -----------------------------------------------------------
        rubrik("Täckning – hur mycket data har vi faktiskt?")

        kontroll(
            "Filmer helt utan betyg",
            """SELECT COUNT(*) FROM movies m
               LEFT JOIN ratings r ON r.movieId = m.movieId
               WHERE r.movieId IS NULL""",
            conn, varning=True, max_ok=0,
            detalj="normalt i MovieLens, men de blir tomma i rapporter")

        kontroll(
            "Filmer utan årtal",
            "SELECT COUNT(*) FROM movies WHERE year IS NULL",
            conn, varning=True, detalj="saknas i källdatan")

        kontroll(
            "Filmer utan tmdbId i källdatan",
            "SELECT COUNT(*) FROM movies WHERE tmdbId IS NULL",
            conn, varning=True, detalj="kan inte hämtas från TMDB")

        kontroll(
            "Filmer med tmdbId men ännu inte hämtade",
            """SELECT COUNT(*) FROM movies m
               WHERE m.tmdbId IS NOT NULL
                 AND m.tmdbId NOT IN (SELECT tmdbId FROM tmdb_movies)
                 AND m.tmdbId NOT IN (SELECT tmdbId FROM tmdb_failures)""",
            conn, varning=True,
            detalj="kör 03_fetch_tmdb.py --limit 0 för att hämta allt")

        kontroll(
            "Hämtade filmer utan synopsis",
            "SELECT COUNT(*) FROM tmdb_movies WHERE overview IS NULL OR overview = ''",
            conn, varning=True, detalj="kan inte analyseras av LLM:en på dag 4")

        # -----------------------------------------------------------
        rubrik("Datamodellen – hänger vyerna ihop?")

        kontroll(
            "Luckor i datumdimensionen",
            """SELECT (julianday(MAX(date_key)) - julianday(MIN(date_key)) + 1)
                      - COUNT(*) FROM dim_date""",
            conn, detalj="varje dag i intervallet ska finnas")

        kontroll(
            "Betyg vars datum saknas i dim_date",
            """SELECT COUNT(*) FROM fact_ratings f
               LEFT JOIN dim_date d ON d.date_key = f.date_key
               WHERE d.date_key IS NULL""",
            conn)

        kontroll(
            "Rader i fact_ratings ≠ rader i ratings",
            """SELECT ABS((SELECT COUNT(*) FROM fact_ratings)
                        - (SELECT COUNT(*) FROM ratings))""",
            conn, detalj="vyn får inte tappa eller duplicera rader")

        # -----------------------------------------------------------
        sammanfatta(conn)


def sammanfatta(conn) -> None:
    fails = [r for r in resultat if r[0] == "FAIL"]
    warns = [r for r in resultat if r[0] == "WARN"]
    passes = [r for r in resultat if r[0] == "PASS"]

    print(f"\n{'=' * 74}")
    print(f"  {GRÖN}{len(passes)} PASS{RESET}   "
          f"{GUL}{len(warns)} WARN{RESET}   "
          f"{RÖD}{len(fails)} FAIL{RESET}")
    print(f"{'=' * 74}")

    # Nyckeltal, som en snabb rimlighetskontroll med egna ögon
    rad = conn.execute("""
        SELECT (SELECT COUNT(*) FROM movies),
               (SELECT COUNT(*) FROM ratings),
               (SELECT COUNT(DISTINCT userId) FROM ratings),
               (SELECT COUNT(*) FROM tmdb_movies),
               (SELECT ROUND(AVG(rating), 3) FROM ratings)
    """).fetchone()

    print(f"\n  Filmer                {rad[0]:>10,}")
    print(f"  Betyg                 {rad[1]:>10,}")
    print(f"  Användare             {rad[2]:>10,}")
    print(f"  Filmer med TMDB-data  {rad[3]:>10,}")
    print(f"  Snittbetyg totalt     {rad[4]:>10}")

    if fails:
        print(f"\n  {RÖD}Åtgärda dessa innan du går vidare:{RESET}")
        for _, namn, text in fails:
            print(f"    • {namn}: {text}")
        sys.exit(1)

    if warns:
        print(f"\n  {GUL}Varningarna är normala i denna datamängd.{RESET}")
        print("  De beskriver luckor i källdatan, inte fel i din pipeline.")

    print(f"\n  {GRÖN}Datamodellen är verifierad. Klar för dag 4.{RESET}\n")


if __name__ == "__main__":
    main()
