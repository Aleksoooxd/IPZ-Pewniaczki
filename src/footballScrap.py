import copy
import os
import numpy as np
import chardet
import requests
import io
from bs4 import BeautifulSoup
import datetime
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from fuzzywuzzy import process
from sqlalchemy import select
from unidecode import unidecode
from flask_app.app.db import db, app, FootballMatch, MatchStats, MatchForm, Team, League, Season, TeamValue
from src.helpfunctions import hhi_index,shannon_index, coefficient_of_variation, gini_index, calculate_consensus
from src.transfermarktScrap import get_all_teams_from_db

pd.set_option('future.no_silent_downcasting', True)
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}
# Obliczenia związane z sezonami
curr_year = (datetime.datetime.now().year-1) if datetime.datetime.now().month < 8 else datetime.datetime.now().year
deadline = curr_year - 2009
deadline2 = curr_year - 2004 - deadline

# Generowanie kodów sezonów
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
    if date.month >= 8:
        if year >= 2009:
            return f"{year}/{(year + 1) % 100:02d}"
        else:
            return f"{year}/{(year + 1) % 100:01d}"
    else:
        if year >= 2009:
            return f"{year}/{year % 100:02d}"
        else:
            return f"{year}/{year % 100:01d}"

def create_placement_columns(dataframe):
    dataframe['FTHG'] = pd.to_numeric(dataframe['FTHG'], errors='coerce')
    dataframe['FTAG'] = pd.to_numeric(dataframe['FTAG'], errors='coerce')
    dataframe['HomeMatchday'] = pd.to_numeric(dataframe['HomeMatchday'], errors='coerce')
    new_columns = {
        'HomeTeamPlacement': None,
        'AwayTeamPlacement': None,
        'HomeForm3': 0,
        'HomeForm5': 0,
        'HomeFormSeason': 0,
        'AwayForm3': 0,
        'AwayForm5': 0,
        'AwayFormSeason': 0,
        'HomeGoals3': 0,
        'HomeGoals5': 0,
        'HomeGoalsSeason': 0,
        'AwayGoals3': 0,
        'AwayGoals5': 0,
        'AwayGoalsSeason': 0
    }
    new_data = pd.DataFrame({k: [v] * len(dataframe) for k, v in new_columns.items()}, index=dataframe.index)
    dataframe = pd.concat([dataframe, new_data], axis=1)
    def calculate_season_placements(season_df):
        standings = {}
        placements = []
        form_data = {}
        goals_data = {}

        for matchday in sorted(season_df['HomeMatchday'].unique()):
            matchday_df = season_df[season_df['HomeMatchday'] == matchday]

            for _, row in matchday_df.iterrows():
                home_team = row['HomeTeam']
                away_team = row['AwayTeam']
                ftr = row['FTR']
                fthg = row['FTHG']
                ftag = row['FTAG']

                if home_team not in standings:
                    standings[home_team] = {'points': 0, 'goal_diff': 0, 'goals_scored': 0}
                    form_data[home_team] = []
                    goals_data[home_team] = []
                if away_team not in standings:
                    standings[away_team] = {'points': 0, 'goal_diff': 0, 'goals_scored': 0}
                    form_data[away_team] = []
                    goals_data[away_team] = []

                if ftr == 'H':
                    standings[home_team]['points'] += 3
                    form_data[home_team].append(3)
                    form_data[away_team].append(0)
                elif ftr == 'A':
                    standings[away_team]['points'] += 3
                    form_data[home_team].append(0)
                    form_data[away_team].append(3)
                elif ftr == 'D':
                    standings[home_team]['points'] += 1
                    standings[away_team]['points'] += 1
                    form_data[home_team].append(1)
                    form_data[away_team].append(1)

                standings[home_team]['goal_diff'] += fthg - ftag
                standings[home_team]['goals_scored'] += fthg
                standings[away_team]['goal_diff'] += ftag - fthg
                standings[away_team]['goals_scored'] += ftag

                goals_data[home_team].append(fthg)
                goals_data[away_team].append(ftag)

            sorted_standings = sorted(standings.items(), key=lambda x: (
                -x[1]['points'], -x[1]['goal_diff'], -x[1]['goals_scored'], x[0]))
            placement_map = {team[0]: idx + 1 for idx, team in enumerate(sorted_standings)}

            for _, row in matchday_df.iterrows():
                placements.append((placement_map[row['HomeTeam']], placement_map[row['AwayTeam']]))

        return placements, form_data, goals_data, placement_map

    for season in sorted(dataframe['Season'].unique()):
        season_mask = dataframe['Season'] == season
        season_df = dataframe[season_mask].sort_values(by=['HomeMatchday', 'Date'])

        season_placements, form_data, goals_data, final_placements = calculate_season_placements(season_df)

        home_placements, away_placements = zip(*season_placements)
        dataframe.loc[season_mask, 'HomeTeamPlacement'] = home_placements
        dataframe.loc[season_mask, 'AwayTeamPlacement'] = away_placements

        for index, row in season_df.iterrows():
            home_team = row['HomeTeam']
            away_team = row['AwayTeam']
            matchday = row['HomeMatchday']

            home_form3 = sum(form_data[home_team][max(0, matchday - 3):matchday])
            home_form5 = sum(form_data[home_team][max(0, matchday - 5):matchday])
            home_form_season = sum(form_data[home_team][:matchday])

            away_form3 = sum(form_data[away_team][max(0, matchday - 3):matchday])
            away_form5 = sum(form_data[away_team][max(0, matchday - 5):matchday])
            away_form_season = sum(form_data[away_team][:matchday])

            home_goals3 = sum(goals_data[home_team][max(0, matchday - 3):matchday])
            home_goals5 = sum(goals_data[home_team][max(0, matchday - 5):matchday])
            home_goals_season = sum(goals_data[home_team][:matchday])

            away_goals3 = sum(goals_data[away_team][max(0, matchday - 3):matchday])
            away_goals5 = sum(goals_data[away_team][max(0, matchday - 5):matchday])
            away_goals_season = sum(goals_data[away_team][:matchday])

            dataframe.at[index, 'HomeForm3'] = home_form3
            dataframe.at[index, 'HomeForm5'] = home_form5
            dataframe.at[index, 'HomeFormSeason'] = home_form_season
            dataframe.at[index, 'AwayForm3'] = away_form3
            dataframe.at[index, 'AwayForm5'] = away_form5
            dataframe.at[index, 'AwayFormSeason'] = away_form_season
            dataframe.at[index, 'HomeGoals3'] = home_goals3
            dataframe.at[index, 'HomeGoals5'] = home_goals5
            dataframe.at[index, 'HomeGoalsSeason'] = home_goals_season
            dataframe.at[index, 'AwayGoals3'] = away_goals3
            dataframe.at[index, 'AwayGoals5'] = away_goals5
            dataframe.at[index, 'AwayGoalsSeason'] = away_goals_season

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
        values = data[cols].dropna(axis=1).values
        data[f"{result_type}_Mean"] = np.round(np.mean(values, axis=1), 4)
        data[f"{result_type}_Std"] = np.round(np.std(values, axis=1), 4)
        data[f"{result_type}_Shannon"] = [shannon_index(v) for v in values]
        data[f"{result_type}_CV"] = [coefficient_of_variation(v) for v in values]
        data[f"{result_type}_Gini"] = [gini_index(v) for v in values]
        data[f"{result_type}_HHI"] = [hhi_index(v) for v in values]
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
def get_team_value_id(session, team_id, season_id):
    team_values = session.execute(
        select(TeamValue)
        .where(TeamValue.team_id == team_id, TeamValue.season_id == season_id)
        .with_for_update()
    ).scalars().all()

    if not team_values:
        return None
    return team_values[0]
def get_league_id(session, league_name):
    league = db.session.execute(
        select(League)
        .where(League.code == league_name)
        .with_for_update()
    ).scalar_one_or_none()
    if not league:
        return None
    return league
def get_team_id(session, team_name):
    team = db.session.execute(
        select(Team)
        .where(Team.name == team_name)
        .with_for_update()
    ).scalar_one_or_none()
    if not team:
        return None
    return team
def get_season_id(session, season_name):
    season = db.session.execute(
        select(Season)
        .where(Season.name == season_name)
        .with_for_update()
    ).scalar_one_or_none()
    if not season:
        return None
    return season
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
            matchday_counter = {}
            def assign_matchday(row):
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
                row = row.copy()
                row['HomeMatchday'] = matchday_counter[season][home_team]
                row['AwayMatchday'] = matchday_counter[season][away_team]
                return row
            df = calculate_is_suprise(df)
            df = df.apply(assign_matchday, axis=1)
            df = create_placement_columns(df)
            df = calculate_statistics_and_consensus(df)

            with app.app_context():
                league = get_league_id(db.session, get_league(df))
                season = get_season_id(db.session, get_seasons(df))
                for _, row in df.iterrows():
                    if league is None or season is None:
                        print(f"Missing league {get_league(df)} or season {get_seasons(df)}")
                        continue
                    home_team = get_team_id(db.session, row['HomeTeam'])
                    away_team = get_team_id(db.session, row['AwayTeam'])
                    if home_team is None or away_team is None:
                        print(f"Skipping match {row['HomeTeam']} vs {row['AwayTeam']} - missing team names")
                        continue
                    homet_value_id = get_team_value_id(db.session, home_team.team_id, season.season_id)
                    awayt_value_id = get_team_value_id(db.session, away_team.team_id, season.season_id)
                    if homet_value_id is None or awayt_value_id is None:
                        print(f"Skipping match {row['HomeTeam']} vs {row['AwayTeam']} - missing team values")
                        continue
                    # Dodawanie meczu
                    match = db.session.execute(
                        select(FootballMatch)
                        .where(FootballMatch.home_team_id == home_team.team_id,FootballMatch.away_team_id == away_team.team_id, FootballMatch.date==row['Date'])
                        .with_for_update()
                    ).scalar_one_or_none()
                    if not match:
                        match = FootballMatch(
                            home_team_id=home_team.team_id,
                            home_value_id = homet_value_id.value_id,
                            away_value_id = awayt_value_id.value_id,
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
                            consensus=row['Consensus']
                        )
                        db.session.add(match)
                        db.session.flush()
                    else:
                        print(
                            f'Skipping match {_} match data for {row["HomeTeam"]} vs {row["AwayTeam"]}, already exists')
                        continue

                    #Indexy statystyczne dla Home, Draw i Away
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
                    # Forma drużyn
                    for side in ['home', 'away']:
                        prefix = side.capitalize()
                        match_form = db.session.execute(
                            select(MatchForm)
                            .where(MatchForm.match_id == match.match_id, MatchForm.team_side == side)
                            .with_for_update().with_for_update()
                        ).scalar_one_or_none()
                        if not match_form:
                            match_form = match_form = MatchForm(
                                match_id=match.match_id,
                                team_side=side,
                                form_last_3=row[f'{prefix}Form3'],
                                form_last_5=row[f'{prefix}Form5'],
                                form_season=row[f'{prefix}FormSeason'],
                                goals_last_3=row[f'{prefix}Goals3'],
                                goals_last_5=row[f'{prefix}Goals5'],
                                goals_season=row[f'{prefix}GoalsSeason'],
                                team_placement=row[f'{prefix}TeamPlacement'],
                                team_strength=None
                            )
                            db.session.add(match_form)
                            db.session.flush()
                    db.session.commit()
                    print(f'Inserted {_} match data for {row["HomeTeam"]} vs {row["AwayTeam"]}')
            print(f"Data successfully inserted into the database for {countryInfo[1]} {seasonCode}")

        except Exception as e:
            print(f"Error processing file: {e}")

def detect_encoding(byte_content):
    result = chardet.detect(byte_content)
    return result['encoding']


def correct_date_format(val):
    if isinstance(val, str) and len(val) == 8:
        return val[:6] + "20" + val[6:]
    return val


def scrape_top_11(correct):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for country, countryValues in countries.items():
            for season, seasonCode in seasons.items():
                futures.append(executor.submit(get_data_from_top_11, correct, countryValues, seasonCode))
        for future in futures:
            future.result()
def get_seasons(df):
    seasons = df['Season'].unique()
    if len(seasons) == 1:
        return seasons[0]
    else:
        # Handle case with multiple seasons or return the first one
        return seasons[0] if len(seasons) > 0 else None
def get_league(df):
    leagues = df['Div'].unique()
    if len(leagues) == 0:
        return None
    league = leagues[0]  # Take the first league if there are multiple
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


def create_team_name_mapping():
    list_2 = sorted(list(get_all_teams_from_db()))
    list_1 = sorted(list(scrape_team_names_only()))
    temp_list_1 = copy.deepcopy(list_1)
    temp_list_2 = copy.deepcopy(list_2)
    THRESHOLD = 95
    correct = {}
    while temp_list_1 and temp_list_2:
        mapping = {}
        for club in temp_list_1:
            match, score = process.extractOne(club, temp_list_2)
            if score >= THRESHOLD:
                mapping[club] = match
            else:
                mapping[club] = None
        matched = {k: v for k, v in mapping.items() if v is not None}
        unmatched = {k: v for k, v in mapping.items() if v is None}
        correct.update(matched)
        for key, value in matched.items():
            if key in temp_list_1:
                temp_list_1.remove(key)
            if value in temp_list_2:
                temp_list_2.remove(value)
        if unmatched:
            THRESHOLD -= 1
            if THRESHOLD < 0:
                break
        else:
            break
    print(f"\nTotal teams in football-data: {len(list_1)}")
    print(f"Total teams in database: {len(list_2)}")
    print(f"Initial matches found: {len(correct)}")
    print(f"Remaining unmapped in football-data: {len(temp_list_1)}")
    print(f"Remaining unmapped in database: {len(temp_list_2)}")
    print(f"Remaining unmapped in database: {temp_list_2}")
    print(f'Mapped teams: {correct}')
    return correct

def correct_scrape_top_11():
    correct = create_team_name_mapping()
    scrape_top_11(correct)


if __name__ == "__main__":
    correct_scrape_top_11()