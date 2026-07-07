import numpy as np
import chardet
import requests
import io
import os
import shutil
from bs4 import BeautifulSoup
import datetime
import traceback
from concurrent.futures import ThreadPoolExecutor
import random
import pandas as pd
from PIL import Image
import time as time_module
from sqlalchemy import select
from unidecode import unidecode
from src.flask_app.app.db import db, app, FootballMatch, MatchStats, MatchForm, Team, League, Season, TeamLeague, FutureMatch
from src.calculations.helpfunctions import hhi_index,shannon_index, coefficient_of_variation, gini_index, calculate_consensus

pd.set_option('future.no_silent_downcasting', True)
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}

curr_year = (datetime.datetime.now().year-1) if datetime.datetime.now().month < 8 else datetime.datetime.now().year
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
        "Belenenses" : "CF Belenenses",
        "Hamilton" : "Hamilton Academical FC",
        "Cadiz" : "Cádiz CF",
        "FC Koln" : "1.FC Köln",
        "FC Famalicão" : "1.FC Köln",
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
        "CF Belenenses": "Belenses"
}

def extract_team_names(csv_content):
    try:
        enc = detect_encoding(csv_content)
        df = pd.read_csv(io.StringIO(csv_content.decode(enc)), encoding=enc, low_memory=False, on_bad_lines='skip')

        team_columns = []
        for col in df.columns:
            col_lower = col.lower()
            if 'team' in col_lower or 'home' in col_lower or 'away' in col_lower or 'hometeam' in col_lower or 'awayteam' in col_lower:
                team_columns.append(col)

        for col in team_columns:
            teams = df[col].dropna().unique()
            mapped_teams = [map_team_name(team) for team in teams]
            all_team_names.update(mapped_teams)

    except Exception as e:
        print(f"Błąd podczas wyodrębniania nazw drużyn: {e}")

def get_team_names_only(countryInfo, seasonCode):
    url = f'https://www.football-data.co.uk/{countryInfo[0]}m.php'
    with requests.Session() as session:
        response = session.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Nie udało się załadować strony {url}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        all_a_tags = soup.find('a', string=f'{countryInfo[1]}')
        if not all_a_tags:
            print(f"Nie znaleziono linku dla {countryInfo[1]} {seasonCode}")
            return

        download_link = all_a_tags.get('href').split('/')
        download_link[1] = f'{seasonCode}'
        download_link = '/'.join(download_link)

        download_url = f'https://www.football-data.co.uk/{download_link}'
        download_response = session.get(download_url, headers=headers)
        if download_response.status_code != 200:
            return

        extract_team_names(download_response.content)

def apply_team_mapping(club_name, mapping):
    cleaned_name = ' '.join(club_name.strip().split())
    if cleaned_name in mapping:
        return mapping[cleaned_name]
    lower_name = cleaned_name.lower()
    for key in mapping:
        if key.lower() == lower_name:
            return mapping[key]
    return cleaned_name
def map_team_name(val):
    if not isinstance(val, str):
        val = str(val)
    val = unidecode(val).strip()
    return football_mapping.get(val, val)

def scrape_team_names_only():
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for country, countryValues in countries.items():
            for season, seasonCode in seasons.items():
                futures.append(executor.submit(get_team_names_only, countryValues, seasonCode))
        for future in futures:
            future.result()

    return sorted(all_team_names)

def get_season(date):
    if pd.isnull(date):
        return None
    if not isinstance(date, (pd.Timestamp, datetime.date)):
        raise ValueError("The 'date' parameter must be a pandas.Timestamp or datetime.date object.")

    year = date.year
    if date.month >= 7:
        start_year = year
        end_year = year + 1
    else:
        start_year = year - 1
        end_year = year

    if start_year >= 2009:
        return f"{start_year}/{end_year % 100:02d}"
    else:
        return f"{start_year}/{end_year % 100:01d}"


def create_placement_columns(dataframe):
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

            sorted_teams = sorted(standings.keys(),
                                  key=lambda t: (
                                  -standings[t]['points'], -standings[t]['goal_diff'], -standings[t]['goals_scored'],
                                  t))
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
            standings[home_team]['goal_diff'] = standings[home_team]['goals_scored'] - standings[home_team][
                'goals_against']

            standings[away_team]['goals_scored'] += ftag
            standings[away_team]['goals_against'] += fthg
            standings[away_team]['goal_diff'] = standings[away_team]['goals_scored'] - standings[away_team][
                'goals_against']

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

        final_sorted_teams = sorted(standings.keys(),
                                    key=lambda t: (
                                    -standings[t]['points'], -standings[t]['goal_diff'], -standings[t]['goals_scored'],
                                    t))
        previous_season_final_placements = {team: i + 1 for i, team in enumerate(final_sorted_teams)}

    return dataframe


def calculate_statistics_and_consensus(data):
    bookmakers_columns = {
        "AllBookmakers": {
            "H": ["B365H", "BFH", "BSH", "BWH", "GBH", "IWH", "LBH", "PSH", "SOH", "SBH", "SJH", "SYH", "VCH",
                  "WHH"],
            "D": ["B365D", "BFD", "BSD", "BWD", "GBD", "IWD", "LBD", "PSD", "SOD", "SBD", "SJD", "SYD", "VCD",
                  "WHD"],
            "A": ["B365A", "BFA", "BSA", "BWA", "GBA", "IWA", "LBA", "PSA", "SOA", "SBA", "SJA", "SYA", "VCA",
                  "WHA"]
        }
    }
    for result_type, cols in bookmakers_columns["AllBookmakers"].items():

        numeric_data = data[cols].apply(pd.to_numeric, errors='coerce')

        data[f"{result_type}_Mean"] = None
        data[f"{result_type}_Std"] = None
        data[f"{result_type}_Shannon"] = None
        data[f"{result_type}_CV"] = None
        data[f"{result_type}_Gini"] = None
        data[f"{result_type}_HHI"] = None

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
                data.loc[i, f"{result_type}_Mean"] = np.nan
                data.loc[i, f"{result_type}_Std"] = np.nan
                data.loc[i, f"{result_type}_Shannon"] = np.nan
                data.loc[i, f"{result_type}_CV"] = np.nan
                data.loc[i, f"{result_type}_Gini"] = np.nan
                data.loc[i, f"{result_type}_HHI"] = np.nan

    data['Consensus'] = data.apply(calculate_consensus, axis=1, columns=bookmakers_columns["AllBookmakers"])
    return data
def calculate_is_suprise(df):
    selected_columns = [
        'Div','Season', 'Date', 'HomeTeam', 'AwayTeam', 'FTR',
        'HomeMatchday', 'AwayMatchday', 'FTHG', 'FTAG'
    ]
    all_bookmaker_columns = [
        'B365H', 'B365D', 'B365A', 'BFH', 'BFD', 'BFA', 'BSH', 'BSD', 'BSA', 'BWH', 'BWD', 'BWA',
        'GBH', 'GBD', 'GBA', 'IWH', 'IWD', 'IWA', 'LBH', 'LBD', 'LBA', 'PSH', 'PSD', 'PSA',
        'SOH', 'SOD', 'SOA', 'SBH', 'SBD', 'SBA', 'SJH', 'SJD', 'SJA', 'SYH', 'SYD', 'SYA',
        'VCH', 'VCD', 'VCA', 'WHH', 'WHD', 'WHA'
    ]
    required_columns = selected_columns + all_bookmaker_columns
    new_columns = {col: pd.NA for col in required_columns if col not in df.columns}
    df = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)
    df = df[required_columns]
    df = df.fillna(1.0)
    home_stakeholders = [col for col in df.columns if col.endswith("H")]
    draw_stakeholders = [col for col in df.columns if col.endswith("D")]
    away_stakeholders = [col for col in df.columns if col.endswith("A")]
    df['Avg_H'] = df[home_stakeholders].mean(axis=1)
    df['Avg_D'] = df[draw_stakeholders].mean(axis=1)
    df['Avg_A'] = df[away_stakeholders].mean(axis=1)
    df['isSuprise_H'] = (
            (df['FTR'] == 'H') & (df['Avg_H'] > df[['Avg_D', 'Avg_A']].max(axis=1))
    ).astype(int)
    df['isSuprise_D'] = (
            (df['FTR'] == 'D') & (df['Avg_D'] > df[['Avg_H', 'Avg_A']].max(axis=1))
    ).astype(int)
    df['isSuprise_A'] = (
            (df['FTR'] == 'A') & (df['Avg_A'] > df[['Avg_H', 'Avg_D']].max(axis=1))
    ).astype(int)
    df['isSuprise'] = df['isSuprise_H'] + df['isSuprise_D'] + df['isSuprise_A']
    df = df.drop(columns=['Avg_H', 'Avg_D', 'Avg_A'])
    return df
def get_league_id(session, league_name):
    league = db.session.execute(
        select(League)
        .where(League.code == league_name)
    ).scalar_one_or_none()
    if not league:
        return None
    return league
def get_team_id(session, team_name):
    team = db.session.execute(
        select(Team)
        .where(Team.name == team_name)
    ).scalar_one_or_none()
    if not team:
        return None
    return team
def get_season_id(session, season_name):
    season = db.session.execute(
        select(Season)
        .where(Season.name == season_name)
    ).scalar_one_or_none()
    if not season:
        return None
    return season

def add_matchday_to_season(df):

    matchday_counter = {}

    df['HomeMatchday'] = pd.NA
    df['AwayMatchday'] = pd.NA

    for index, row in df.iterrows():
        season = row['Season']
        home_team = row['HomeTeam']
        away_team = row['AwayTeam']

        if season not in matchday_counter:
            matchday_counter[season] = {}
        if home_team not in matchday_counter[season]:
            matchday_counter[season][home_team] = 0
        if away_team not in matchday_counter[season]:
            matchday_counter[season][away_team] = 0

        matchday_counter[season][home_team] += 1
        matchday_counter[season][away_team] += 1

        df.loc[index, 'HomeMatchday'] = matchday_counter[season][home_team]
        df.loc[index, 'AwayMatchday'] = matchday_counter[season][away_team]

    return df
def get_data_from_top_11(correct, countryInfo, seasonCode):
    name_mapping = correct
    url = f'https://www.football-data.co.uk/{countryInfo[0]}m.php'
    with requests.Session() as session:
        response = session.get(url, headers=headers)
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
        download_response = session.get(download_url, headers=headers)
        if download_response.status_code != 200:
            print(f"Failed to load page {download_url}")
            return
        try:
            enc = detect_encoding(download_response.content)
            df = pd.read_csv(io.StringIO(download_response.content.decode(enc)), encoding=enc, low_memory=False, on_bad_lines='skip')
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
            df["HomeTeam"] = df["HomeTeam"].apply(lambda x: apply_team_mapping(x, name_mapping))
            df["AwayTeam"] = df["AwayTeam"].apply(lambda x: apply_team_mapping(x, name_mapping))


            df = add_matchday_to_season(df)
            df = calculate_is_suprise(df)
            df = create_placement_columns(df)
            df = calculate_statistics_and_consensus(df)


            df = df.sort_values(by='Date')

            with app.app_context():
                league = get_or_create_league(db.session, get_league(df))
                season = get_or_create_season(db.session, get_seasons(df))
                db.session.commit()

                inserted = 0
                updated = 0
                errors = 0
                for _, row in df.iterrows():
                    try:
                        home_team = get_or_create_team(db.session, row['HomeTeam'])
                        away_team = get_or_create_team(db.session, row['AwayTeam'])
                        get_or_create_team_league(db.session, home_team.team_id, league.league_id, season.season_id)
                        get_or_create_team_league(db.session, away_team.team_id, league.league_id, season.season_id)
                        match = db.session.execute(
                            select(FootballMatch)
                            .where(FootballMatch.home_team_id == home_team.team_id,FootballMatch.away_team_id == away_team.team_id, FootballMatch.date==row['Date'])
                        ).scalar_one_or_none()
                        is_new = match is None
                        if is_new:
                            match = FootballMatch(
                                home_team_id=home_team.team_id,
                                away_team_id=away_team.team_id,
                                season_id=season.season_id,
                                league_id=league.league_id,
                                date=row['Date'],
                                result=row['FTR'],
                                home_matchday=row['HomeMatchday'],
                                away_matchday=row['AwayMatchday'],
                                fthg=row['FTHG'],
                                ftag=row['FTAG'],
                                is_surprise=row['isSuprise'],
                                is_suprise_h=row['isSuprise_H'],
                                is_suprise_d=row['isSuprise_D'],
                                is_suprise_a=row['isSuprise_A'],
                                consensus=row['Consensus'],

                                home_elo=None,
                                away_elo=None,
                                home_elo_change=None,
                                away_elo_change=None
                            )
                            db.session.add(match)
                            db.session.flush()
                            check_and_remove_future_match(db.session, home_team.team_id, away_team.team_id, row['Date'])
                        else:
                            match.season_id = season.season_id
                            match.league_id = league.league_id
                            match.result = row['FTR']
                            match.home_matchday = row['HomeMatchday']
                            match.away_matchday = row['AwayMatchday']
                            match.fthg = row['FTHG']
                            match.ftag = row['FTAG']
                            match.is_surprise = row['isSuprise']
                            match.is_suprise_h = row['isSuprise_H']
                            match.is_suprise_d = row['isSuprise_D']
                            match.is_suprise_a = row['isSuprise_A']
                            match.consensus = row['Consensus']
                            db.session.flush()

                        for suffix in ['H', 'D', 'A']:
                            side = 'home' if suffix == 'H' else ('draw' if suffix == 'D' else 'away')
                            stats_data = {
                                'mean': row.get(f'{suffix}_Mean'),
                                'std': row.get(f'{suffix}_Std'),
                                'shannon': row.get(f'{suffix}_Shannon'),
                                'cv': row.get(f'{suffix}_CV'),
                                'gini': row.get(f'{suffix}_Gini'),
                                'hhi': row.get(f'{suffix}_HHI')
                            }
                            stats_data = {k: float(v) for k, v in stats_data.items() if v is not None and pd.notna(v)}
                            if stats_data:
                                MatchStats.create_or_update_stats(
                                    session=db.session,
                                    match_id=match.match_id,
                                    side=side,
                                    stats_data=stats_data
                                )
                        for side in ['home', 'away']:
                            prefix = side.capitalize()
                            match_form = db.session.execute(
                                select(MatchForm)
                                .where(MatchForm.match_id == match.match_id, MatchForm.team_side == side)
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
                                    h2h_last_5_points=None
                                )
                                db.session.add(match_form)
                                db.session.flush()
                            else:
                                match_form.form_last_3 = row[f'{prefix}Form3']
                                match_form.form_last_5 = row[f'{prefix}Form5']
                                match_form.form_season = row[f'{prefix}FormSeason']
                                match_form.goals_last_3 = row[f'{prefix}Goals3']
                                match_form.goals_last_5 = row[f'{prefix}Goals5']
                                match_form.goals_season = row[f'{prefix}GoalsSeason']
                                match_form.team_placement = row[f'{prefix}TeamPlacement']
                        db.session.commit()
                        if is_new:
                            inserted += 1
                        else:
                            updated += 1
                    except Exception as e:
                        db.session.rollback()
                        errors += 1
                        print(f'Error inserting match {row.get("HomeTeam", "?")} vs {row.get("AwayTeam", "?")}: {e}')
                        traceback.print_exc()
                print(f"Data for {countryInfo[1]} {seasonCode}: inserted={inserted}, updated={updated}, errors={errors}")

        except Exception as e:
            print(f"Error processing file {countryInfo[1]} {seasonCode}: {e}")
            traceback.print_exc()

def detect_encoding(byte_content):
    result = chardet.detect(byte_content)
    return result['encoding']

def check_and_remove_future_match(session, home_team_id, away_team_id, match_date):
    future_match = session.execute(
        select(FutureMatch)
        .where(FutureMatch.home_team_id == home_team_id,
               FutureMatch.away_team_id == away_team_id,
               FutureMatch.date == match_date)
    ).scalar_one_or_none()

    if future_match:
        print(f"Match found in FutureMatch table. Removing it as it's now a past match.")
        session.delete(future_match)
        return True

    return False

def correct_date_format(val):
    if isinstance(val, str) and len(val) == 8:
        return val[:6] + "20" + val[6:]
    return val


def scrape_top_11(correct):
    for country, countryValues in countries.items():
        for season, seasonCode in seasons.items():
            get_data_from_top_11(correct, countryValues, seasonCode)
def get_seasons(df):
    seasons = df['Season'].unique()
    if len(seasons) == 1:
        return seasons[0]
    else:

        return seasons[0] if len(seasons) > 0 else None
def get_league(df):
    leagues = df['Div'].unique()
    if len(leagues) == 0:
        return None
    league = leagues[0]
    if league == 'E0':
        return 'premier league'
    elif league == 'SC0':
        return 'spremier league'
    elif league == 'D1':
        return 'bundesliga'
    elif league == 'SP1':
        return 'la liga'
    elif league == 'I1':
        return 'serie a'
    elif league == 'F1':
        return 'ligue 1'
    elif league == 'N1':
        return 'eredivisie'
    elif league == 'B1':
        return 'jupiler league'
    elif league == 'P1':
        return 'liga i'
    elif league == 'T1':
        return 'futbol ligi 1'
    elif league == 'G1':
        return 'ethniki katigoria'
    else:
        return league


def get_or_create_team(session, team_name):
    team = session.execute(
        select(Team)
        .where(Team.name == team_name)
    ).scalar_one_or_none()
    if team is None:
        team = Team(name=team_name)
        session.add(team)
        session.flush()
    return team


def get_or_create_league(session, league_name):
    league = session.execute(
        select(League)
        .where(League.code == league_name)
    ).scalar_one_or_none()
    if league is None:
        league = League(code=league_name)
        session.add(league)
        session.flush()
    return league


def get_or_create_season(session, season_name):
    season = session.execute(
        select(Season)
        .where(Season.name == season_name)
    ).scalar_one_or_none()
    if season is None:
        season = Season(name=season_name)
        session.add(season)
        session.flush()
    return season


def get_or_create_team_league(session, team_id, league_id, season_id):
    team_league = session.execute(
        select(TeamLeague)
        .where(
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


def create_team_name_mapping():
    return {}

def correct_scrape_top_11():
    scrape_top_11({})


if __name__ == "__main__":
    correct_scrape_top_11()