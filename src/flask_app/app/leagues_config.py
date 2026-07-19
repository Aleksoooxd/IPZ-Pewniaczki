"""Single source of truth for the tracked football leagues.

Previously the league catalogue was duplicated across several Blueprints
(``routes/leagues.py``, ``routes/teams.py``, ``routes/main.py``,
``routes/stats.py``) and again inside the templates. Adding a league therefore
meant editing six places by hand, which is how the ``"spremier league"`` DB code
ended up mismatched against the ``"ScottishPremierLeague"`` URL code (a bug that
broke team links on Scottish match pages).

Every league is now declared exactly once here. The Blueprints, the scraper and
the templates all derive their maps/lookups from this list, so onboarding a new
league is a one-line change.

Each entry carries:
    url_code  - segment used in URLs, e.g. ``"ScottishPremierLeague"``
    db_code   - value stored in the ``league.code`` column, e.g. ``"spremier league"``
    display   - human-readable name shown in the UI, e.g. ``"Scottish Premiership"``
    flag      - flag/logo basename (without size suffix), e.g. ``"scottish-premiership"``
"""

LEAGUES = [
    {"url_code": "Premierleague",        "db_code": "premier league",     "display": "Premier League",        "flag": "premier-league"},
    {"url_code": "Bundesliga",           "db_code": "bundesliga",        "display": "Bundesliga",           "flag": "bundesliga"},
    {"url_code": "Eredivisie",           "db_code": "eredivisie",        "display": "Eredivisie",           "flag": "eredivisie"},
    {"url_code": "EthnikiKatigoria",     "db_code": "ethniki katigoria", "display": "Ethniki Katigoria",     "flag": "ethniki-katigoria"},
    {"url_code": "FutbolLig1",           "db_code": "futbol ligi 1",     "display": "Futbol Lig 1",         "flag": "futbol-ligi-1"},
    {"url_code": "JupiterLeague",        "db_code": "jupiler league",    "display": "Jupiler League",        "flag": "jupiler-league"},
    {"url_code": "LaLiga",               "db_code": "la liga",           "display": "La Liga",              "flag": "la-liga"},
    {"url_code": "Ligue1",               "db_code": "ligue 1",           "display": "Ligue 1",              "flag": "ligue-1"},
    {"url_code": "LigaI",                "db_code": "liga i",            "display": "Liga I",               "flag": "liga-i"},
    {"url_code": "SerieA",               "db_code": "serie a",           "display": "Serie A",              "flag": "serie-a"},
    {"url_code": "ScottishPremierLeague","db_code": "spremier league",   "display": "Scottish Premiership", "flag": "scottish-premiership"},
]

# url_code -> db_code  (look up the DB row from a URL segment)
URL_TO_DB = {lg["url_code"]: lg["db_code"] for lg in LEAGUES}
# db_code -> url_code  (build links back to team/league pages)
DB_TO_URL = {lg["db_code"]: lg["url_code"] for lg in LEAGUES}
# db_code -> display name (headings, main page)
DB_TO_DISPLAY = {lg["db_code"]: lg["display"] for lg in LEAGUES}
# url_code -> display name (landing / main page)
URL_TO_DISPLAY = {lg["url_code"]: lg["display"] for lg in LEAGUES}
# db_code -> small flag file name (matches page)
DB_TO_FLAG_SMALL = {lg["db_code"]: f"{lg['flag']}-small.png" for lg in LEAGUES}
# db_code -> big flag file name (league view header)
DB_TO_FLAG_BIG = {lg["db_code"]: f"{lg['flag']}-big.png" for lg in LEAGUES}
