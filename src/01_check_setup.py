"""
01_check_setup.py
-----------------
Dag 1: Kontrollerar att hela din miljö fungerar innan vi börjar bygga.

Kör med:  python src/01_check_setup.py

Skriptet gör fyra saker:
  1. Kollar Python-versionen
  2. Kollar att alla paket är installerade
  3. Kollar att dina API-nycklar hittas i .env-filen
  4. Skapar en liten SQLite-databas och läser tillbaka från den
"""

import sys
import sqlite3
from pathlib import Path

# ANSI-färger så output blir lätt att läsa i terminalen
OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

# Projektroten = mappen ovanför src/
ROOT = Path(__file__).resolve().parent.parent

problems = []


def rubrik(text: str) -> None:
    print(f"\n--- {text} ---")


# ---------------------------------------------------------------
# 1. Python-version
# ---------------------------------------------------------------
rubrik("1. Python")

version = sys.version_info
print(f"    Python {version.major}.{version.minor}.{version.micro}")
print(f"    Sökväg: {sys.executable}")

if version >= (3, 10):
    print(f"{OK} Versionen är tillräckligt ny.")
else:
    print(f"{FAIL} Du behöver Python 3.10 eller nyare.")
    problems.append("Uppgradera Python till 3.10+")

# Kollar att vi kör inifrån det virtuella miljön (venv)
if sys.prefix != sys.base_prefix:
    print(f"{OK} Du kör inifrån ditt virtuella miljö (venv).")
else:
    print(f"{FAIL} Du kör INTE i venv. Kör: source .venv/bin/activate")
    problems.append("Aktivera venv innan du kör skript")


# ---------------------------------------------------------------
# 2. Paket
# ---------------------------------------------------------------
rubrik("2. Paket")

# Nyckel = importnamnet, värde = namnet man installerar med pip
paket = {
    "pandas": "pandas",              # tabeller och datahantering
    "requests": "requests",          # hämta data från API:er
    "sqlalchemy": "SQLAlchemy",      # prata med databasen från Python
    "dotenv": "python-dotenv",       # läsa hemliga nycklar från .env
    "sklearn": "scikit-learn",       # maskininlärning (dag 5)
    "matplotlib": "matplotlib",      # snabba diagram medan vi bygger
    "tqdm": "tqdm",                  # progressbar när vi hämtar mycket data
}

for importnamn, pipnamn in paket.items():
    try:
        modul = __import__(importnamn)
        ver = getattr(modul, "__version__", "okänd version")
        print(f"{OK} {pipnamn:<16} {ver}")
    except ImportError:
        print(f"{FAIL} {pipnamn:<16} saknas")
        problems.append(f"pip install {pipnamn}")


# ---------------------------------------------------------------
# 3. API-nycklar
# ---------------------------------------------------------------
rubrik("3. API-nycklar (.env)")

env_fil = ROOT / ".env"

if not env_fil.exists():
    print(f"{FAIL} Ingen .env-fil hittad i {ROOT}")
    problems.append("Skapa en .env-fil (se guiden, steg 6)")
else:
    print(f"{OK} .env-filen hittad.")

    try:
        from dotenv import load_dotenv
        import os

        load_dotenv(env_fil)

        # TMDB behövs på dag 2, Anthropic först på dag 4
        nycklar = {
            "TMDB_API_KEY": "behövs dag 2",
            "ANTHROPIC_API_KEY": "behövs dag 4",
        }

        for namn, när in nycklar.items():
            värde = os.getenv(namn)
            if värde and not värde.startswith("din_"):
                # Visa bara början av nyckeln - aldrig hela, av vana
                print(f"{OK} {namn} hittad ({värde[:8]}...)")
            else:
                print(f"    – {namn} inte satt ännu ({när})")
    except ImportError:
        print(f"{FAIL} python-dotenv saknas, kan inte läsa .env")


# ---------------------------------------------------------------
# 4. SQLite
# ---------------------------------------------------------------
rubrik("4. SQLite-databas")

db_sökväg = ROOT / "data" / "test.db"
db_sökväg.parent.mkdir(parents=True, exist_ok=True)

try:
    # connect() skapar filen om den inte finns
    conn = sqlite3.connect(db_sökväg)
    cur = conn.cursor()

    # Skapa en testtabell, lägg in tre filmer, läs tillbaka
    cur.execute("DROP TABLE IF EXISTS testfilmer")
    cur.execute("""
        CREATE TABLE testfilmer (
            id      INTEGER PRIMARY KEY,
            titel   TEXT NOT NULL,
            år      INTEGER,
            betyg   REAL
        )
    """)
    cur.executemany(
        "INSERT INTO testfilmer (titel, år, betyg) VALUES (?, ?, ?)",
        [
            ("Parasite", 2019, 4.6),
            ("Arrival", 2016, 4.2),
            ("Whiplash", 2014, 4.5),
        ],
    )
    conn.commit()

    # Din första riktiga SQL-fråga i projektet
    cur.execute("""
        SELECT titel, år, betyg
        FROM testfilmer
        WHERE betyg > 4.3
        ORDER BY betyg DESC
    """)
    rader = cur.fetchall()

    print(f"{OK} Databas skapad: {db_sökväg.name}")
    print(f"{OK} SQL-fråga körd, {len(rader)} rader tillbaka:")
    for titel, år, betyg in rader:
        print(f"      {titel} ({år}) – {betyg}")

    conn.close()
    db_sökväg.unlink()  # städa bort testfilen
    print(f"{OK} Testdatabasen borttagen igen.")

except Exception as fel:
    print(f"{FAIL} SQLite-problem: {fel}")
    problems.append("SQLite fungerar inte")


# ---------------------------------------------------------------
# Sammanfattning
# ---------------------------------------------------------------
print("\n" + "=" * 50)
if problems:
    print(f"{FAIL} {len(problems)} sak(er) kvar att fixa:\n")
    for i, p in enumerate(problems, 1):
        print(f"   {i}. {p}")
    sys.exit(1)
else:
    print(f"{OK} Allt fungerar. Du är klar med dag 1 – redo för dag 2.")
    sys.exit(0)
