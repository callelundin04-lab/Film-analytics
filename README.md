# Film Analytics — End-to-End Data Pipeline

> **Status:** under utveckling (dag 1 av 7 klar)

Ett dataprojekt som tar filmdata från publika API:er hela vägen till en interaktiv dashboard, med två AI-lager på vägen: en LLM som extraherar strukturerade egenskaper ur filmsynopsis, och en ML-modell som förutsäger personliga betyg.

## Arkitektur

```
TMDB API + MovieLens 25M + egna betyg
            │
            ▼
   Python ETL (pandas, requests)
            │
            ▼
     SQLite-databas  ◄──┐
            │           │  nya kolumner
            ▼           │
   AI-lager (Claude + scikit-learn)
            │
            ▼
   Power BI-dashboard
```

## Frågor projektet besvarar

- Vad kännetecknar filmer som publiken älskar men kritiker ogillar — och var är gapet störst?
- Kan en modell förutsäga mitt betyg på en film jag inte sett, och hur nära kommer den?
- Vilka teman och toner återkommer i de filmer jag betygsätter högst?
- Ger vissa genrer systematiskt bättre avkastning per investerad krona?

## Teknik

| Område | Verktyg |
|---|---|
| Språk | Python 3.10+ |
| Datahantering | pandas, NumPy |
| Databas | SQLite, SQLAlchemy, SQL |
| Maskininlärning | scikit-learn |
| LLM | Anthropic Claude API |
| Visualisering | Power BI, matplotlib |
| Versionshantering | Git |

## Datakällor

- **[TMDB API](https://www.themoviedb.org/documentation/api)** — metadata, synopsis, budget, intäkter
- **[MovieLens 25M](https://grouplens.org/datasets/movielens/25m/)** — 25 miljoner användarbetyg
- **Egna betyg** — manuellt satta betyg som modellen tränas mot

## Kom igång

```bash
git clone https://github.com/DITT-ANVÄNDARNAMN/film-analytics.git
cd film-analytics

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # fyll i dina API-nycklar
python src/01_check_setup.py
```

## Projektstruktur

```
film-analytics/
├── data/
│   └── raw/              # nedladdad rådata (gitignorerad)
├── src/
│   └── 01_check_setup.py # verifierar miljön
├── notebooks/            # utforskande analys
├── .env.example          # mall för API-nycklar
├── requirements.txt
├── DAG1.md               # installationsguide
└── README.md
```

## Framsteg

- [x] **Dag 1** — Miljö, projektstruktur, Git
- [ ] **Dag 2** — ETL: MovieLens + TMDB → databas
- [ ] **Dag 3** — SQL-modellering: schema, joins, vyer
- [ ] **Dag 4** — AI-lager 1: LLM-baserad feature-extraktion
- [ ] **Dag 5** — AI-lager 2: betygsprediktionsmodell
- [ ] **Dag 6** — Power BI-dashboard
- [ ] **Dag 7** — Dokumentation och slutpolering

## Licens

MIT. Filmdata tillhör respektive leverantör; TMDB-data används enligt deras användarvillkor. Detta projekt är inte godkänt av eller kopplat till TMDB.
