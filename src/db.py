"""
db.py
-----
Delade hjälpfunktioner för databasen.

Den här filen körs inte direkt. Den importeras av de andra skripten så att
alla använder samma databasfil och samma sätt att koppla upp sig. Att lägga
sådant på ett ställe istället för att upprepa det i varje skript är en av de
mest grundläggande vanorna i all programmering.
"""

import sqlite3
from pathlib import Path

# Projektroten = mappen ovanför src/
# __file__ är sökvägen till denna fil. .resolve() gör den absolut,
# .parent tar ett steg upp. Två steg upp från src/db.py = projektroten.
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "film.db"


def ensure_dirs() -> None:
    """Skapar data/ och data/raw/ om de inte finns. Ofarligt att köra flera gånger."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    """
    Öppnar en koppling till databasen. Skapar filen om den inte finns.

    Använd som:
        with connect() as conn:
            ...

    Då stängs kopplingen automatiskt, även om något går fel på vägen.
    """
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)

    # Får SQLite att faktiskt kontrollera foreign keys. Av som standard,
    # av historiska skäl. Vi vill ha det på, så att databasen vägrar
    # spara en rad som pekar på en film som inte finns.
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def table_count(conn: sqlite3.Connection, table: str) -> int:
    """Antal rader i en tabell. Returnerar 0 om tabellen inte finns."""
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def show_summary(conn: sqlite3.Connection) -> None:
    """Skriver ut hur många rader varje tabell har. Bra för att se att allt gick in."""
    tabeller = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    if not tabeller:
        print("    (databasen är tom)")
        return

    print(f"\n    {'Tabell':<20} {'Rader':>10}")
    print(f"    {'-' * 20} {'-' * 10}")
    for (namn,) in tabeller:
        print(f"    {namn:<20} {table_count(conn, namn):>10,}")
