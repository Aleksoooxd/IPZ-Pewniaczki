# IPZ-Pewniaczki

## About the Project

IPZ-Pewniaczki is an academic project focused on developing a system for predicting football match results. It encompasses several key components:

1. **Data Scraping**: Gathering historical match data and future fixture information from various online sources.
2. **Data Processing and Feature Engineering**: Calculating advanced statistical metrics, ELO ratings, and team form/head-to-head (H2H) statistics.
3. **Prediction Model**: Training a machine learning model (XGBoost) to predict match outcomes (Home Win, Draw, Away Win). A single canonical XGBoost classifier is used for both past and future matches.
4. **Web Application (Flask)**: Providing an interactive interface for users to browse match details, league standings, team profiles, and view predictions.

## Screenshots

### Landing Page

![Landing Page](Docs/screenshots/landing_page.png)

### Main Page (Matches)

![Main Page](Docs/screenshots/mainpage.png)

### League View

![League View](Docs/screenshots/league_view.png)

### Match Detail

![Match Detail](Docs/screenshots/match_detail.png)

### Team Season Profile

![Team Season Profile](Docs/screenshots/team_season.png)

### Team All-Season Profile

![Team All-Season Profile](Docs/screenshots/team_allseason.png)

## Features
- **Top 11 tracked leagues**: View the top 11 leagues with the most matches played and ELO ratings.
- **Over 400 clubs**: Access detailed information about over 400 football clubs with their respective historically accurate logos.
- **Comprehensive Match Details**: View historical and upcoming matches with detailed information, including:
  - Match date and time.
  - Home and Away teams.
  - League and Matchday.
  - Final score (for past matches).
  - Team ELO ratings and changes.
  - Team market values.
  - Team form (last 3, last 5, and season).
  - Goals scored in recent matches and season.
  - Team placements in league tables.
  - Head-to-Head (H2H) statistics.
  - Bookmaker odds statistics (mean, standard deviation, Shannon entropy, Gini index, HHI, Coefficient of Variation).
  - Consensus prediction from bookmakers.
  - "Surprise" indicator based on odds.
- **Match Predictions**: Displays predicted results for matches with a confidence score.
- **Interactive League Tables**: Browse league standings for various seasons, including an "All-Time" view.
- **Team Profiles**: Interactive team detail pages with season and all-time statistics, including:
  - ELO rating history (per season and all-time).
  - League position history.
  - Cumulative points, goals scored and goals conceded charts.
  - Cumulative match results (Win/Draw/Loss) chart.
  - Season summary statistics with league-wide rankings.
- **Theme Toggle**: Switch between light and dark modes for better user experience.
- **Multi-Language Support**: Full UI translation via Flask-Babel, currently:
  - English
  - Polish (default)
  - Adding a language only requires a new `translations/<code>/LC_MESSAGES/messages.po` catalog.

## Data Sources

The project scrapes data from the following sources:

- **Football-Data.co.uk**: Provides historical match data, including results and a wide range of bookmaker odds.

## Technical Stack

- **Backend**: Python 3.9
- **Web Framework**: Flask
- **Database**: SQLite
- **ORM**: SQLAlchemy
- **Data Manipulation**: Pandas, NumPy
- **Web Scraping**: BeautifulSoup4, Requests, httpx, fuzzywuzzy, chardet, unidecode
- **Machine Learning**: XGBoost (canonical model)
- **Frontend**: HTML, CSS (custom, with Inter font), JavaScript (Chart.js for interactive charts)

## Project Structure

```
IPZ-Pewniaczki/
├── Docs/                   # Project documentation
│   └── screenshots/        # Application screenshots (see Screenshots section)
├── models/                 # Trained model checkpoints (xgboost_canonical.json)
├── src/
│   ├── flask_app/
│   │   ├── app/
│   │   │   ├── __init__.py   # App factory (create_app), CLI commands, i18n
│   │   │   ├── config.py     # Flask + SQLAlchemy + Babel config
│   │   │   ├── db.py         # Shared SQLAlchemy / Babel extensions
│   │   │   ├── leagues_config.py  # Single source of truth for tracked leagues
│   │   │   ├── models/       # SQLAlchemy models (team, match, elo, prediction, ...)
│   │   │   ├── routes/       # Flask blueprints (main, leagues, teams, matches, stats, api)
│   │   │   ├── static/       # css/, js/, img/ (logos, flags, trophies)
│   │   │   ├── templates/    # base.html, MainPage.html, league_view.html, ...
│   │   │   └── translations/ # Flask-Babel catalogs (pl, en)
│   │   └── local.db          # SQLite database (gitignored)
│   ├── calculations/        # ELO, feature building, prediction pipeline
│   ├── scraping/            # football-data.co.uk ingestion (footballScrap.py)
│   └── main.py              # Interactive data-pipeline CLI menu
├── tests/                   # pytest suite (isolated in-memory SQLite)
├── wsgi.py                  # Canonical launcher (create_app factory)
├── requirements.txt
└── README.md
```

## Setup

```bash
git clone https://github.com/Aleksoooxd/IPZ-Pewniaczki.git
cd IPZ-Pewniaczki
pip install -r requirements.txt
```

## Running

All commands below are run from the **repository root** so the `src` package is
importable. There is a single canonical launcher — `wsgi.py` — which routes
everything through the `create_app` factory in `src/flask_app/app/__init__.py`.

### Web app (development)

```bash
flask --app wsgi run          # reloader + debugger, reads .flaskenv (port 7777)
# or, equivalently:
python wsgi.py
```

### Data pipeline (scraping / ELO / predictions)

```bash
python -m src.main            # interactive menu; also works as `python src/main.py`
```

### Tests

Unit tests live in `tests/` (pytest). They are pure-math where possible
(`calculate_elo_change`, `calculate_consensus`, the dispersion indices) and use
an isolated in-memory SQLite database for the DB-backed `calculate_standings`.

```bash
pip install -r requirements.txt   # pytest is included
python -m pytest                  # from the repository root
```

### Deployment (production)

`app.run()` in `wsgi.py` is the **development** server only — single-threaded
and not hardened. Use a real WSGI server instead. The factory is thread-safe for
multi-threaded servers (see `SQLALCHEMY_ENGINE_OPTIONS` in
`src/flask_app/app/config.py`).

**waitress** (recommended — pure Python, cross-platform, runs on Windows):

```bash
pip install waitress
waitress-serve --call --listen=127.0.0.1:7777 wsgi:create_app
```

**gunicorn** (Linux / POSIX only — not available on Windows):

```bash
pip install gunicorn
gunicorn "wsgi:create_app" --bind 0.0.0.0:7777 --workers 2 --threads 4
```

> **SQLite + workers caveat:** SQLite supports multiple reader/writer
> *threads* but not multiple writer *processes*. With gunicorn use a single
> worker (`--workers 1`) or switch `SQLALCHEMY_DATABASE_URI` to a server-grade
> database (e.g. PostgreSQL) for multi-process deployments. waitress is
> single-process/multi-threaded, so it works with the default SQLite setup.


