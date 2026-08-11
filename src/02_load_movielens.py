"""
02_load_movielens.py
--------------------
Dag 2, del 1: laddar ner MovieLens-datasetet och läser in det i databasen.

Kör med:  python src/02_load_movielens.py

Detta är ett klassiskt ETL-skript — Extract, Transform, Load:

  EXTRACT   ladda ner zip-filen, packa upp den, läs CSV-filerna
  TRANSFORM städa datan: bryt ut årtal ur titeln, dela upp genrer
  LOAD      skriv resultatet till SQLite i ett normaliserat schema

Datasetet är ml-latest-small: 100 836 betyg från 610 användare på 9 742 filmer.
Cirka 1 MB. Det finns en version med 25 miljoner betyg, men den är 1 GB och
gör allt långsammare utan att lära dig något nytt.
"""

import io
import sys
import zipfile

import pandas as pd
import requests

import db

URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"

OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def rubrik(text: str) -> None:
    print(f"\n{'=' * 55}\n  {text}\n{'=' * 55}")


# ===============================================================
# EXTRACT
# ===============================================================

def ladda_ner() -> None:
    """
    Hämtar zip-filen och packar upp den i data/raw/.

    Hoppar över nedladdningen om filerna redan finns, så att du kan köra
    skriptet om och om igen utan att belasta deras server i onödan.
    """
    rubrik("EXTRACT – hämta datasetet")

    mapp = db.RAW_DIR / "ml-latest-small"

    if (mapp / "ratings.csv").exists():
        print(f"{OK} Datasetet finns redan i data/raw/ – hoppar över nedladdning.")
        print("    (radera mappen om du vill hämta det igen)")
        return

    db.ensure_dirs()
    print(f"    Hämtar {URL}")
    print("    (~1 MB, tar några sekunder)")

    try:
        svar = requests.get(URL, timeout=60)
        svar.raise_for_status()  # kastar fel om servern svarade 404, 500 osv
    except requests.RequestException as fel:
        print(f"{FAIL} Nedladdningen misslyckades: {fel}")
        print("\n    Ladda ner manuellt istället:")
        print(f"      1. Öppna {URL} i webbläsaren")
        print("      2. Packa upp zip-filen")
        print(f"      3. Lägg mappen 'ml-latest-small' i {db.RAW_DIR}")
        sys.exit(1)

    # Packa upp direkt ur minnet, utan att spara zip-filen till disk.
    # io.BytesIO låter zipfile läsa bytes som om de vore en fil.
    with zipfile.ZipFile(io.BytesIO(svar.content)) as z:
        z.extractall(db.RAW_DIR)

    print(f"{OK} Uppackat till data/raw/ml-latest-small/")


def läs_csv() -> dict[str, pd.DataFrame]:
    """Läser in de tre CSV-filer vi behöver som pandas DataFrames."""
    mapp = db.RAW_DIR / "ml-latest-small"

    # En DataFrame är pandas motsvarighet till ett Excel-blad:
    # namngivna kolumner, numrerade rader, och operationer som gäller
    # hela kolumner samtidigt istället för cell för cell.
    filer = {
        "movies": "movies.csv",    # movieId, title, genres
        "ratings": "ratings.csv",  # userId, movieId, rating, timestamp
        "links": "links.csv",      # movieId, imdbId, tmdbId
    }

    data = {}
    for namn, filnamn in filer.items():
        df = pd.read_csv(mapp / filnamn)
        data[namn] = df
        print(f"{OK} {filnamn:<14} {len(df):>7,} rader, kolumner: {list(df.columns)}")

    return data


# ===============================================================
# TRANSFORM
# ===============================================================

def städa_filmer(movies: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    """
    MovieLens-titlar ser ut så här:

        Toy Story (1995)
        City of Lost Children, The (Cité des enfants perdus, La) (1995)
        Babylon 5                              ← inget årtal alls

    Årtalet sitter fast i titelsträngen, vilket är oanvändbart för analys.
    Vi bryter ut det till en egen numerisk kolumn.
    """
    rubrik("TRANSFORM – städa filmdatan")

    df = movies.copy()  # arbeta på en kopia, rör aldrig originalet

    # Regex: \( ( \d{4} ) \) i slutet av strängen.
    # extract() returnerar NaN om mönstret inte hittas — precis vad vi vill.
    df["year"] = df["title"].str.extract(r"\((\d{4})\)\s*$")[0]

    # Ta bort årtalet ur titeln och trimma bort mellanslag som blir kvar
    df["title"] = df["title"].str.replace(r"\s*\(\d{4}\)\s*$", "", regex=True).str.strip()

    utan_år = df["year"].isna().sum()
    print(f"{OK} Årtal utbrutet ur titeln.")
    if utan_år:
        print(f"    {utan_år} filmer saknar årtal – de behåller NULL, vi hittar inte på data.")

    # Int64 (stort I) är pandas heltalstyp som tillåter saknade värden.
    # Vanlig int kan inte vara NULL, så den skulle krascha här.
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    # Koppla på tmdbId från links.csv. Utan den kan vi inte hämta från TMDB på del 2.
    # how="left" = behåll alla filmer även om de saknar länk.
    df = df.merge(links[["movieId", "imdbId", "tmdbId"]], on="movieId", how="left")
    df["tmdbId"] = pd.to_numeric(df["tmdbId"], errors="coerce").astype("Int64")

    saknar_tmdb = df["tmdbId"].isna().sum()
    print(f"{OK} TMDB-id påkopplat.")
    print(f"    {saknar_tmdb} filmer saknar tmdbId ({saknar_tmdb / len(df):.1%}) – normalt i verklig data.")

    return df[["movieId", "title", "year", "imdbId", "tmdbId", "genres"]]


def dela_genrer(movies: pd.DataFrame) -> pd.DataFrame:
    """
    Genrer kommer som en enda sträng med rör emellan:

        "Adventure|Animation|Children|Comedy|Fantasy"

    Det går inte att filtrera eller gruppera på. Vi gör om det till en
    kopplingstabell med en rad per film-och-genre-kombination:

        movieId  genre
        1        Adventure
        1        Animation
        1        Children

    Detta kallas normalisering och är själva kärnan i relationsdatabasdesign.
    Efter detta är "visa alla animerade filmer" en enkel WHERE-sats istället
    för strängmatchning.
    """
    # explode() gör en rad per element i listan — den gör hela jobbet
    df = movies[["movieId", "genres"]].copy()
    df["genre"] = df["genres"].str.split("|")
    df = df.explode("genre")

    # MovieLens använder denna platshållare för filmer utan genre
    df = df[df["genre"] != "(no genres listed)"]
    df = df[["movieId", "genre"]].dropna()

    print(f"{OK} Genrer normaliserade: {len(df):,} kopplingar, "
          f"{df['genre'].nunique()} unika genrer.")

    return df


# ===============================================================
# LOAD
# ===============================================================

SCHEMA = """
DROP TABLE IF EXISTS movie_genres;
DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS movies;

-- En rad per film. movieId är primärnyckel: unik, får inte vara NULL.
CREATE TABLE movies (
    movieId  INTEGER PRIMARY KEY,
    title    TEXT    NOT NULL,
    year     INTEGER,
    imdbId   INTEGER,
    tmdbId   INTEGER
);

-- En rad per betyg. Foreign key = movieId måste finnas i movies.
-- Databasen vägrar spara ett betyg på en film som inte existerar.
CREATE TABLE ratings (
    userId    INTEGER NOT NULL,
    movieId   INTEGER NOT NULL,
    rating    REAL    NOT NULL,
    timestamp INTEGER,
    FOREIGN KEY (movieId) REFERENCES movies(movieId)
);

-- Kopplingstabell för genrer (många-till-många).
CREATE TABLE movie_genres (
    movieId INTEGER NOT NULL,
    genre   TEXT    NOT NULL,
    PRIMARY KEY (movieId, genre),
    FOREIGN KEY (movieId) REFERENCES movies(movieId)
);

-- Index gör WHERE och JOIN på dessa kolumner dramatiskt snabbare.
-- Utan index måste SQLite läsa varje rad; med index kan den hoppa direkt.
CREATE INDEX idx_ratings_movie ON ratings(movieId);
CREATE INDEX idx_ratings_user  ON ratings(userId);
CREATE INDEX idx_genres_genre  ON movie_genres(genre);
"""


def ladda_till_db(movies: pd.DataFrame, ratings: pd.DataFrame,
                  genres: pd.DataFrame) -> None:
    rubrik("LOAD – skriv till databasen")

    with db.connect() as conn:
        # executescript() kan köra flera SQL-satser i följd
        conn.executescript(SCHEMA)
        print(f"{OK} Schema skapat: movies, ratings, movie_genres + index")

        # to_sql() skriver en hel DataFrame till en tabell.
        # if_exists="append" = lägg till i tabellen vi just skapade.
        # index=False = spara inte pandas radnummer, vi har egna nycklar.
        movies[["movieId", "title", "year", "imdbId", "tmdbId"]].to_sql(
            "movies", conn, if_exists="append", index=False)

        ratings.to_sql("ratings", conn, if_exists="append", index=False)
        genres.to_sql("movie_genres", conn, if_exists="append", index=False)

        conn.commit()
        print(f"{OK} All data skriven till {db.DB_PATH.name}")
        db.show_summary(conn)


# ===============================================================
# Kontroll — läs tillbaka och verifiera
# ===============================================================

def kontrollera() -> None:
    """
    Grundregel: lita aldrig på att en inläsning gick rätt. Läs tillbaka
    och titta på datan. Nästan alla databugg jag sett hade fångats här.
    """
    rubrik("KONTROLL – läs tillbaka ur databasen")

    with db.connect() as conn:
        print("\n  De 5 mest betygsatta filmerna:\n")

        # Din första riktiga JOIN: kombinera movies och ratings,
        # gruppera per film, räkna och snitta.
        rader = conn.execute("""
            SELECT  m.title,
                    m.year,
                    COUNT(r.rating)          AS antal,
                    ROUND(AVG(r.rating), 2)  AS snitt
            FROM        movies  AS m
            INNER JOIN  ratings AS r ON r.movieId = m.movieId
            GROUP BY    m.movieId
            ORDER BY    antal DESC
            LIMIT 5
        """).fetchall()

        print(f"    {'Titel':<38} {'År':>5} {'Antal':>7} {'Snitt':>6}")
        print(f"    {'-' * 38} {'-' * 5} {'-' * 7} {'-' * 6}")
        for titel, år, antal, snitt in rader:
            print(f"    {titel[:38]:<38} {år or '?':>5} {antal:>7} {snitt:>6}")

        print("\n  Vanligaste genrerna:\n")
        rader = conn.execute("""
            SELECT   genre, COUNT(*) AS antal
            FROM     movie_genres
            GROUP BY genre
            ORDER BY antal DESC
            LIMIT 5
        """).fetchall()

        for genre, antal in rader:
            stapel = "█" * (antal // 100)
            print(f"    {genre:<12} {antal:>5}  {stapel}")


# ===============================================================
def main() -> None:
    print("\n  MovieLens → SQLite")

    ladda_ner()

    print()
    data = läs_csv()

    movies = städa_filmer(data["movies"], data["links"])
    genres = dela_genrer(movies)

    ladda_till_db(movies, data["ratings"], genres)
    kontrollera()

    print(f"\n{OK} Klart. Nästa steg: python src/03_fetch_tmdb.py\n")


if __name__ == "__main__":
    main()
