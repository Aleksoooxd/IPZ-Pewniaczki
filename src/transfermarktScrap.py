import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime
from concurrent.futures import ThreadPoolExecutor
from flask_app.app.db import db,app, Team, League, Season, TeamLeague, TeamValue
import os
from sqlalchemy.exc import IntegrityError

# Adres strony głównej
site = "https://www.transfermarkt.com/"
curr_year = (datetime.datetime.now().year - 1) if datetime.datetime.now().month < 8 else datetime.datetime.now().year

# Ścieżki do poszczególnych lig
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

# Generowanie sezonów dla wszystkich lig
season_dict = {}
for year in range(2004, curr_year + 1):  # Wszystkie sezony od 2004/05
    season_dict[f'{year}/{(year % 100) + 1}'] = f"/saison_id/{year}"

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}

# Mapa nazw klubów do znormalizowanych nazw
club_name_mapping = {
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
    """Normalize club names using the mapping dictionary"""
    return club_name_mapping.get(club_name, club_name)


def get_or_create_team(session, team_name):
    """Get existing team or create new one"""
    normalized_name = normalize_club_name(team_name)
    team = session.query(Team).filter_by(name=normalized_name).first()
    if not team:
        team = Team(name=normalized_name)
        session.add(team)
        session.commit()
    return team


def get_or_create_league(session, league_name):
    """Get existing league or create new one"""
    # For league code, we'll use the first part of the URL path
    path_part = leagues_dict[league_name].split('/')[0]
    league = session.query(League).filter_by(code=path_part).first()
    if not league:
        league = League(code=path_part)
        session.add(league)
        session.commit()
    return league


def get_or_create_season(session, season_name):
    """Get existing season or create new one"""
    season = session.query(Season).filter_by(name=season_name).first()
    if not season:
        season = Season(name=season_name)
        session.add(season)
        session.commit()
    return season


def create_team_value(session, team_id, season_id, value_str):
    """Create team value record after converting the string value to float"""
    try:
        # Convert value string (like "€5.00m") to float
        if value_str == 'N/A':
            return None
        if value_str.endswith('bn'):
            value = float(value_str.replace('€', '').replace('bn', '').strip())*1000
        else:
            value = float(value_str.replace('€', '').replace('m', '').strip())
        team_value = TeamValue(
            team_id=team_id,
            season_id=season_id,
            value=value
        )
        session.add(team_value)
        session.commit()
        return team_value
    except (ValueError, AttributeError):
        print(f"Could not parse value: {value_str}")
        return None


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
            # Get or create league and season in database
            league = get_or_create_league(db.session, league_name)
            season = get_or_create_season(db.session, season_name)

            for i, name_td in enumerate(club_names):
                try:
                    original_club_name = name_td.text.strip()
                    club_value_str = club_values[((i + 1) * 2) + 1].text.strip()

                    # Get or create team
                    team = get_or_create_team(db.session, original_club_name)

                    # Create team value record
                    create_team_value(db.session, team.team_id, season.season_id, club_value_str)

                    # Create team-league-season association
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
                    print(f"Database error for {original_club_name}: {e}")
                    continue
                except Exception as e:
                    print(f"Unexpected error for {original_club_name}: {e}")
                    continue


def scrape_leagues():
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for league, path in leagues_dict.items():
            # Wszystkie sezony dla innych lig
            for season, spath in season_dict.items():
                futures.append(
                    executor.submit(fetch_league_data, league, season, path, spath)
                )
        for future in futures:
            future.result()


def scrape_transfermarkt():
    try:
        scrape_leagues()
        print("Data successfully saved to database")
    except Exception as e:
        print(f"Error during scraping: {e}")
        with app.app_context():
            db.session.rollback()