import csv

import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime
from concurrent.futures import ThreadPoolExecutor
import re
from sqlalchemy import select

from flask_app.app.db import db, app, Team, League, Season, TeamLeague, TeamValue
import os
from threading import Lock
from sqlalchemy.exc import IntegrityError

site = "https://www.transfermarkt.com/"
curr_year = (datetime.datetime.now().year - 1) if datetime.datetime.now().month < 8 else datetime.datetime.now().year

leagues_dict = {
    'Premier League': "premier-league/startseite/wettbewerb/GB1",
    'La Liga': "laliga/startseite/wettbewerb/ES1",
    'Bundesliga': "bundesliga/startseite/wettbewerb/L1",
    'Serie A': "serie-a/startseite/wettbewerb/IT1",
    'Ligue 1': "ligue-1/startseite/wettbewerb/FR1",
    'SPremier League': "scottish-premiership/startseite/wettbewerb/SC1",
    'Eredivisie': "eredivisie/startseite/wettbewerb/NL1",
    'Jupiler League': "jupiler-pro-league/startseite/wettbewerb/BE1",
    'Liga I': "liga-nos/startseite/wettbewerb/PO1",
    'Futbol Ligi 1': "super-lig/startseite/wettbewerb/TR1",
    'Ethniki Katigoria': "super-league-1/startseite/wettbewerb/GR1"
}

leagues_fixtures_dict = {
    'Premier League': "premier-league/gesamtspielplan/wettbewerb/GB1",
    'La Liga': "laliga/gesamtspielplan/wettbewerb/ES1",
    'Bundesliga': "bundesliga/gesamtspielplan/wettbewerb/L1",
    'Serie A': "serie-a/gesamtspielplan/wettbewerb/IT1",
    'Ligue 1': "ligue-1/gesamtspielplan/wettbewerb/FR1",
    'SPremier League': "scottish-premiership/gesamtspielplan/wettbewerb/SC1",
    'Eredivisie': "eredivisie/gesamtspielplan/wettbewerb/NL1",
    'Jupiler League': "jupiler-pro-league/gesamtspielplan/wettbewerb/BE1",
    'Liga I': "liga-nos/gesamtspielplan/wettbewerb/PO1",
    'Futbol Ligi 1': "super-lig/gesamtspielplan/wettbewerb/TR1",
    'Ethniki Katigoria': "super-league-1/gesamtspielplan/wettbewerb/GR1"
}

season_dict = {}
for year in range(2004, curr_year + 1):
    season_dict[f'{year}/{(year % 100) + 1}'] = f"/saison_id/{year}"
last_season_key = list(season_dict.keys())[-1]
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}

club_name_mapping = {
    'CF União Madeira (-2021)' : 'Uniao Madeira',
    'CF Belenenses' : 'Belenses',
    'AO Kerkyraikos' : "Kerkyra",
    'AO Chalkidona Near-East': 'Atromitos Athens',
    'SPAL 2013': 'SPAL',
    'Parma Calcio 1913': 'Parma FC',
    'Beerschot AC (-2013)': 'Germinal',
    'Büyüksehir Belediyespor': 'Buyuksehyr',
    'Basaksehir FK': 'Buyuksehyr',
    'Istanbul Büyüksehir Belediyespor': 'Buyuksehyr',
    'Apollon Smyrnis': 'Apollon',
    'Lierse SK (-2018)': 'Lierse',
    'Büyüksehir Belediye Erzurumspor': 'Erzurum BB',
    '1.FC Nuremberg': 'Nurnberg',
    'Desportivo Aves (- 2020)': 'AVS',
    'Avs Futebol': 'AVS',
    'Germinal Beerschot Antwerpen': 'Germinal',
    'AEK Athens': 'AEK',
    'RAEC Mons (-2015)': 'Bergen',
    'Sporting CP': 'Sp Lisbon',
    'Aris Thessaloniki': 'Aris',
    'Iraklis Thessaloniki': 'Iraklis',
    'Asteras Aktor': 'Asteras Tripolis',
    'AOK Kerkyra': 'Kerkyra',
    'AO Kerkyra': 'Kerkyra',
    'Akhisarspor': 'Akhisar Belediyespor',
    'Büyüksehir Belediyesi Ankaraspor': 'Ankaraspor',
    'Excelsior Rotterdam': 'Excelsior',
    'FC Brüssel': 'FC Brussels',
    'FC Molenbeek Brüssel': 'FC Brussels',
    'FC Molenbeek Brüssel Strombeek': 'FC Brussels',
    'Kardemir DC Karabükspor': 'Karabukspor',
    'Kardemir Karabükspor': 'Karabukspor',
    'Skoda Xanthi': 'Xanthi',
    'AO Xanthi': 'Xanthi',
    'Royal Excel Mouscron (-2022)': 'Mouscron',
    'Excelsior Mouscron (-2009)': 'Mouscron',
    'B SAD': 'Belenses',
    'CF Os Belenenses': 'Belenses',
    'RC Lens': 'Lens',
    'Roda JC Kerkrade': 'Roda',
    'Roda JC': 'Roda'
}

def normalize_club_name(club_name):
    cleaned_name = ' '.join(club_name.strip().split())
    if cleaned_name in club_name_mapping:
        return club_name_mapping[cleaned_name]
    lower_name = cleaned_name.lower()
    for key in club_name_mapping:
        if key.lower() == lower_name:
            return club_name_mapping[key]
    return cleaned_name

def get_or_create_team(session, team_name):
    team = session.execute(
        select(Team)
        .where(Team.name == team_name)
        .with_for_update()
    ).scalar_one_or_none()
    if not team:
        team = Team(name=team_name)
        session.add(team)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            team = session.execute(
                select(Team)
                .where(Team.name == team_name)
            ).scalar_one()
    return team

def get_or_create_league(session, league_name):
    league = session.execute(
        select(League)
        .where(League.code == league_name)
        .with_for_update()
    ).scalar_one_or_none()
    if not league:
        league = League(code=league_name.lower())
        session.add(league)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            league = session.execute(
                select(League)
                .where(League.code == league_name)
            ).scalar_one()
    return league

def get_or_create_season(session, season_name):
    season = session.execute(
        select(Season)
        .where(Season.name == season_name)
        .with_for_update()
    ).scalar_one_or_none()
    if not season:
        season = Season(name=season_name)
        session.add(season)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            season = session.execute(
                select(Season)
                .where(Season.name == season_name)
            ).scalar_one()
    return season

def get_or_create_team_value(session, team_id, season_id, value_str):
    team_value = db.session.execute(
        select(TeamValue)
        .where(TeamValue.team_id == team_id, TeamValue.season_id == season_id)
        .with_for_update()
    ).scalar_one_or_none()
    if not team_value:
        try:
            if value_str == 'N/A':
                return None
            if value_str.endswith('bn'):
                value = float(value_str.replace('€', '').replace('bn', '').strip()) * 1000
            else:
                value = float(value_str.replace('€', '').replace('m', '').strip())
            team_value = TeamValue(
                team_id=team_id,
                season_id=season_id,
                value=value
            )
            session.add(team_value)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                team_value = session.execute(
                    select(TeamValue)
                    .where(TeamValue.team_id == team_id, TeamValue.season_id==season_id)
                ).scalar_one()
            return team_value
        except (ValueError, AttributeError):
            print(f"Could not parse value: {value_str}")
            return None
    return team_value

def fetch_league_data(league_name, season_name, path, spath):
    url = site + path + spath
    print(f"Fetching: {league_name}, Season: {season_name}, URL: {url}")
    with requests.Session() as session:
        response = session.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching data for {league_name} {season_name}: {response.status_code}")
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        club_names = soup.find_all('td', class_='hauptlink no-border-links')
        club_values = soup.find_all('td', class_='rechts')
        with app.app_context():
            league = get_or_create_league(db.session, league_name)
            season = get_or_create_season(db.session, season_name)
            for i, name_td in enumerate(club_names):
                try:
                    original_club_name = name_td.text.strip()
                    normalized_club_name = normalize_club_name(original_club_name)
                    club_value_str = club_values[((i + 1) * 2) + 1].text.strip()
                    team = get_or_create_team(db.session, normalized_club_name)
                    get_or_create_team_value(db.session, team.team_id, season.season_id, club_value_str)
                    team_league = db.session.query(TeamLeague).filter_by(
                        team_id=team.team_id,
                        league_id=league.league_id,
                        season_id=season.season_id
                    ).first()
                    if not team_league:
                        team_league = TeamLeague(
                            team_id=team.team_id,
                            league_id=league.league_id,
                            season_id=season.season_id
                        )
                        db.session.add(team_league)
                        db.session.commit()
                except IndexError:
                    continue
                except IntegrityError as e:
                    db.session.rollback()
                    print(f"Database error for {normalized_club_name}: {e}")
                    continue
                except Exception as e:
                    print(f"Unexpected error for {normalized_club_name}: {e}")
                    continue

def scrape_leagues():
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for league, path in leagues_dict.items():
            for season, spath in season_dict.items():
                futures.append(
                    executor.submit(fetch_league_data, league, season, path, spath)
                )
        for future in futures:
            future.result()
def get_all_teams_from_db():
    with app.app_context():
        teams = db.session.query(Team).all()
        return [team.name for team in teams]
def scrape_transfermarkt():
    try:
        scrape_leagues()
        print("Data successfully saved to database")
        print(get_all_teams_from_db())
    except Exception as e:
        print(f"Error during scraping: {e}")
        with app.app_context():
            db.session.rollback()


def scrape_fixtures():
    all_fixtures = []

    for league_name, url_path in leagues_fixtures_dict.items():
        url = site + url_path + season_dict[last_season_key]
        print(f"Scraping fixtures from {url} for {league_name}")
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch fixtures for {league_name}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        boxes = soup.select("div.box")

        for box in boxes:
            # Pobieramy numer kolejki
            headline = box.select_one("div.content-box-headline")
            round_number = headline.text.strip() if headline else "N/A"
            round_number = re.sub(r"[^\d]", "", round_number)

            table = box.select_one("table")
            if not table:
                continue

            rows = table.select("tbody > tr")
            rows = [row for row in rows if 'bg_blau_20' not in row.get('class', [])]
            last_date = 'N/A'
            last_time = 'N/A'
            for row in rows:
                date = row.select_one("td.hide-for-small a")
                time = row.select_one("td.zentriert.hide-for-small")
                if date is not None:
                    if date.text.strip() is not None:
                        last_date = date.text.strip()
                if time is not None:
                    if time.text.strip() is not None and time.text.strip() != "":
                        last_time = time.text.strip()
                print(last_date, last_time)

                # Pobierz datę i godzinę (jeśli obecne)
                # if len(cols) >= 2:
                #     raw_date = cols[0].text.strip()
                #     raw_time = cols[1].text.strip()

                #     date_match = re.search(r"\d{2}\.\d{2}\.\d{4}", raw_date)
                #     if date_match:
                #         try:
                #             parsed_date = datetime.datetime.strptime(date_match.group(), "%d.%m.%Y")
                #             date_str = parsed_date.strftime("%d/%m/%Y")
                #         except:
                #             pass  # zostaw pustą datę
                #
                #     time_match = re.search(r"\d{2}:\d{2}", raw_time)
                #     if time_match:
                #         current_time = time_match.group()
                #
                # # Wiersz z meczem
                # if row.select("td.hauptlink"):
                #     try:
                #         score_text = cols[4].text.strip()
                #         if score_text != "-:-":
                #             continue  # mecz już się odbył
                #
                #         home_raw = ' '.join(cols[2].text.split())
                #         home_team = re.sub(r"\(\d+\.\)\s*", "", home_raw)
                #
                #         away_raw = ' '.join(cols[6].text.split())
                #         away_team = re.sub(r"\(\d+\.\)\s*", "", away_raw)
                #
                #         all_fixtures.append({
                #             "league": league_name,
                #             "round": round_number,
                #             "date": date_str,  # może być pusta
                #             "time": current_time if current_time else "",
                #             "home_team": home_team,
                #             "away_team": away_team
                #         })
                #
                #     except Exception as e:
                #         print(f"Błąd przy przetwarzaniu meczu: {e}")
                #         continue

    # Zapis do pliku CSV
    with open('upcoming_fixtures.csv', mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["league", "round", "date", "time", "home_team", "away_team"])
        writer.writeheader()
        writer.writerows(all_fixtures)

    print("✅ Zapisano dane do 'upcoming_fixtures.csv'")

scrape_fixtures()
