import csv
import copy
from fuzzywuzzy import process
import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime
from concurrent.futures import ThreadPoolExecutor
import re
from sqlalchemy import select
from flask_app.app.db import db, app, Team, League, Season, TeamLeague, TeamValue, FutureMatch
from sqlalchemy.exc import IntegrityError
site = "https://www.transfermarkt.com/"
curr_year = (datetime.datetime.now().year - 1) if datetime.datetime.now().month < 8 else datetime.datetime.now().year
today = datetime.datetime.today()
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
    'Roda JC': 'Roda',
    'Málaga CF': 'Malaga',
    'Paris SG': 'Paris Saint-Germain',
    'Twente FC': 'Twente Enschede FC',
    'Alavés': 'Deportivo Alavés'

}

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}

season_dict = {}
for year in range(2004, curr_year + 1):
    season_dict[f'{year}/{(year % 100) + 1}'] = f"/saison_id/{year}"
last_season_key = list(season_dict.keys())[-1]

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


def fetch_league_data(league_name, season_name, path, spath, max_retries=20, retry_delay=15):
    url = site + path + spath
    retries = 0

    while retries <= max_retries:
        try:
            print(f"Fetching: {league_name}, Season: {season_name}, URL: {url} (Attempt {retries + 1})")
            with requests.Session() as session:
                response = session.get(url, headers=headers)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    club_names = soup.find_all('td', class_='hauptlink no-border-links')
                    club_values = soup.find_all('td', class_='rechts')

                    if club_names and club_values:
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
                        return True
                    else:
                        print(f"No club data found for {league_name} {season_name} (Attempt {retries + 1})")
                else:
                    print(
                        f"Error fetching data for {league_name} {season_name}: {response.status_code} (Attempt {retries + 1})")

            wait_time = retry_delay * (2 ** retries)
            print(f"Retrying in {wait_time} seconds...")
            import time
            time.sleep(wait_time)
            retries += 1

        except requests.exceptions.RequestException as e:
            print(f"Request error for {league_name} {season_name}: {e} (Attempt {retries + 1})")
            wait_time = retry_delay * (2 ** retries)
            print(f"Retrying in {wait_time} seconds...")
            import time
            time.sleep(wait_time)
            retries += 1

    print(f"Failed to fetch data for {league_name} {season_name} after {max_retries} retries")
    return False

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

def get_current_season():
    current_year = datetime.datetime.now().year
    if datetime.datetime.now().month < 8:
        season = f"{current_year - 1}/{str(current_year)[-2:]}"
    else:
        season = f"{current_year}/{str(current_year + 1)[-2:]}"
    return season

def get_all_teams_current_season_from_db():
    with app.app_context():
        current_season = get_current_season()
        season = db.session.query(Season).filter(Season.name == current_season).first()
        if not season:
            return []
        teams = db.session.query(Team.name).join(TeamLeague).filter(TeamLeague.season_id == season.season_id).all()
        return [team.name for team in teams]

def scrape_transfermarkt():
    try:
        scrape_leagues()
        scrape_fixtures()
        print("Data successfully saved to database")
        print(get_all_teams_from_db())
    except Exception as e:
        print(f"Error during scraping: {e}")
        with app.app_context():
            db.session.rollback()

def convert_date(date_str):
    if isinstance(date_str, str):
        splited = date_str.split("/")
        date_str = splited[0]+"/"+splited[1]+"/"+"20"+splited[2]
    return datetime.datetime.strptime(date_str, "%m/%d/%Y")

def convert_time(time_str):
    if isinstance(time_str, str):
        time_str =  datetime.datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")
    return time_str

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
            headline = box.select_one("div.content-box-headline")
            matchday = headline.text.strip() if headline else "N/A"
            matchday = re.sub(r"[^\d]", "", matchday)

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
                hteam = row.select_one("td.text-right.no-border-rechts.hauptlink a")
                ateam = row.select_one("td.no-border-links.hauptlink a")
                if hteam is None and ateam is None:
                    continue
                if date is not None:
                    if date.text.strip() is not None:
                        last_date = date.text.strip()
                        last_date = convert_date(last_date)

                if time is not None:
                    if time.text.strip() is not None and time.text.strip() != "":
                        last_time = time.text.strip()
                        last_time = convert_time(last_time)
                home_team = hteam.text.strip()
                away_team = ateam.text.strip()
                if last_date < today:
                    continue

                all_fixtures.append({
                            "league": league_name.lower(),
                            "season": get_current_season(),
                            "matchday": matchday,
                            "date": last_date,
                            "time": last_time,
                            "home_team": home_team,
                            "away_team": away_team
                })
    db_teams = get_all_teams_current_season_from_db()
    transfermarkt_teams = set()
    all_fixtures = apply_team_mapping(all_fixtures, club_name_mapping)
    for fixture in all_fixtures:
        transfermarkt_teams.add(fixture["home_team"])
        transfermarkt_teams.add(fixture["away_team"])
    transfermarkt_teams = list(transfermarkt_teams)
    normalizedtm = set()
    for team in transfermarkt_teams:
        normalizedtm.add(normalize_club_name(team))
    mapping = create_team_name_mapping(db_teams,normalizedtm)
    all_fixtures = apply_team_mapping(all_fixtures,mapping)
    with app.app_context():
        for fixture in all_fixtures:
            league = get_league_id(db.session, fixture['league'])
            season = get_season_id(db.session, fixture['season'])
            home_team = get_team_id(db.session, fixture['home_team'])
            away_team = get_team_id(db.session, fixture['away_team'])
            if home_team is None or away_team is None or league is None or season is None:
                print("Missing team/league/home_team/away_team")
                continue
            futurematch = db.session.execute(
                select(FutureMatch)
                .where(FutureMatch.home_team_id == home_team.team_id, FutureMatch.away_team_id == away_team.team_id,
                       FutureMatch.date == fixture['date'])
                .with_for_update()
            ).scalar_one_or_none()
            if not futurematch:
                futurematch = FutureMatch(
                    home_team_id=home_team.team_id,
                    away_team_id=away_team.team_id,
                    season_id=season.season_id,
                    league_id=league.league_id,
                    date=fixture['date'],
                    time=fixture['time'],
                    matchday=fixture['matchday']
                )
                db.session.add(futurematch)
                db.session.flush()
                db.session.commit()
                print(f'Inserted match data for {fixture["home_team"]} vs {fixture["away_team"]}')
            else:
                print(f'Skipping match match data for {fixture["home_team"]} vs {fixture["away_team"]}, already exists')
                continue

def apply_team_mapping(fixtures, mapping):
    for fixture in fixtures:
        fixture["home_team"] = mapping.get(fixture["home_team"], fixture["home_team"])
        fixture["away_team"] = mapping.get(fixture["away_team"], fixture["away_team"])
    return fixtures

def create_team_name_mapping(db_teams, scrapped_teams):
    list_2 = sorted(list(db_teams))
    list_1 = sorted(list(scrapped_teams))
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