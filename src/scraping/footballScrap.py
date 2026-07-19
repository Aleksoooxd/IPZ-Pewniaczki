import numpy as np
import chardet
import requests
import io
import traceback
from concurrent.futures import ThreadPoolExecutor
import datetime
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.flask_app.app.models import (
    FootballMatch, MatchStats, MatchForm,
    Team, League, Season, TeamLeague, FutureMatch,
    MatchOdds, FutureMatchOdds,
)
from src.calculations.helpfunctions import (
    hhi_index, shannon_index, coefficient_of_variation, gini_index, calculate_consensus
)
from src.scraping.team_mapping import load_team_mapping

# Single unified raw -> canonical team-name map (composed from mapping.json).
TEAM_NAME_MAP = load_team_mapping()

pd.set_option('future.no_silent_downcasting', True)

headers = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
    )
}

def build_seasons(now: datetime.datetime = None) -> dict:
    """Build the {season_label: season_code} map for tracked football seasons.

    Pure function of ``now`` (defaults to the current time) so it can be tested
    without depending on module-import side effects, and the reference point can
    be mocked. Seasons run August-to-May; a season starting in August of year Y
    is labelled ``"Y/Y+1"`` with a two-digit code. The function emits consecutive
    seasons backward from the current season down to 2009/2010 (special-cased as
    "0910"), then continues with zero-padded codes for older seasons ending in
    2004/2005.

    Args:
        now (datetime.datetime, optional): Reference point used to determine the
            current season. If None, the system clock (datetime.datetime.now()) is
            used.

    Returns:
        dict: Mapping of season label strings (e.g. ``"2023/2024"``) to their
        two-digit season codes (e.g. ``"2324"``).
    """
    if now is None:
        now = datetime.datetime.now()
    curr_year = (
        (now.year - 1)
        if now.month < 8
        else now.year
    )
    deadline = curr_year - 2009
    deadline2 = curr_year - 2004 - deadline

    seasons = {}
    generate_season_entry = lambda year, offset: {
        f'{year - offset}/{year - offset + 1}': f"{year % 100 - offset}{year % 100 - offset + 1}"
    }
    generate_season_entry_0 = lambda year, offset: {
        f'{year - offset}/{year - offset + 1}': f"0{year % 100 - offset}0{year % 100 - offset + 1}"
    }
    for i in range(deadline):
        seasons.update(generate_season_entry(curr_year, i))
    seasons.update({'2009/2010': '0910'})
    for i in range(deadline2):
        seasons.update(generate_season_entry_0(2008, i))
    return seasons


countries = {
    'en': ['england', 'Premier League'],
    'sp': ['spain', 'La Liga Primera Division'],
    'de': ['germany', 'Bundesliga 1'],
    'it': ['italy', 'Serie A'],
    'fr': ['france', 'Le Championnat'],
    'sc': ['scotland', 'Premier League'],
    'ne': ['netherlands', 'Eredivisie'],
    'be': ['belgium', 'Jupiler League'],
    'po': ['portugal', 'Liga I'],
    'tu': ['turkey', 'Futbol Ligi 1'],
    'gr': ['greece', 'Ethniki Katigoria']
}

# Country key (used to build football-data.co.uk URLs) -> canonical league code
# that get_or_create_league(get_league(df)) stores. Lets us check DB presence
# for a (country, season) pair without downloading the CSV first.
COUNTRY_LEAGUE_CODE = {
    'en': 'premier league',
    'sc': 'spremier league',
    'de': 'bundesliga',
    'it': 'serie a',
    'fr': 'ligue 1',
    'ne': 'eredivisie',
    'be': 'jupiler league',
    'po': 'liga i',
    'tu': 'futbol ligi 1',
    'gr': 'ethniki katigoria',
    'sp': 'la liga',
}

# football-data.co.uk division code (the `Div` column) -> canonical league code.
# Drives both the historical scrape (get_league) and the fixtures pipeline, so
# the set of "tracked" leagues is defined in exactly one place.
DIV_TO_LEAGUE_CODE = {
    'E0': 'premier league',
    'SC0': 'spremier league',
    'D1': 'bundesliga',
    'SP1': 'la liga',
    'I1': 'serie a',
    'F1': 'ligue 1',
    'N1': 'eredivisie',
    'B1': 'jupiler league',
    'P1': 'liga i',
    'T1': 'futbol ligi 1',
    'G1': 'ethniki katigoria',
}


# ---------------------------------------------------------------------------
# Pomocnicze — bez zależności od bazy
# ---------------------------------------------------------------------------

def detect_encoding(byte_content: bytes) -> str:
    """Detect the character encoding of raw byte content.

    Uses the ``chardet`` library to guess the encoding of a byte string (e.g. an
    HTTP response body) so the content can be decoded and parsed correctly.

    Args:
        byte_content (bytes): Raw bytes whose encoding should be detected.

    Returns:
        str: Name of the detected character encoding (e.g. ``"utf-8"``,
        ``"iso-8859-1"``).
    """
    result = chardet.detect(byte_content)
    return result['encoding']


def apply_team_mapping(club_name: str, mapping: dict) -> str:
    """Map a raw club name to its canonical name using a lookup dictionary.

    First normalizes whitespace, then checks for an exact case-sensitive match,
    then a case-insensitive match against the mapping keys. If no match is found
    the normalized (whitespace-cleaned) name is returned unchanged.

    Args:
        club_name (str): The raw team name scraped from a source.
        mapping (dict): Mapping of raw/alternate names (str) to canonical names
            (str).

    Returns:
        str: The canonical team name if a match was found, otherwise the
        whitespace-normalized ``club_name``.
    """
    cleaned_name = ' '.join(club_name.strip().split())
    if cleaned_name in mapping:
        return mapping[cleaned_name]
    lower_name = cleaned_name.lower()
    for key in mapping:
        if key.lower() == lower_name:
            return mapping[key]
    return cleaned_name


def _odds_from_row(row) -> dict:
    """Extract average/best decimal odds (H/D/A) from a scraped match row.

    Reads the ``Avg*`` / ``Max*`` bookmaker-summary columns, coercing each to a
    float and treating missing / non-positive / placeholder values as ``None``
    (a stake of 1.0 would be meaningless). Returns a dict with ``avg_home``,
    ``avg_draw``, ``avg_away``, ``best_home``, ``best_draw``, ``best_away``.

    Args:
        row (pandas.Series): A row from a football-data.co.uk match CSV.

    Returns:
        dict: Odds keyed by outcome; ``None`` where unavailable.
    """
    def _coerce(col):
        """Coerce one odds column to float, treating invalid values as ``None``.

        A stake of 1.0 would be meaningless, so any value that is not strictly
        greater than 1.0 (missing, non-numeric, or a placeholder) is returned as
        ``None`` so the value-EV calculator can skip that outcome.

        Args:
            col (str): Odds column name (e.g. ``"AvgH"`` / ``"MaxA"``).

        Returns:
            float or None: The parsed decimal odds, or ``None`` when unavailable.
        """
        val = row.get(col) if hasattr(row, "get") else None
        try:
            val = float(val)
        except (TypeError, ValueError):
            return None
        return val if val and val > 1.0 else None
    return {
        "avg_home": _coerce("AvgH"), "avg_draw": _coerce("AvgD"), "avg_away": _coerce("AvgA"),
        "best_home": _coerce("MaxH"), "best_draw": _coerce("MaxD"), "best_away": _coerce("MaxA"),
    }


def correct_date_format(val):
    """Normalize two-digit-year dates to four-digit-year dates.

    football-data.co.uk encodes dates as ``DDMMYY`` (8 characters). This helper
    expands the two-digit year to a full four-digit year prefixed with ``"20"``,
    producing ``DDMMYYYY`` so pandas can parse it unambiguously. Values that are
    not 8-character strings are returned unchanged.

    Args:
        val (str or Any): A date token; expected to be an 8-character ``DDMMYY``
            string.

    Returns:
        str or Any: The reformatted ``DDMMYYYY`` string when ``val`` is an
        8-character string; otherwise ``val`` unchanged.
    """
    if isinstance(val, str) and len(val) == 8:
        return val[:6] + "20" + val[6:]
    return val


def get_season(date):
    """Return the football season label for a given date.

    Seasons start in August. For a date in August or later, the season is
    ``"<year>/<last-two-digits-of-year+1>"``; for January-July it is the previous
    year wrapped across the boundary (e.g. March 2024 -> ``"2023/24"``).

    Args:
        date (pandas.Timestamp or datetime.date): The date whose season is needed.

    Returns:
        str or None: The season label (e.g. ``"2023/24"``), or None when ``date``
        is null/NaN.

    Raises:
        ValueError: If ``date`` is not a pandas.Timestamp, datetime.date, or null.
    """
    if pd.isnull(date):
        return None
    if not isinstance(date, (pd.Timestamp, datetime.date)):
        raise ValueError("The 'date' parameter must be a pandas.Timestamp or datetime.date object.")
    year = date.year
    # Season starts in August, consistent with _current_season_name() and build_seasons().
    if date.month >= 8:
        start_year, end_year = year, year + 1
    else:
        start_year, end_year = year - 1, year
    return f"{start_year}/{end_year % 100:02d}"


def get_league(df: pd.DataFrame):
    """Determine the canonical league code for the rows in a DataFrame.

    Inspects the ``Div`` column (football-data.co.uk division code). If the
    DataFrame has no rows, returns None. Otherwise it returns the canonical
    league code for the first/only division via DIV_TO_LEAGUE_CODE, falling back
    to the raw division code when no mapping exists.

    Args:
        df (pd.DataFrame): DataFrame containing a ``Div`` column.

    Returns:
        str or None: Canonical league code, the raw division code if unmapped, or
        None when the DataFrame has no rows.
    """
    leagues = df['Div'].unique()
    if len(leagues) == 0:
        return None
    league = leagues[0]
    return DIV_TO_LEAGUE_CODE.get(league, league)


def get_seasons(df: pd.DataFrame):
    """Return the single season value present in the DataFrame.

    Assumes the DataFrame contains rows for exactly one season. Returns the first
    unique value of the ``Season`` column, or None if the column is empty.

    Args:
        df (pd.DataFrame): DataFrame expected to contain a ``Season`` column.

    Returns:
        Any or None: The unique season value, or None when there are no rows.
    """
    unique = df['Season'].unique()
    return unique[0] if len(unique) > 0 else None


# ---------------------------------------------------------------------------
# Transformacje DataFrame — bez zależności od bazy
# ---------------------------------------------------------------------------

def add_matchday_to_season(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-team matchday numbers and a canonical round for each match.

    The matchday for a team is the number of matches it has played so far
    (home or away), including the current one -- computed as a per-(season, team)
    cumulative count via a vectorized melt/cumcount. ``Round`` is the later of the
    two sides' progress (stable when the schedule is unsynced). The input is
    sorted by Season and Date first.

    Args:
        df (pd.DataFrame): Match DataFrame containing at least ``Season``,
            ``Date``, ``HomeTeam`` and ``AwayTeam`` columns.

    Returns:
        pd.DataFrame: A copy of the input with added ``HomeMatchday``,
        ``AwayMatchday`` and ``Round`` columns.
    """
    # Matchday for a team == how many matches it has played so far (home or away),
    # including the current one. That is a per-(season, team) cumulative count,
    # which we compute vectorized by melting home/away into a long table,
    # sorting by match order, and taking a grouped cumcount.
    df = df.sort_values(by=['Season', 'Date']).reset_index(drop=True).copy()
    df['_order'] = np.arange(len(df))

    long = pd.DataFrame({
        'Season': np.concatenate([df['Season'].to_numpy(), df['Season'].to_numpy()]),
        'team': np.concatenate([df['HomeTeam'].to_numpy(), df['AwayTeam'].to_numpy()]),
        'order': np.concatenate([df['_order'].to_numpy(), df['_order'].to_numpy()]),
        'role': np.concatenate([np.full(len(df), 'H'), np.full(len(df), 'A')]),
    })
    long = long.sort_values(['Season', 'order'])
    # +1 because the first appearance is matchday 1, not 0.
    long['matchday'] = long.groupby(['Season', 'team']).cumcount() + 1

    pivot = long.pivot(index='order', columns='role', values='matchday')
    df['HomeMatchday'] = pivot['H'].reindex(df['_order']).to_numpy()
    df['AwayMatchday'] = pivot['A'].reindex(df['_order']).to_numpy()
    # Canonical round = the later of the two sides' progress. Equivalent to the
    # correct "both sides within N" standings filter, and stable when the schedule
    # is unsynced (rescheduled games).
    df['Round'] = df[['HomeMatchday', 'AwayMatchday']].max(axis=1)
    return df.drop(columns=['_order'])


def calculate_is_surprise(df: pd.DataFrame) -> pd.DataFrame:
    """Compute bookmaker-consensus "surprise" flags for each match result.

    Ensures all required base and bookmaker-odds columns exist (filling missing
    bookmaker columns with 1.0), computes per-result average odds across all
    bookmakers, and flags a match as a surprise when the actual result (home win,
    draw, away win) had higher average odds than both alternative outcomes. The
    per-result flags and their integer sum (``isSurprise``) are returned.

    Args:
        df (pd.DataFrame): Match DataFrame expected to contain result (``FTR``),
            team/matchday columns, and bookmaker odds columns ending in H/D/A.

    Returns:
        pd.DataFrame: The input augmented with ``isSurprise_H``, ``isSurprise_D``,
        ``isSurprise_A``, and ``isSurprise`` columns.
    """
    selected_columns = [
        'Div', 'Season', 'Date', 'HomeTeam', 'AwayTeam', 'FTR',
        'HomeMatchday', 'AwayMatchday', 'FTHG', 'FTAG', 'Round'
    ]
    all_bookmaker_columns = [
        'B365H', 'B365D', 'B365A', 'BFH', 'BFD', 'BFA', 'BSH', 'BSD', 'BSA',
        'BWH', 'BWD', 'BWA', 'GBH', 'GBD', 'GBA', 'IWH', 'IWD', 'IWA',
        'LBH', 'LBD', 'LBA', 'PSH', 'PSD', 'PSA', 'SOH', 'SOD', 'SOA',
        'SBH', 'SBD', 'SBA', 'SJH', 'SJD', 'SJA', 'SYH', 'SYD', 'SYA',
        'VCH', 'VCD', 'VCA', 'WHH', 'WHD', 'WHA'
    ]
    # Bookmaker average / best-odds summary columns (Avg*/Max*) are needed
    # downstream to persist odds for the value-bet calculator, but must NOT be
    # filled with the 1.0 placeholder used for missing individual-bookmaker
    # odds. Detach them, run the surprise calc, then re-attach them untouched.
    odds_summary_cols = ['AvgH', 'AvgD', 'AvgA', 'MaxH', 'MaxD', 'MaxA']
    kept_odds = df[[c for c in odds_summary_cols if c in df.columns]].copy()

    required_columns = selected_columns + all_bookmaker_columns
    new_columns = {col: pd.NA for col in required_columns if col not in df.columns}
    df = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)
    df = df[required_columns].fillna(1.0)
    if not kept_odds.empty:
        df = pd.concat([df, kept_odds], axis=1)

    home_stakeholders = [col for col in df.columns if col.endswith("H")]
    draw_stakeholders = [col for col in df.columns if col.endswith("D")]
    away_stakeholders = [col for col in df.columns if col.endswith("A")]

    df['Avg_H'] = df[home_stakeholders].mean(axis=1)
    df['Avg_D'] = df[draw_stakeholders].mean(axis=1)
    df['Avg_A'] = df[away_stakeholders].mean(axis=1)

    df['isSurprise_H'] = (
        (df['FTR'] == 'H') & (df['Avg_H'] > df[['Avg_D', 'Avg_A']].max(axis=1))
    ).astype(int)
    df['isSurprise_D'] = (
        (df['FTR'] == 'D') & (df['Avg_D'] > df[['Avg_H', 'Avg_A']].max(axis=1))
    ).astype(int)
    df['isSurprise_A'] = (
        (df['FTR'] == 'A') & (df['Avg_A'] > df[['Avg_H', 'Avg_D']].max(axis=1))
    ).astype(int)
    df['isSurprise'] = df['isSurprise_H'] + df['isSurprise_D'] + df['isSurprise_A']
    df = df.drop(columns=['Avg_H', 'Avg_D', 'Avg_A'])
    return df


def create_placement_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Compute running standings, form and goals columns for each match.

    Iterates season-by-season, match-by-match (each match's standings depend on
    all prior matches) and accumulates, into NumPy arrays, each team's current
    league placement, last-3 / last-5 / season-to-date form points, last-3 /
    last-5 / season-to-date goals scored, and the previous season's final
    placement (HTLSP / ATLSP). Results are assigned back to the DataFrame in one
    shot. The ``FTHG``/``FTAG`` columns are coerced to numeric first.

    Args:
        dataframe (pd.DataFrame): Match DataFrame with ``Season``, ``Date``,
            ``HomeMatchday``, ``HomeTeam``, ``AwayTeam``, ``FTHG``, ``FTAG`` and
            ``FTR`` columns.

    Returns:
        pd.DataFrame: The input with added placement/form/goal columns
        (``HomeTeamPlacement``, ``HomeForm3``, ``HomeGoalsSeason``, etc.).
    """
    cols_to_init = [
        'HomeTeamPlacement', 'AwayTeamPlacement', 'HomeForm3', 'HomeForm5',
        'HomeFormSeason', 'AwayForm3', 'AwayForm5', 'AwayFormSeason',
        'HomeGoals3', 'HomeGoals5', 'HomeGoalsSeason', 'AwayGoals3',
        'AwayGoals5', 'AwayGoalsSeason', 'HTLSP', 'ATLSP'
    ]
    for col in cols_to_init:
        dataframe[col] = 0

    dataframe['FTHG'] = pd.to_numeric(dataframe['FTHG'], errors='coerce')
    dataframe['FTAG'] = pd.to_numeric(dataframe['FTAG'], errors='coerce')

    # The per-match placement/form computations are inherently sequential (each
    # match's standings depend on all prior matches), so we keep the row loop but
    # accumulate results into NumPy arrays and assign the columns in one shot at
    # the end — instead of the very slow df.loc[index, col] = ... write pattern.
    dataframe = dataframe.reset_index(drop=True)
    n = len(dataframe)

    home_team_placement = np.zeros(n, dtype=int)
    away_team_placement = np.zeros(n, dtype=int)
    home_form3 = np.zeros(n, dtype=int)
    home_form5 = np.zeros(n, dtype=int)
    home_form_season = np.zeros(n, dtype=int)
    away_form3 = np.zeros(n, dtype=int)
    away_form5 = np.zeros(n, dtype=int)
    away_form_season = np.zeros(n, dtype=int)
    home_goals3 = np.zeros(n, dtype=int)
    home_goals5 = np.zeros(n, dtype=int)
    home_goals_season = np.zeros(n, dtype=int)
    away_goals3 = np.zeros(n, dtype=int)
    away_goals5 = np.zeros(n, dtype=int)
    away_goals_season = np.zeros(n, dtype=int)
    htlsp = np.zeros(n, dtype=int)
    atlsp = np.zeros(n, dtype=int)
    home_draw_ratio = np.zeros(n, dtype=float)
    away_draw_ratio = np.zeros(n, dtype=float)
    home_league_draw_ratio = np.zeros(n, dtype=float)
    away_league_draw_ratio = np.zeros(n, dtype=float)

    previous_season_final_placements = {}

    for season, season_df_orig in dataframe.groupby('Season'):
        season_df = season_df_orig.sort_values(by=['Date', 'HomeMatchday']).copy()
        standings = {}
        team_history = {}
        league_draws = 0
        league_matches = 0

        for index, row in season_df.iterrows():
            home_team = row['HomeTeam']
            away_team = row['AwayTeam']

            for team in (home_team, away_team):
                if team not in standings:
                    standings[team] = {'points': 0, 'goal_diff': 0, 'goals_scored': 0, 'goals_against': 0}
                if team not in team_history:
                    team_history[team] = {'results_pts': [], 'goals_for': [], 'draws': 0}

            sorted_teams = sorted(
                standings.keys(),
                key=lambda t: (-standings[t]['points'], -standings[t]['goal_diff'], -standings[t]['goals_scored'], t)
            )
            placement_map = {team: i + 1 for i, team in enumerate(sorted_teams)}

            home_hist = team_history[home_team]
            away_hist = team_history[away_team]

            home_team_placement[index] = placement_map.get(home_team, len(standings) + 1)
            away_team_placement[index] = placement_map.get(away_team, len(standings) + 1)

            # Draw-tendency ratios as of this match (before its own result is
            # counted): team ratio = team draws / team matches played so far;
            # league ratio = league draws / league matches played so far.
            home_m = len(home_hist['results_pts'])
            away_m = len(away_hist['results_pts'])
            home_draw_ratio[index] = (home_hist['draws'] / home_m) if home_m else 0.0
            away_draw_ratio[index] = (away_hist['draws'] / away_m) if away_m else 0.0
            league_ratio = (league_draws / league_matches) if league_matches else 0.0
            home_league_draw_ratio[index] = league_ratio
            away_league_draw_ratio[index] = league_ratio
            home_form3[index] = sum(home_hist['results_pts'][-3:])
            home_form5[index] = sum(home_hist['results_pts'][-5:])
            home_form_season[index] = sum(home_hist['results_pts'])
            home_goals3[index] = sum(home_hist['goals_for'][-3:])
            home_goals5[index] = sum(home_hist['goals_for'][-5:])
            home_goals_season[index] = sum(home_hist['goals_for'])
            away_form3[index] = sum(away_hist['results_pts'][-3:])
            away_form5[index] = sum(away_hist['results_pts'][-5:])
            away_form_season[index] = sum(away_hist['results_pts'])
            away_goals3[index] = sum(away_hist['goals_for'][-3:])
            away_goals5[index] = sum(away_hist['goals_for'][-5:])
            away_goals_season[index] = sum(away_hist['goals_for'])
            htlsp[index] = previous_season_final_placements.get(home_team, 0)
            atlsp[index] = previous_season_final_placements.get(away_team, 0)

            fthg, ftag = row['FTHG'], row['FTAG']
            standings[home_team]['goals_scored'] += fthg
            standings[home_team]['goals_against'] += ftag
            standings[home_team]['goal_diff'] = (
                standings[home_team]['goals_scored'] - standings[home_team]['goals_against']
            )
            standings[away_team]['goals_scored'] += ftag
            standings[away_team]['goals_against'] += fthg
            standings[away_team]['goal_diff'] = (
                standings[away_team]['goals_scored'] - standings[away_team]['goals_against']
            )

            home_points, away_points = 0, 0
            if row['FTR'] == 'H':
                home_points = 3
            elif row['FTR'] == 'A':
                away_points = 3
            elif row['FTR'] == 'D':
                home_points, away_points = 1, 1

            standings[home_team]['points'] += home_points
            standings[away_team]['points'] += away_points
            team_history[home_team]['results_pts'].append(home_points)
            team_history[home_team]['goals_for'].append(fthg)
            team_history[away_team]['results_pts'].append(away_points)
            team_history[away_team]['goals_for'].append(ftag)
            if row['FTR'] == 'D':
                team_history[home_team]['draws'] += 1
                team_history[away_team]['draws'] += 1
            league_matches += 1
            if row['FTR'] == 'D':
                league_draws += 1

        final_sorted_teams = sorted(
            standings.keys(),
            key=lambda t: (-standings[t]['points'], -standings[t]['goal_diff'], -standings[t]['goals_scored'], t)
        )
        previous_season_final_placements = {team: i + 1 for i, team in enumerate(final_sorted_teams)}

    dataframe['HomeTeamPlacement'] = home_team_placement
    dataframe['AwayTeamPlacement'] = away_team_placement
    dataframe['HomeForm3'] = home_form3
    dataframe['HomeForm5'] = home_form5
    dataframe['HomeFormSeason'] = home_form_season
    dataframe['AwayForm3'] = away_form3
    dataframe['AwayForm5'] = away_form5
    dataframe['AwayFormSeason'] = away_form_season
    dataframe['HomeGoals3'] = home_goals3
    dataframe['HomeGoals5'] = home_goals5
    dataframe['HomeGoalsSeason'] = home_goals_season
    dataframe['AwayGoals3'] = away_goals3
    dataframe['AwayGoals5'] = away_goals5
    dataframe['AwayGoalsSeason'] = away_goals_season
    dataframe['HTLSP'] = htlsp
    dataframe['ATLSP'] = atlsp
    dataframe['HomeDrawRatio'] = home_draw_ratio
    dataframe['AwayDrawRatio'] = away_draw_ratio
    dataframe['HomeLeagueDrawRatio'] = home_league_draw_ratio
    dataframe['AwayLeagueDrawRatio'] = away_league_draw_ratio
    return dataframe


def calculate_statistics_and_consensus(data: pd.DataFrame) -> pd.DataFrame:
    """Compute per-result bookmaker dispersion statistics and a consensus score.

    For each result type (H/D/A), builds a numeric matrix of all bookmaker odds,
    then computes the mean, standard deviation, Shannon index, coefficient of
    variation, Gini index and HHI index per row (dispersion/concentration
    measures of bookmaker agreement). Finally appends a ``Consensus`` column via
    ``calculate_consensus`` over the per-result odds.

    Args:
        data (pd.DataFrame): Match DataFrame containing the bookmaker odds columns
            used by ``AllBookmakers`` (e.g. ``B365H``, ``WHH``).

    Returns:
        pd.DataFrame: The input augmented with ``{H,D,A}_Mean``, ``_Std``,
        ``_Shannon``, ``_CV``, ``_Gini``, ``_HHI`` and ``Consensus`` columns.
    """
    bookmakers_columns = {
        "AllBookmakers": {
            "H": ["B365H", "BFH", "BSH", "BWH", "GBH", "IWH", "LBH", "PSH", "SOH", "SBH", "SJH", "SYH", "VCH", "WHH"],
            "D": ["B365D", "BFD", "BSD", "BWD", "GBD", "IWD", "LBD", "PSD", "SOD", "SBD", "SJD", "SYD", "VCD", "WHD"],
            "A": ["B365A", "BFA", "BSA", "BWA", "GBA", "IWA", "LBA", "PSA", "SOA", "SBA", "SJA", "SYA", "VCA", "WHA"]
        }
    }
    for result_type, cols in bookmakers_columns["AllBookmakers"].items():
        # Numeric matrix (n_rows x n_bookmakers) once, then operate on the
        # underlying NumPy array — no per-row Series, no df.loc writes.
        numeric = data[cols].apply(pd.to_numeric, errors='coerce').to_numpy(dtype=float)
        mask = ~np.isnan(numeric)
        has_valid = mask.any(axis=1)

        mean = np.full(len(data), np.nan)
        std = np.full(len(data), np.nan)
        if has_valid.any():
            masked_valid = np.where(mask[has_valid], numeric[has_valid], np.nan)
            mean[has_valid] = np.nanmean(masked_valid, axis=1)
            std[has_valid] = np.nanstd(masked_valid, axis=1)

        # Shannon/CV/Gini/HHI depend on the ragged set of per-row valid values,
        # so loop over rows on the fast NumPy arrays (no DataFrame fragmentation).
        shannon = np.full(len(data), np.nan)
        cv = np.full(len(data), np.nan)
        gini = np.full(len(data), np.nan)
        hhi = np.full(len(data), np.nan)
        for r in range(numeric.shape[0]):
            if not has_valid[r]:
                continue
            vals = numeric[r][mask[r]]
            shannon[r] = shannon_index(vals)
            cv[r] = coefficient_of_variation(vals)
            gini[r] = gini_index(vals)
            hhi[r] = hhi_index(vals)

        data[f"{result_type}_Mean"] = np.round(mean, 4)
        data[f"{result_type}_Std"] = np.round(std, 4)
        data[f"{result_type}_Shannon"] = shannon
        data[f"{result_type}_CV"] = cv
        data[f"{result_type}_Gini"] = gini
        data[f"{result_type}_HHI"] = hhi

    data['Consensus'] = data.apply(
        calculate_consensus, axis=1, columns=bookmakers_columns["AllBookmakers"]
    )
    return data


# ---------------------------------------------------------------------------
# Operacje na bazie — przyjmują session z zewnątrz
# ---------------------------------------------------------------------------

def _upsert_get_or_create(session: Session, model, unique_col: str, value):
    """Get an existing ORM row by unique column or create it, race-safe.

    Used for shared lookup rows (leagues, seasons) that multiple concurrent
    worker threads may try to insert at the same time. A naive SELECT-then-INSERT
    would race and trip the UNIQUE constraint, so this uses a SQLite upsert with
    ON CONFLICT DO NOTHING (the second writer's insert becomes a no-op) followed
    by a commit and a re-read to guarantee both workers observe the canonical
    committed row.

    Args:
        session (Session): Active SQLAlchemy session.
        model: ORM model class to query/insert.
        unique_col (str): Name of the unique column used for the lookup/conflict
            target.
        value: Value to match against / insert into ``unique_col``.

    Returns:
        The ORM instance (existing or freshly inserted) for ``value``.
    """
    existing = session.execute(
        select(model).where(getattr(model, unique_col) == value)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    stmt = sqlite_insert(model).values({unique_col: value})
    stmt = stmt.on_conflict_do_nothing(index_elements=[unique_col])
    session.execute(stmt)
    session.commit()  # publish + take a fresh snapshot before the re-read
    return session.execute(
        select(model).where(getattr(model, unique_col) == value)
    ).scalar_one()


def get_or_create_league(session: Session, league_name: str) -> League:
    """Get or create a League row by its canonical code, race-safe.

    Args:
        session (Session): Active SQLAlchemy session.
        league_name (str): Canonical league code (e.g. ``"premier league"``).

    Returns:
        League: The existing or newly created League instance.
    """
    return _upsert_get_or_create(session, League, 'code', league_name)


def get_or_create_season(session: Session, season_name: str) -> Season:
    """Get or create a Season row by its name, race-safe.

    Args:
        session (Session): Active SQLAlchemy session.
        season_name (str): Season label (e.g. ``"2023/24"``).

    Returns:
        Season: The existing or newly created Season instance.
    """
    return _upsert_get_or_create(session, Season, 'name', season_name)


# ---------------------------------------------------------------------------
# Future fixtures — single CSV of upcoming matches across all divisions
# ---------------------------------------------------------------------------

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"


def download_fixtures_csv():
    """Download football-data.co.uk's fixtures.csv into a DataFrame.

    Performs an HTTP GET of the single upcoming-fixtures CSV (no database
    access). On any network exception, non-200 status, or CSV parse failure the
    function prints a message and returns None rather than raising.

    Returns:
        pandas.DataFrame or None: Parsed fixtures CSV, or None on HTTP/parse
        failure.
    """
    try:
        response = requests.get(FIXTURES_URL, headers=headers, timeout=60)
    except requests.RequestException as e:
        print(f"Failed to download fixtures: {e}")
        return None
    if response.status_code != 200:
        print(f"Failed to download fixtures: HTTP {response.status_code}")
        return None
    try:
        enc = detect_encoding(response.content)
        return pd.read_csv(
            io.StringIO(response.content.decode(enc)),
            encoding=enc, low_memory=False, on_bad_lines='skip'
        )
    except Exception as e:
        print(f"Failed to parse fixtures CSV: {e}")
        return None


def _delete_past_fixtures(session: Session, as_of: datetime.date) -> int:
    """Delete FutureMatch rows dated strictly before a reference date.

    Fixtures that have already been played are no longer "future" and must not
    linger in the prediction set (they would otherwise be predicted as if
    upcoming). Their ``PredictedFuture`` rows are removed first so they do not
    become orphans (SQLite does not enforce the FK, and a bulk query delete does
    not trigger ORM cascades). Deletion is performed with
    ``synchronize_session=False``.

    Args:
        session (Session): Active SQLAlchemy session.
        as_of (datetime.date): Reference date; rows with date < as_of are removed.

    Returns:
        int: Number of FutureMatch rows deleted.
    """
    from src.flask_app.app.models import PredictedFuture

    stale_ids = [
        mid for (mid,) in session.query(FutureMatch.match_id)
        .filter(FutureMatch.date < as_of).all()
    ]
    if not stale_ids:
        return 0
    # Remove dangling predictions before dropping the matches they point at.
    session.query(PredictedFuture).filter(
        PredictedFuture.match_id.in_(stale_ids)
    ).delete(synchronize_session=False)
    deleted = session.query(FutureMatch).filter(
        FutureMatch.match_id.in_(stale_ids)
    ).delete(synchronize_session=False)
    return deleted


def process_fixtures(session: Session, df: pd.DataFrame, as_of: datetime.date = None):
    """Store upcoming fixtures for tracked leagues into FutureMatch.

    Network-free (takes a DataFrame) so it is unit-testable. Rows whose ``Div``
    is not in DIV_TO_LEAGUE_CODE are dropped, rows with unparseable or past dates
    are skipped, and any existing FutureMatch row whose date is in the past is
    deleted so stale fixtures never pollute the prediction set. Re-running is
    idempotent: fixtures already present (by home/away/date within
    league+season) are skipped.

    Args:
        session (Session): Active SQLAlchemy session.
        df (pandas.DataFrame): Raw fixtures CSV with ``Div``, ``HomeTeam``,
            ``AwayTeam``, ``Date`` (and optionally ``Time``) columns.
        as_of (datetime.date, optional): Reference "today" date. Past fixtures are
            skipped/deleted. Defaults to datetime.date.today().

    Returns:
        tuple[int, int, int]: ``(inserted, skipped, errors)`` counts.
    """
    if as_of is None:
        as_of = datetime.date.today()

    # Drop stale fixtures first — cleanup runs even when there is no new data.
    deleted = _delete_past_fixtures(session, as_of)
    if deleted:
        session.commit()

    if df is None or df.empty:
        return 0, 0, 0

    df = df.copy()
    required = ['Div', 'HomeTeam', 'AwayTeam', 'Date']
    df = df.dropna(subset=[c for c in required if c in df.columns])
    if df.empty:
        return 0, 0, 0

    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    # Split into rows we can place vs. rows with an unparseable date.
    unparsed = df['Date'].isna()
    skipped = int(unparsed.sum())
    df = df[~unparsed].copy()
    if df.empty:
        return 0, skipped, 0

    # Past fixtures are no longer "future" — do not insert them.
    past = df['Date'].dt.date < as_of
    skipped += int(past.sum())
    df = df[~past].copy()
    if df.empty:
        return 0, skipped, 0

    df['HomeTeam'] = df['HomeTeam'].apply(lambda x: apply_team_mapping(x, TEAM_NAME_MAP))
    df['AwayTeam'] = df['AwayTeam'].apply(lambda x: apply_team_mapping(x, TEAM_NAME_MAP))
    df['league_code'] = df['Div'].map(DIV_TO_LEAGUE_CODE)

    tracked = df[df['league_code'].notna()].copy()
    skipped += int((df['league_code'].isna()).sum())  # untracked divisions
    if tracked.empty:
        return 0, skipped, 0

    tracked['season_label'] = tracked['Date'].apply(get_season)

    # Resolve distinct leagues / seasons / teams up front (conflict-safe).
    league_map = {
        code: get_or_create_league(session, code)
        for code in tracked['league_code'].unique()
    }
    season_map = {
        label: get_or_create_season(session, label)
        for label in tracked['season_label'].unique()
    }
    team_names = pd.concat([tracked['HomeTeam'], tracked['AwayTeam']]).dropna().unique()
    teams_by_name = resolve_teams(session, team_names)

    # Existing fixtures -> skip on re-run (dedup by home/away/date within league+season).
    league_ids = [lg.league_id for lg in league_map.values()]
    season_ids = [s.season_id for s in season_map.values()]
    existing_keys = set()
    if league_ids and season_ids:
        for fm in session.query(FutureMatch).filter(
            FutureMatch.league_id.in_(league_ids),
            FutureMatch.season_id.in_(season_ids),
        ):
            existing_keys.add((fm.home_team_id, fm.away_team_id, fm.date))

    inserted = errors = 0
    for _, row in tracked.iterrows():
        try:
            home = teams_by_name.get(row['HomeTeam'])
            away = teams_by_name.get(row['AwayTeam'])
            if home is None or away is None:
                skipped += 1
                continue
            lg = league_map[row['league_code']]
            season = season_map[row['season_label']]
            date_val = row['Date'].date()
            key = (home.team_id, away.team_id, date_val)
            if key in existing_keys:
                skipped += 1
                continue
            fm = FutureMatch(
                league_id=lg.league_id,
                season_id=season.season_id,
                date=date_val,
                time=str(row['Time']) if pd.notna(row.get('Time')) else None,
                home_team_id=home.team_id,
                away_team_id=away.team_id,
            )
            session.add(fm)
            session.flush()
            odds_dict = _odds_from_row(row)
            if any(odds_dict.values()):
                fm.future_odds = FutureMatchOdds(fetched_at=as_of, **odds_dict)
            existing_keys.add(key)
            inserted += 1
        except Exception as e:
            errors += 1
            print(f"Error inserting fixture {row.get('HomeTeam')} vs "
                  f"{row.get('AwayTeam')}: {e}")

    session.commit()
    return inserted, skipped, errors


def scrape_fixtures(session: Session):
    """Download fixtures.csv and persist upcoming matches for tracked leagues.

    Convenience orchestrator: downloads the fixtures CSV via
    ``download_fixtures_csv`` and stores it with ``process_fixtures``, printing a
    summary line.

    Args:
        session (Session): Active SQLAlchemy session.

    Returns:
        tuple[int, int, int]: ``(inserted, skipped, errors)`` counts returned by
        ``process_fixtures``.
    """
    df = download_fixtures_csv()
    inserted, skipped, errors = process_fixtures(session, df)
    print(f"Fixtures: inserted={inserted}, skipped={skipped}, errors={errors}")
    return inserted, skipped, errors



def resolve_teams(session: Session, names) -> dict:
    """Ensure a Team row exists for each name, returning a name->Team map.

    Teams are shared across leagues/seasons, so concurrent scrape workers (up to
    6 threads against one SQLite file) may try to INSERT the same team name
    simultaneously. A plain get-or-create+INSERT would race and trip
    UNIQUE(team.name); the SQLite upsert with ON CONFLICT DO NOTHING makes it
    safe, and the re-read afterwards returns the canonical committed rows
    regardless of which worker won the insert.

    Args:
        session (Session): Active SQLAlchemy session.
        names (Iterable[str]): Team names to ensure exist. Falsy/empty names are
            ignored.

    Returns:
        dict: Mapping of team name (str) to its Team ORM instance.
    """
    unique_names = sorted({n for n in names if n})
    if not unique_names:
        return {}
    stmt = sqlite_insert(Team).values([{'name': n} for n in unique_names])
    stmt = stmt.on_conflict_do_nothing(index_elements=['name'])
    session.execute(stmt)
    session.commit()  # publish + take a fresh snapshot before the re-read
    return {
        t.name: t
        for t in session.query(Team).filter(Team.name.in_(unique_names))
    }


# ---------------------------------------------------------------------------
# Scraping — funkcje przyjmują session z zewnątrz
# ---------------------------------------------------------------------------

def get_data_from_top_11(
    session: Session,
    countryInfo: list,
    seasonCode: str,
):
    """Download, transform and persist all matches for one league-season.

    Fetches the football-data.co.uk match CSV for the given country and season
    code, cleans/rename columns, parses dates, maps team names to canonical
    names, then enriches the DataFrame with matchday, surprise, placement/form
    and bookmaker-statistics columns. Persists leagues, seasons, teams,
    TeamLeague links, FootballMatch rows (inserting new or updating existing),
    and their MatchStats/MatchForm children. Matches already present as
    FutureMatch are removed. Finally assigns the season champion.

    Args:
        session (Session): Active SQLAlchemy session (with Flask app context).
        countryInfo (list): Two-element list ``[country_slug, league_label]``
            used to build the source URL (``country_slug + "m.php"``) and find the
            season link.
        seasonCode (str): Two-digit season code (e.g. ``"2324"``) selecting the
            download file.

    Returns:
        None: Persists data via the session; prints progress/error messages.
    """
    url = f'https://www.football-data.co.uk/{countryInfo[0]}m.php'
    with requests.Session() as req_session:
        response = req_session.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to load page {url}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        all_a_tags = soup.find('a', string=f'{countryInfo[1]}')
        if not all_a_tags:
            print(f"Link for {countryInfo[1]} {seasonCode} not found")
            return

        download_link = all_a_tags.get('href').split('/')
        download_link[1] = f'{seasonCode}'
        download_link = '/'.join(download_link)
        download_url = f'https://www.football-data.co.uk/{download_link}'

        download_response = req_session.get(download_url, headers=headers)
        if download_response.status_code != 200:
            print(f"Failed to load page {download_url}")
            return

    try:
        enc = detect_encoding(download_response.content)
        df = pd.read_csv(
            io.StringIO(download_response.content.decode(enc)),
            encoding=enc, low_memory=False, on_bad_lines='skip'
        )
        if "HT" in df.columns:
            df.rename(columns={'HT': 'HomeTeam', 'AT': 'AwayTeam'}, inplace=True)

        df.dropna(axis=1, how='all', inplace=True)
        df.dropna(axis=0, how='all', inplace=True)
        df.dropna(axis=0, how='any', subset=['Div', 'FTR'], inplace=True)

        df["Date"] = df["Date"].apply(correct_date_format)
        df["Date"] = pd.to_datetime(df["Date"], errors='coerce', dayfirst=True)
        df['Season'] = df['Date'].apply(get_season)
        df["HomeTeam"] = df["HomeTeam"].apply(lambda x: apply_team_mapping(x, TEAM_NAME_MAP))
        df["AwayTeam"] = df["AwayTeam"].apply(lambda x: apply_team_mapping(x, TEAM_NAME_MAP))

        df = add_matchday_to_season(df)
        df = calculate_is_surprise(df)
        df = create_placement_columns(df)
        df = calculate_statistics_and_consensus(df)
        df = df.sort_values(by='Date')

        league = get_or_create_league(session, get_league(df))
        season_obj = get_or_create_season(session, get_seasons(df))
        session.commit()

        # ---- Pre-load / create teams (conflict-safe across concurrent workers) ----
        teams_by_name = resolve_teams(
            session,
            pd.concat([df['HomeTeam'], df['AwayTeam']]).dropna().unique(),
        )

        needed_tl = {
            (t.team_id, league.league_id, season_obj.season_id)
            for t in teams_by_name.values()
        }
        existing_tl = set()
        if needed_tl:
            existing_tl = {
                (tl.team_id, tl.league_id, tl.season_id)
                for tl in session.query(TeamLeague).filter(
                    TeamLeague.team_id.in_([k[0] for k in needed_tl]),
                    TeamLeague.league_id == league.league_id,
                    TeamLeague.season_id == season_obj.season_id,
                )
            }
        missing_tl = [
            TeamLeague(team_id=tid, league_id=lid, season_id=sid)
            for (tid, lid, sid) in needed_tl
            if (tid, lid, sid) not in existing_tl
        ]
        if missing_tl:
            session.add_all(missing_tl)
            session.flush()

        matches_by_key = {
            (m.home_team_id, m.away_team_id, m.date): m
            for m in session.query(FootballMatch).filter_by(
                league_id=league.league_id, season_id=season_obj.season_id
            )
        }
        match_ids = [m.match_id for m in matches_by_key.values()]
        match_stats_by_key = {}
        match_forms_by_key = {}
        match_odds_by_key = {}
        if match_ids:
            for s in session.query(MatchStats).filter(MatchStats.match_id.in_(match_ids)):
                match_stats_by_key[(s.match_id, s.team_side)] = s
            for f in session.query(MatchForm).filter(MatchForm.match_id.in_(match_ids)):
                match_forms_by_key[(f.match_id, f.team_side)] = f
            for o in session.query(MatchOdds).filter(MatchOdds.match_id.in_(match_ids)):
                match_odds_by_key[o.match_id] = o

        future_by_key = {
            (fm.home_team_id, fm.away_team_id, fm.date): fm
            for fm in session.query(FutureMatch).filter_by(
                league_id=league.league_id, season_id=season_obj.season_id
            )
        }

        inserted = updated = errors = 0
        new_match_records = []      # (match_fields, stats_records, form_records, odds_dict)
        pending_odds = []            # MatchOdds objects created for existing matches
        pending_stats = []          # MatchStats objects created for existing matches
        pending_forms = []          # MatchForm objects created for existing matches
        futures_to_delete = set()

        side_for = {'H': 'home', 'D': 'draw', 'A': 'away'}
        STAT_FIELDS = ('mean', 'std', 'shannon', 'cv', 'gini', 'hhi')

        for _, row in df.iterrows():
            try:
                home_team = teams_by_name[row['HomeTeam']]
                away_team = teams_by_name[row['AwayTeam']]
                odds_dict = _odds_from_row(row)
                match_key = (home_team.team_id, away_team.team_id, row['Date'])
                match = matches_by_key.get(match_key)

                if match is None:
                    match_fields = dict(
                        home_team_id=home_team.team_id,
                        away_team_id=away_team.team_id,
                        season_id=season_obj.season_id,
                        league_id=league.league_id,
                        date=row['Date'],
                        result=row['FTR'],
                        home_matchday=row['HomeMatchday'],
                        away_matchday=row['AwayMatchday'],
                        round=row['Round'],
                        fthg=row['FTHG'],
                        ftag=row['FTAG'],
                        is_surprise=row['isSurprise'],
                        is_surprise_h=row['isSurprise_H'],
                        is_surprise_d=row['isSurprise_D'],
                        is_surprise_a=row['isSurprise_A'],
                        consensus=row['Consensus'],
                        home_elo=None,
                        away_elo=None,
                        home_elo_change=None,
                        away_elo_change=None,
                    )
                    stats_records = []
                    for suffix in ('H', 'D', 'A'):
                        sd = {
                            k: float(v)
                            for k, v in {
                                'mean': row.get(f'{suffix}_Mean'),
                                'std': row.get(f'{suffix}_Std'),
                                'shannon': row.get(f'{suffix}_Shannon'),
                                'cv': row.get(f'{suffix}_CV'),
                                'gini': row.get(f'{suffix}_Gini'),
                                'hhi': row.get(f'{suffix}_HHI'),
                            }.items()
                            if v is not None and pd.notna(v)
                        }
                        if sd:
                            stats_records.append({'team_side': side_for[suffix], **sd})
                    form_records = []
                    for side in ('home', 'away'):
                        p = side.capitalize()
                        form_records.append(dict(
                            team_side=side,
                            form_last_3=row[f'{p}Form3'],
                            form_last_5=row[f'{p}Form5'],
                            form_season=row[f'{p}FormSeason'],
                            goals_last_3=row[f'{p}Goals3'],
                            goals_last_5=row[f'{p}Goals5'],
                            goals_season=row[f'{p}GoalsSeason'],
                            team_placement=row[f'{p}TeamPlacement'],
                            draw_ratio_team=row[f'{p}DrawRatio'],
                            draw_ratio_league=row[f'{p}LeagueDrawRatio'],
                        ))
                    new_match_records.append((match_fields, stats_records, form_records, odds_dict))
                    if match_key in future_by_key:
                        futures_to_delete.add(future_by_key[match_key])
                    inserted += 1
                else:
                    match.season_id = season_obj.season_id
                    match.league_id = league.league_id
                    match.result = row['FTR']
                    match.home_matchday = row['HomeMatchday']
                    match.away_matchday = row['AwayMatchday']
                    match.round = row['Round']
                    match.fthg = row['FTHG']
                    match.ftag = row['FTAG']
                    match.is_surprise = row['isSurprise']
                    match.is_surprise_h = row['isSurprise_H']
                    match.is_surprise_d = row['isSurprise_D']
                    match.is_surprise_a = row['isSurprise_A']
                    match.consensus = row['Consensus']

                    for suffix in ('H', 'D', 'A'):
                        side = side_for[suffix]
                        sd = {
                            k: float(v)
                            for k, v in {
                                'mean': row.get(f'{suffix}_Mean'),
                                'std': row.get(f'{suffix}_Std'),
                                'shannon': row.get(f'{suffix}_Shannon'),
                                'cv': row.get(f'{suffix}_CV'),
                                'gini': row.get(f'{suffix}_Gini'),
                                'hhi': row.get(f'{suffix}_HHI'),
                            }.items()
                            if v is not None and pd.notna(v)
                        }
                        if sd:
                            st = match_stats_by_key.get((match.match_id, side))
                            if st is None:
                                st = MatchStats(match=match, team_side=side)
                                match_stats_by_key[(match.match_id, side)] = st
                                pending_stats.append(st)
                            for field in STAT_FIELDS:
                                setattr(st, field, sd.get(field))

                    for side in ('home', 'away'):
                        p = side.capitalize()
                        fm = match_forms_by_key.get((match.match_id, side))
                        if fm is None:
                            fm = MatchForm(match=match, team_side=side)
                            match_forms_by_key[(match.match_id, side)] = fm
                            pending_forms.append(fm)
                        fm.form_last_3 = row[f'{p}Form3']
                        fm.form_last_5 = row[f'{p}Form5']
                        fm.form_season = row[f'{p}FormSeason']
                        fm.goals_last_3 = row[f'{p}Goals3']
                        fm.goals_last_5 = row[f'{p}Goals5']
                        fm.goals_season = row[f'{p}GoalsSeason']
                        fm.team_placement = row[f'{p}TeamPlacement']
                        fm.draw_ratio_team = row[f'{p}DrawRatio']
                        fm.draw_ratio_league = row[f'{p}LeagueDrawRatio']

                    if any(odds_dict.values()):
                        mo = match_odds_by_key.get(match.match_id)
                        if mo is None:
                            mo = MatchOdds(match=match, source='football-data.co.uk')
                            match_odds_by_key[match.match_id] = mo
                            pending_odds.append(mo)
                        for fld, val in odds_dict.items():
                            setattr(mo, fld, val)

                    if match_key in future_by_key:
                        futures_to_delete.add(future_by_key[match_key])
                    updated += 1

            except Exception as e:
                errors += 1
                print(f'Error inserting match {row.get("HomeTeam", "?")} vs {row.get("AwayTeam", "?")}: {e}')
                traceback.print_exc()

        # ---- Bulk persist: new matches (with cascaded stats + forms) once ----
        for match_fields, stats_records, form_records, odds_dict in new_match_records:
            m = FootballMatch(**match_fields)
            for sr in stats_records:
                m.match_stats.append(MatchStats(**sr))
            for fr in form_records:
                m.form_data.append(MatchForm(**fr))
            if odds_dict and any(odds_dict.values()):
                m.match_odds = MatchOdds(
                    source='football-data.co.uk', **odds_dict)
            session.add(m)

        if pending_stats or pending_forms:
            session.add_all(pending_stats + pending_forms)
        if pending_odds:
            session.add_all(pending_odds)

        for fm in futures_to_delete:
            session.delete(fm)

        session.commit()


        champion_id = assign_champion_for_season(session, league.league_id, season_obj.season_id)

        if champion_id:
            champion = session.query(Team).filter_by(team_id=champion_id).first()

            print(f"Champion {countryInfo[1]} {seasonCode}: {champion.name if champion else champion_id}")

        print(f"Data for {countryInfo[1]} {seasonCode}: inserted={inserted}, updated={updated}, errors={errors}")

    except Exception as e:
        print(f"Error processing file {countryInfo[1]} {seasonCode}: {e}")
        traceback.print_exc()


def _season_already_scraped(session: Session, league_code: str, season_name: str) -> bool:
    """Check whether a league-season has already been scraped.

    Returns True only when both the league and season exist in the DB and at
    least one FootballMatch row is present for that (league, season) pair.

    Args:
        session (Session): Active SQLAlchemy session.
        league_code (str): Canonical league code.
        season_name (str): Season label.

    Returns:
        bool: True if matches already exist for the league-season, else False.
    """
    league = session.execute(
        select(League).where(League.code == league_code)
    ).scalar_one_or_none()
    if league is None:
        return False
    season = session.execute(
        select(Season).where(Season.name == season_name)
    ).scalar_one_or_none()
    if season is None:
        return False
    return session.query(FootballMatch).filter_by(
        league_id=league.league_id, season_id=season.season_id
    ).first() is not None


def _make_concurrent_engine(engine):
    """Clone the engine so each worker thread owns its own connection.

    SQLAlchemy sessions are not thread-safe, so every worker gets a fresh
    session. For SQLite, a new engine is created with a raised busy ``timeout``
    (60s) so concurrent writers queue instead of raising "database is locked".
    Non-SQLite engines are returned unchanged.

    Args:
        engine (Engine): The application's SQLAlchemy engine.

    Returns:
        Engine: A per-thread clone (SQLite) or the original engine.
    """
    if str(engine.url).startswith('sqlite'):
        return create_engine(str(engine.url), connect_args={'timeout': 60})
    return engine


def scrape_top_11(engine, max_workers: int = 6, skip_existing: bool = True):
    """Concurrently scrape all tracked countries x seasons into the database.

    Builds a task list of every (country, season) pair, optionally filters out
    seasons that already have matches (via ``skip_existing``), then runs one
    worker per remaining task using a thread pool. Each worker opens its own
    session/connection and calls ``get_data_from_top_11``. Exceptions in workers
    are caught and logged so one failure doesn't abort the whole run.

    Args:
        engine (Engine): SQLAlchemy engine used to derive per-worker engines.
        max_workers (int, optional): Thread-pool size. Defaults to 6.
        skip_existing (bool, optional): When True, already-scraped league-seasons
            are skipped. Defaults to True.

    Returns:
        None: Prints skip/progress messages; data is committed within workers.
    """
    scrape_engine = _make_concurrent_engine(engine)

    tasks = [
        (countryValues, seasonCode, COUNTRY_LEAGUE_CODE[country], season_name)
        for country, countryValues in countries.items()
        for season_name, seasonCode in build_seasons().items()
        if country in COUNTRY_LEAGUE_CODE
    ]

    if skip_existing:
        with Session(scrape_engine) as check_session:
            existing = {
                (league_code, season_name)
                for (_cv, _sc, league_code, season_name) in tasks
                if _season_already_scraped(check_session, league_code, season_name)
            }
        tasks = [t for t in tasks if (t[2], t[3]) not in existing]
        print(
            f"Skipping {len(existing)} already-scraped season(s); "
            f"{len(tasks)} remaining to scrape."
        )

    if not tasks:
        print("Nothing to scrape - all seasons already present.")
        return

    def _worker(countryValues, seasonCode, _league_code, _season_name):
        """Run a single league-season scrape in its own session.

        Worker callback submitted to the thread pool. Opens a dedicated session
        bound to the scrape engine and delegates to ``get_data_from_top_11``.

        Args:
            countryValues (list): ``[country_slug, league_label]`` for the source.
            seasonCode (str): Two-digit season code.
            _league_code (str): Canonical league code (unused here; passed for
                task-tuple symmetry).
            _season_name (str): Season label (unused here; passed for task-tuple
                symmetry).

        Returns:
            None: Scrapes and commits data via the session.
        """
        with Session(scrape_engine) as session:
            get_data_from_top_11(session, countryValues, seasonCode)

    done = 0
    total = len(tasks)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_worker, cv, sc, lc, sn)
            for (cv, sc, lc, sn) in tasks
        ]
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"Error during scrape task: {e}")
                traceback.print_exc()
            done += 1
            if done % 25 == 0 or done == total:
                print(f"Scrape progress: {done}/{total}")



def _calculate_final_standings(session, league_id, season_id):
    """Compute final league standings from played matches.

    Replays all matches (ordered by date) for a league-season, accumulating
    points, goals for and goals against per team, then ranks teams by points,
    goal difference and goals for. Used to determine the season champion.

    Args:
        session (Session): Active SQLAlchemy session.
        league_id: League identifier.
        season_id: Season identifier.

    Returns:
        list[tuple]: A ranked list of ``(team_id, points, goal_diff, goals_for)``
        tuples (best first); empty list when there are no matches.
    """
    matches = session.query(FootballMatch).filter(
        FootballMatch.league_id == league_id,
        FootballMatch.season_id == season_id,
    ).order_by(FootballMatch.date, FootballMatch.match_id).all()

    if not matches:
        return []

    standings = {}

    for m in matches:
        for tid in (m.home_team_id, m.away_team_id):
            standings.setdefault(tid, {"points": 0, "gf": 0, "ga": 0})

        h, a = standings[m.home_team_id], standings[m.away_team_id]
        hg, ag = m.fthg or 0, m.ftag or 0
        h["gf"] += hg; h["ga"] += ag
        a["gf"] += ag; a["ga"] += hg

        if m.result == "H":
            h["points"] += 3
        elif m.result == "D":
            h["points"] += 1; a["points"] += 1
        elif m.result == "A":
            a["points"] += 3

    ranked = sorted(
        standings.items(),
        key=lambda kv: (-kv[1]["points"], -(kv[1]["gf"] - kv[1]["ga"]), -kv[1]["gf"])
    )
    return [(tid, s["points"], s["gf"] - s["ga"], s["gf"]) for tid, s in ranked]


def assign_champion_for_season(session, league_id, season_id):
    """Mark the season champion on TeamLeague rows.

    Computes the final standings, takes the top-ranked team, and sets
    ``is_champion`` to 1 on its TeamLeague row (0 for every other team in the
    league-season). Commits the changes.

    Args:
        session (Session): Active SQLAlchemy session.
        league_id: League identifier.
        season_id: Season identifier.

    Returns:
        Any or None: The champion team_id, or None when no matches exist.
    """
    standings = _calculate_final_standings(session, league_id, season_id)
    if not standings:
        return None

    champion_team_id = standings[0][0]

    team_leagues = session.query(TeamLeague).filter_by(
        league_id=league_id, season_id=season_id
    ).all()

    for tl in team_leagues:
        tl.is_champion = 1 if tl.team_id == champion_team_id else 0

    session.commit()
    return champion_team_id

def compute_stats_dict(session: Session) -> dict:
    """Compute system statistics from the current database state (no save).

    Returns a dict of aggregate counts and "extreme" records (teams, seasons,
    leagues, played matches, future matches, highest/lowest Elo, highest-goal
    match, and the biggest upset by prediction confidence). The dict fields
    mirror the ``SystemStats`` columns except processing-time fields. Used both
    when persisting (``compute_and_save_stats``) and for live display on /stats.

    Args:
        session (Session): Active SQLAlchemy session.

    Returns:
        dict: Statistics keyed by SystemStats column names (e.g.
        ``teams_count``, ``matches_count``, ``biggest_upset_match_id``).
    """
    from sqlalchemy.sql import func
    from src.flask_app.app.models import (
        Team, Season, League, FootballMatch,
        TeamElo, FutureMatch, Predicted,
    )

    teams_count = session.execute(
        select(func.count()).select_from(Team)
    ).scalar()

    seasons_count = session.execute(
        select(func.count()).select_from(Season)
    ).scalar()

    leagues_count = session.execute(
        select(func.count()).select_from(League)
    ).scalar()

    matches_count = session.execute(
        select(func.count()).select_from(FootballMatch)
        .where(FootballMatch.result.isnot(None))
    ).scalar()

    future_matches_count = session.execute(
        select(func.count()).select_from(FutureMatch)
    ).scalar()

    highest_elo = session.execute(
        select(TeamElo).order_by(TeamElo.rating.desc()).limit(1)
    ).scalar_one_or_none()

    lowest_elo = session.execute(
        select(TeamElo).order_by(TeamElo.rating.asc()).limit(1)
    ).scalar_one_or_none()

    highest_goal_match = session.execute(
        select(FootballMatch)
        .where(
            FootballMatch.fthg.isnot(None),
            FootballMatch.ftag.isnot(None),
        )
        .order_by((FootballMatch.fthg + FootballMatch.ftag).desc())
        .limit(1)
    ).scalar_one_or_none()

    upset_row = session.execute(
        select(
            FootballMatch,
            Predicted.predicted_result,
            Predicted.confidence,
        )
        .join(Predicted, Predicted.match_id == FootballMatch.match_id)
        .where(
            FootballMatch.result.isnot(None),
            Predicted.predicted_result != FootballMatch.result,
            Predicted.confidence.isnot(None),
        )
        .order_by(Predicted.confidence.desc())
        .limit(1)
    ).first()

    biggest_upset_match = upset_row[0] if upset_row else None
    biggest_upset_predicted = upset_row[1] if upset_row else None
    biggest_upset_confidence = float(upset_row[2]) if upset_row else None
    biggest_upset_actual = biggest_upset_match.result if biggest_upset_match else None

    return {
        "teams_count": teams_count,
        "seasons_count": seasons_count,
        "leagues_count": leagues_count,
        "matches_count": matches_count,
        "future_matches_count": future_matches_count,
        "highest_elo_id": highest_elo.elo_id if highest_elo else None,
        "lowest_elo_id": lowest_elo.elo_id if lowest_elo else None,
        "highest_goal_match_id": highest_goal_match.match_id if highest_goal_match else None,
        "biggest_upset_match_id": biggest_upset_match.match_id if biggest_upset_match else None,
        "biggest_upset_confidence": biggest_upset_confidence,
        "biggest_upset_predicted": biggest_upset_predicted,
        "biggest_upset_actual": biggest_upset_actual,
    }


def compute_and_save_stats(
    session: Session,
    scraping_time: float = None,
    elo_calc_time: float = None,
    prediction_time: float = None,
):
    """Compute system stats and persist them as a new SystemStats row.

    Builds the statistics dict via ``compute_stats_dict`` and combines it with
    the supplied pipeline timing values, then creates and commits a SystemStats
    record.

    Args:
        session (Session): Active SQLAlchemy session.
        scraping_time (float, optional): Elapsed scraping time in seconds.
        elo_calc_time (float, optional): Elapsed Elo-calculation time in seconds.
        prediction_time (float, optional): Elapsed prediction time in seconds.

    Returns:
        SystemStats: The newly created and committed SystemStats instance.
    """
    from src.flask_app.app.models import SystemStats

    stats = SystemStats(
        scraping_time=scraping_time,
        elo_calc_time=elo_calc_time,
        prediction_time=prediction_time,
        **compute_stats_dict(session),
    )
    session.add(stats)
    session.commit()
    return stats

def correct_scrape_top_11(session: Session):
    """Run the full concurrent scrape using the session's bound engine.

    Convenience wrapper that extracts the engine from an active session
    (``session.get_bind()``) and passes it to ``scrape_top_11``.

    Args:
        session (Session): Active SQLAlchemy session whose bound engine is used.

    Returns:
        None: Delegates to ``scrape_top_11``.
    """
    scrape_top_11(session.get_bind())

