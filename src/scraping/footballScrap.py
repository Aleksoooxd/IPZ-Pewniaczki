import numpy as np
import chardet
import requests
import io
import traceback
from concurrent.futures import ThreadPoolExecutor
import datetime
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from unidecode import unidecode

from src.flask_app.app.models import (
    FootballMatch, MatchStats, MatchForm,
    Team, League, Season, TeamLeague, FutureMatch
)
from src.calculations.helpfunctions import (
    hhi_index, shannon_index, coefficient_of_variation, gini_index, calculate_consensus
)

pd.set_option('future.no_silent_downcasting', True)

headers = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
    )
}

curr_year = (
    (datetime.datetime.now().year - 1)
    if datetime.datetime.now().month < 8
    else datetime.datetime.now().year
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

all_team_names = set()

football_mapping = {
    "Belenenses": "CF Belenenses",
    "Hamilton": "Hamilton Academical FC",
    "Cadiz": "Cádiz CF",
    "FC Koln": "1.FC Köln",
    "FC Famalicão": "1.FC Köln",
    "Famalicao": "FC Famalicão",
    "QPR": "Queens Park Rangers",
    "Rennes": "Stade Rennais FC",
    "Verona": "Hellas Verona",
    "Ajax ": "Ajax",
    "Feyenoord ": "Feyenoord",
    "Graafschap ": "Graafschap",
    "Groningen ": "Groningen",
    "Heracles ": "Heracles",
    "Roda ": "Roda",
    "Utrecht ": "Utrecht",
    "Vitesse ": "Vitesse",
    "Willem II ": "Willem II",
    "Kalithea": "Kallithea",
    "Aves": "AVS",
    "Feirense ": "Feirense",
    "Sparta": "Sparta Rotterdam",
    "OFI": "OFI Crete",
    "Roda JC": "Roda",
    "CF Belenenses": "Belenses",
    "Estrela": "Est Amadora",
    "Germinal": "Beerschot VA",
    "Waasland-Beveren": "Beveren",
    "FC Brussels": "RWD Molenbeek",
    "Mouscron-Peruwelz": "Mouscron",
    "Louvieroise": "RAAL La Louviere",
    "Oftasspor": "Hacettepespor",
}


# ---------------------------------------------------------------------------
# Pomocnicze — bez zależności od bazy
# ---------------------------------------------------------------------------

def detect_encoding(byte_content: bytes) -> str:
    result = chardet.detect(byte_content)
    return result['encoding']


def apply_team_mapping(club_name: str, mapping: dict) -> str:
    cleaned_name = ' '.join(club_name.strip().split())
    if cleaned_name in mapping:
        return mapping[cleaned_name]
    lower_name = cleaned_name.lower()
    for key in mapping:
        if key.lower() == lower_name:
            return mapping[key]
    return cleaned_name


def map_team_name(val) -> str:
    if not isinstance(val, str):
        val = str(val)
    val = unidecode(val).strip()
    return football_mapping.get(val, val)


def correct_date_format(val):
    if isinstance(val, str) and len(val) == 8:
        return val[:6] + "20" + val[6:]
    return val


def get_season(date):
    if pd.isnull(date):
        return None
    if not isinstance(date, (pd.Timestamp, datetime.date)):
        raise ValueError("The 'date' parameter must be a pandas.Timestamp or datetime.date object.")
    year = date.year
    if date.month >= 7:
        start_year, end_year = year, year + 1
    else:
        start_year, end_year = year - 1, year
    if start_year >= 2009:
        return f"{start_year}/{end_year % 100:02d}"
    else:
        return f"{start_year}/{end_year % 100:01d}"


def get_league(df: pd.DataFrame):
    leagues = df['Div'].unique()
    if len(leagues) == 0:
        return None
    league = leagues[0]
    mapping = {
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
    return mapping.get(league, league)


def get_seasons(df: pd.DataFrame):
    unique = df['Season'].unique()
    return unique[0] if len(unique) > 0 else None


# ---------------------------------------------------------------------------
# Transformacje DataFrame — bez zależności od bazy
# ---------------------------------------------------------------------------

def add_matchday_to_season(df: pd.DataFrame) -> pd.DataFrame:
    matchday_counter = {}
    df['HomeMatchday'] = pd.NA
    df['AwayMatchday'] = pd.NA
    for index, row in df.iterrows():
        season = row['Season']
        home_team = row['HomeTeam']
        away_team = row['AwayTeam']
        matchday_counter.setdefault(season, {})
        matchday_counter[season].setdefault(home_team, 0)
        matchday_counter[season].setdefault(away_team, 0)
        matchday_counter[season][home_team] += 1
        matchday_counter[season][away_team] += 1
        df.loc[index, 'HomeMatchday'] = matchday_counter[season][home_team]
        df.loc[index, 'AwayMatchday'] = matchday_counter[season][away_team]
    return df


def calculate_is_surprise(df: pd.DataFrame) -> pd.DataFrame:
    selected_columns = [
        'Div', 'Season', 'Date', 'HomeTeam', 'AwayTeam', 'FTR',
        'HomeMatchday', 'AwayMatchday', 'FTHG', 'FTAG'
    ]
    all_bookmaker_columns = [
        'B365H', 'B365D', 'B365A', 'BFH', 'BFD', 'BFA', 'BSH', 'BSD', 'BSA',
        'BWH', 'BWD', 'BWA', 'GBH', 'GBD', 'GBA', 'IWH', 'IWD', 'IWA',
        'LBH', 'LBD', 'LBA', 'PSH', 'PSD', 'PSA', 'SOH', 'SOD', 'SOA',
        'SBH', 'SBD', 'SBA', 'SJH', 'SJD', 'SJA', 'SYH', 'SYD', 'SYA',
        'VCH', 'VCD', 'VCA', 'WHH', 'WHD', 'WHA'
    ]
    required_columns = selected_columns + all_bookmaker_columns
    new_columns = {col: pd.NA for col in required_columns if col not in df.columns}
    df = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)
    df = df[required_columns].fillna(1.0)

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

    previous_season_final_placements = {}

    for season, season_df_orig in dataframe.groupby('Season'):
        season_df = season_df_orig.sort_values(by=['Date', 'HomeMatchday']).copy()
        standings = {}
        team_history = {}

        for index, row in season_df.iterrows():
            home_team = row['HomeTeam']
            away_team = row['AwayTeam']

            for team in [home_team, away_team]:
                if team not in standings:
                    standings[team] = {'points': 0, 'goal_diff': 0, 'goals_scored': 0, 'goals_against': 0}
                if team not in team_history:
                    team_history[team] = {'results_pts': [], 'goals_for': []}

            sorted_teams = sorted(
                standings.keys(),
                key=lambda t: (-standings[t]['points'], -standings[t]['goal_diff'], -standings[t]['goals_scored'], t)
            )
            placement_map = {team: i + 1 for i, team in enumerate(sorted_teams)}

            dataframe.loc[index, 'HomeTeamPlacement'] = placement_map.get(home_team, len(standings) + 1)
            dataframe.loc[index, 'AwayTeamPlacement'] = placement_map.get(away_team, len(standings) + 1)

            home_hist = team_history[home_team]
            away_hist = team_history[away_team]

            dataframe.loc[index, 'HomeForm3'] = sum(home_hist['results_pts'][-3:])
            dataframe.loc[index, 'HomeForm5'] = sum(home_hist['results_pts'][-5:])
            dataframe.loc[index, 'HomeFormSeason'] = sum(home_hist['results_pts'])
            dataframe.loc[index, 'HomeGoals3'] = sum(home_hist['goals_for'][-3:])
            dataframe.loc[index, 'HomeGoals5'] = sum(home_hist['goals_for'][-5:])
            dataframe.loc[index, 'HomeGoalsSeason'] = sum(home_hist['goals_for'])

            dataframe.loc[index, 'AwayForm3'] = sum(away_hist['results_pts'][-3:])
            dataframe.loc[index, 'AwayForm5'] = sum(away_hist['results_pts'][-5:])
            dataframe.loc[index, 'AwayFormSeason'] = sum(away_hist['results_pts'])
            dataframe.loc[index, 'AwayGoals3'] = sum(away_hist['goals_for'][-3:])
            dataframe.loc[index, 'AwayGoals5'] = sum(away_hist['goals_for'][-5:])
            dataframe.loc[index, 'AwayGoalsSeason'] = sum(away_hist['goals_for'])

            dataframe.loc[index, 'HTLSP'] = previous_season_final_placements.get(home_team, 0)
            dataframe.loc[index, 'ATLSP'] = previous_season_final_placements.get(away_team, 0)

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

        final_sorted_teams = sorted(
            standings.keys(),
            key=lambda t: (-standings[t]['points'], -standings[t]['goal_diff'], -standings[t]['goals_scored'], t)
        )
        previous_season_final_placements = {team: i + 1 for i, team in enumerate(final_sorted_teams)}

    return dataframe


def calculate_statistics_and_consensus(data: pd.DataFrame) -> pd.DataFrame:
    bookmakers_columns = {
        "AllBookmakers": {
            "H": ["B365H", "BFH", "BSH", "BWH", "GBH", "IWH", "LBH", "PSH", "SOH", "SBH", "SJH", "SYH", "VCH", "WHH"],
            "D": ["B365D", "BFD", "BSD", "BWD", "GBD", "IWD", "LBD", "PSD", "SOD", "SBD", "SJD", "SYD", "VCD", "WHD"],
            "A": ["B365A", "BFA", "BSA", "BWA", "GBA", "IWA", "LBA", "PSA", "SOA", "SBA", "SJA", "SYA", "VCA", "WHA"]
        }
    }
    for result_type, cols in bookmakers_columns["AllBookmakers"].items():
        numeric_data = data[cols].apply(pd.to_numeric, errors='coerce')
        for stat in ["Mean", "Std", "Shannon", "CV", "Gini", "HHI"]:
            data[f"{result_type}_{stat}"] = None

        for i, row in numeric_data.iterrows():
            valid_values = row.dropna().to_numpy()
            if len(valid_values) > 0:
                data.loc[i, f"{result_type}_Mean"] = np.round(np.mean(valid_values), 4)
                data.loc[i, f"{result_type}_Std"] = np.round(np.std(valid_values), 4)
                data.loc[i, f"{result_type}_Shannon"] = shannon_index(valid_values)
                data.loc[i, f"{result_type}_CV"] = coefficient_of_variation(valid_values)
                data.loc[i, f"{result_type}_Gini"] = gini_index(valid_values)
                data.loc[i, f"{result_type}_HHI"] = hhi_index(valid_values)
            else:
                for stat in ["Mean", "Std", "Shannon", "CV", "Gini", "HHI"]:
                    data.loc[i, f"{result_type}_{stat}"] = np.nan

    data['Consensus'] = data.apply(
        calculate_consensus, axis=1, columns=bookmakers_columns["AllBookmakers"]
    )
    return data


# ---------------------------------------------------------------------------
# Operacje na bazie — przyjmują session z zewnątrz
# ---------------------------------------------------------------------------

def get_or_create_team(session: Session, team_name: str) -> Team:
    team = session.execute(select(Team).where(Team.name == team_name)).scalar_one_or_none()
    if team is None:
        team = Team(name=team_name)
        session.add(team)
        session.flush()
    return team


def get_or_create_league(session: Session, league_name: str) -> League:
    league = session.execute(select(League).where(League.code == league_name)).scalar_one_or_none()
    if league is None:
        league = League(code=league_name)
        session.add(league)
        session.flush()
    return league


def get_or_create_season(session: Session, season_name: str) -> Season:
    season = session.execute(select(Season).where(Season.name == season_name)).scalar_one_or_none()
    if season is None:
        season = Season(name=season_name)
        session.add(season)
        session.flush()
    return season


def get_or_create_team_league(session: Session, team_id: int, league_id: int, season_id: int) -> TeamLeague:
    team_league = session.execute(
        select(TeamLeague).where(
            TeamLeague.team_id == team_id,
            TeamLeague.league_id == league_id,
            TeamLeague.season_id == season_id,
        )
    ).scalar_one_or_none()
    if team_league is None:
        team_league = TeamLeague(team_id=team_id, league_id=league_id, season_id=season_id)
        session.add(team_league)
        session.flush()
    return team_league


def check_and_remove_future_match(
    session: Session, home_team_id: int, away_team_id: int, match_date
) -> bool:
    future_match = session.execute(
        select(FutureMatch).where(
            FutureMatch.home_team_id == home_team_id,
            FutureMatch.away_team_id == away_team_id,
            FutureMatch.date == match_date,
        )
    ).scalar_one_or_none()
    if future_match:
        print(f"Match found in FutureMatch table. Removing — it's now a past match.")
        session.delete(future_match)
        return True
    return False


def extract_team_names(csv_content: bytes):
    try:
        enc = detect_encoding(csv_content)
        df = pd.read_csv(
            io.StringIO(csv_content.decode(enc)), encoding=enc,
            low_memory=False, on_bad_lines='skip'
        )
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ('team', 'home', 'away', 'hometeam', 'awayteam')):
                teams = df[col].dropna().unique()
                all_team_names.update(map_team_name(t) for t in teams)
    except Exception as e:
        print(f"Błąd podczas wyodrębniania nazw drużyn: {e}")


# ---------------------------------------------------------------------------
# Scraping — funkcje przyjmują session z zewnątrz
# ---------------------------------------------------------------------------

def get_data_from_top_11(
    session: Session,
    correct: dict,
    countryInfo: list,
    seasonCode: str,
):
    """
    Pobiera i zapisuje dane meczów dla jednej ligi i sezonu.
    session — SQLAlchemy session przekazana z zewnątrz (z Flask app context).
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
        df["HomeTeam"] = df["HomeTeam"].apply(lambda x: apply_team_mapping(x, football_mapping))
        df["AwayTeam"] = df["AwayTeam"].apply(lambda x: apply_team_mapping(x, football_mapping))
        df["HomeTeam"] = df["HomeTeam"].apply(lambda x: apply_team_mapping(x, correct))
        df["AwayTeam"] = df["AwayTeam"].apply(lambda x: apply_team_mapping(x, correct))

        df = add_matchday_to_season(df)
        df = calculate_is_surprise(df)
        df = create_placement_columns(df)
        df = calculate_statistics_and_consensus(df)
        df = df.sort_values(by='Date')

        league = get_or_create_league(session, get_league(df))
        season_obj = get_or_create_season(session, get_seasons(df))
        session.commit()

        inserted = updated = errors = 0

        for _, row in df.iterrows():
            try:
                home_team = get_or_create_team(session, row['HomeTeam'])
                away_team = get_or_create_team(session, row['AwayTeam'])
                get_or_create_team_league(session, home_team.team_id, league.league_id, season_obj.season_id)
                get_or_create_team_league(session, away_team.team_id, league.league_id, season_obj.season_id)

                match = session.execute(
                    select(FootballMatch).where(
                        FootballMatch.home_team_id == home_team.team_id,
                        FootballMatch.away_team_id == away_team.team_id,
                        FootballMatch.date == row['Date']
                    )
                ).scalar_one_or_none()

                is_new = match is None
                if is_new:
                    match = FootballMatch(
                        home_team_id=home_team.team_id,
                        away_team_id=away_team.team_id,
                        season_id=season_obj.season_id,
                        league_id=league.league_id,
                        date=row['Date'],
                        result=row['FTR'],
                        home_matchday=row['HomeMatchday'],
                        away_matchday=row['AwayMatchday'],
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
                    session.add(match)
                    session.flush()
                    check_and_remove_future_match(session, home_team.team_id, away_team.team_id, row['Date'])
                else:
                    match.season_id = season_obj.season_id
                    match.league_id = league.league_id
                    match.result = row['FTR']
                    match.home_matchday = row['HomeMatchday']
                    match.away_matchday = row['AwayMatchday']
                    match.fthg = row['FTHG']
                    match.ftag = row['FTAG']
                    match.is_surprise = row['isSurprise']
                    match.is_surprise_h = row['isSurprise_H']
                    match.is_surprise_d = row['isSurprise_D']
                    match.is_surprise_a = row['isSurprise_A']
                    match.consensus = row['Consensus']
                    session.flush()

                for suffix in ['H', 'D', 'A']:
                    side = 'home' if suffix == 'H' else ('draw' if suffix == 'D' else 'away')
                    stats_data = {
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
                    if stats_data:
                        MatchStats.create_or_update(
                            session=session,
                            match_id=match.match_id,
                            side=side,
                            data=stats_data,
                        )

                for side in ['home', 'away']:
                    prefix = side.capitalize()
                    match_form = session.execute(
                        select(MatchForm).where(
                            MatchForm.match_id == match.match_id,
                            MatchForm.team_side == side
                        )
                    ).scalar_one_or_none()

                    if not match_form:
                        match_form = MatchForm(
                            match_id=match.match_id,
                            team_side=side,
                            form_last_3=row[f'{prefix}Form3'],
                            form_last_5=row[f'{prefix}Form5'],
                            form_season=row[f'{prefix}FormSeason'],
                            goals_last_3=row[f'{prefix}Goals3'],
                            goals_last_5=row[f'{prefix}Goals5'],
                            goals_season=row[f'{prefix}GoalsSeason'],
                            team_placement=row[f'{prefix}TeamPlacement'],
                            h2h_matches=None,
                            h2h_wins=None,
                            h2h_draws=None,
                            h2h_losses=None,
                            h2h_goals_for=None,
                            h2h_goals_against=None,
                            h2h_last_5_points=None,
                        )
                        session.add(match_form)
                        session.flush()
                    else:
                        match_form.form_last_3 = row[f'{prefix}Form3']
                        match_form.form_last_5 = row[f'{prefix}Form5']
                        match_form.form_season = row[f'{prefix}FormSeason']
                        match_form.goals_last_3 = row[f'{prefix}Goals3']
                        match_form.goals_last_5 = row[f'{prefix}Goals5']
                        match_form.goals_season = row[f'{prefix}GoalsSeason']
                        match_form.team_placement = row[f'{prefix}TeamPlacement']

                session.commit()
                if is_new:
                    inserted += 1
                else:
                    updated += 1


            except Exception as e:

                session.rollback()

                errors += 1

                print(f'Error inserting match {row.get("HomeTeam", "?")} vs {row.get("AwayTeam", "?")}: {e}')

                traceback.print_exc()


        champion_id = assign_champion_for_season(session, league.league_id, season_obj.season_id)

        if champion_id:
            champion = session.query(Team).filter_by(team_id=champion_id).first()

            print(f"Champion {countryInfo[1]} {seasonCode}: {champion.name if champion else champion_id}")

        print(f"Data for {countryInfo[1]} {seasonCode}: inserted={inserted}, updated={updated}, errors={errors}")

    except Exception as e:
        print(f"Error processing file {countryInfo[1]} {seasonCode}: {e}")
        traceback.print_exc()


def scrape_top_11(session: Session, correct: dict):
    """Iteruje po wszystkich krajach i sezonach, zapisuje dane do bazy."""
    for country, countryValues in countries.items():
        for season, seasonCode in seasons.items():
            get_data_from_top_11(session, correct, countryValues, seasonCode)


def get_team_names_only(countryInfo: list, seasonCode: str):
    url = f'https://www.football-data.co.uk/{countryInfo[0]}m.php'
    with requests.Session() as req_session:
        response = req_session.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Nie udało się załadować strony {url}")
            return
        soup = BeautifulSoup(response.text, 'html.parser')
        all_a_tags = soup.find('a', string=f'{countryInfo[1]}')
        if not all_a_tags:
            return
        download_link = all_a_tags.get('href').split('/')
        download_link[1] = f'{seasonCode}'
        download_url = f'https://www.football-data.co.uk/{"/".join(download_link)}'
        download_response = req_session.get(download_url, headers=headers)
        if download_response.status_code == 200:
            extract_team_names(download_response.content)


def scrape_team_names_only() -> list:
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(get_team_names_only, countryValues, seasonCode)
            for countryValues in countries.values()
            for seasonCode in seasons.values()
        ]
        for future in futures:
            future.result()
    return sorted(all_team_names)
def _calculate_final_standings(session, league_id, season_id):
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

def compute_and_save_stats(
    session: Session,
    scraping_time: float = None,
    elo_calc_time: float = None,
    prediction_time: float = None,
):
    from sqlalchemy.sql import func
    from src.flask_app.app.models import (
        Team, Season, League, FootballMatch,
        TeamElo, FutureMatch, Predicted, SystemStats
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

    stats = SystemStats(
        scraping_time=scraping_time,
        elo_calc_time=elo_calc_time,
        prediction_time=prediction_time,
        teams_count=teams_count,
        seasons_count=seasons_count,
        leagues_count=leagues_count,
        matches_count=matches_count,
        future_matches_count=future_matches_count,
        highest_elo_id=highest_elo.elo_id if highest_elo else None,
        lowest_elo_id=lowest_elo.elo_id if lowest_elo else None,
        highest_goal_match_id=highest_goal_match.match_id if highest_goal_match else None,
        biggest_upset_match_id=biggest_upset_match.match_id if biggest_upset_match else None,
        biggest_upset_confidence=biggest_upset_confidence,
        biggest_upset_predicted=biggest_upset_predicted,
        biggest_upset_actual=biggest_upset_actual,
    )
    session.add(stats)
    session.commit()
    return stats

def correct_scrape_top_11(session: Session):
    scrape_top_11(session, {})
    from src.scraping.rename_team import rename
    rename(session)

