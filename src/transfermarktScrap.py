import pandas as pd
import requests
from bs4 import BeautifulSoup
import csv
import datetime
from concurrent.futures import ThreadPoolExecutor
import os

# Adres strony głównej
site = "https://www.transfermarkt.com/"
curr_year = datetime.datetime.now().year

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
all_clubs_data = {}
def fetch_league_data(league, season, path, spath):
    url = site + path + spath
    print(f"Fetching: {league}, Season: {season}, URL: {url}")
    with requests.Session() as session:
        response = session.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching data for {league} {season}: {response.status_code}")
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        club_names = soup.find_all('td', class_='hauptlink no-border-links')
        club_values = soup.find_all('td', class_='rechts')
        league_data = {}
        for i, name_td in enumerate(club_names):
            try:
                club_name = name_td.text.strip()
                club_value = club_values[((i + 1) * 2) + 1].text.strip()

                if club_name not in all_clubs_data:
                    all_clubs_data[club_name] = {}

                all_clubs_data[club_name][season] = club_value
                league_data[club_name] = club_value
            except IndexError:
                continue  # Dalsza obsługa w przypadku niezgodności danych
        return league_data

# Pobieranie danych wielowątkowo
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
def modify_transfermarkt(temp_df,file_path):
    temp_df['Club'] = temp_df['Club'].replace({
        'SPAL 2013': 'SPAL',
        'Parma Calcio 1913': 'Parma FC',
        'Beerschot AC (-2013)': 'Germinal',
        'Büyüksehir Belediyespor': 'Buyuksehyr',
        'Basaksehir FK' : 'Buyuksehyr',
        'Istanbul Büyüksehir Belediyespor': 'Buyuksehyr',
        'Apollon Smyrnis': 'Apollon',
        'Lierse SK (-2018)': 'Lierse',
        'Büyüksehir Belediye Erzurumspor': 'Erzurum BB',
        '1.FC Nuremberg': 'Nurnberg',
        'Desportivo Aves (- 2020)' : 'AVS',
        'Avs Futebol' : 'AVS',
        'Germinal Beerschot Antwerpen' : 'Germinal',
        'AEK Athens': 'AEK',
        'RAEC Mons (-2015)' : 'Bergen',
        'Sporting CP' : 'Sp Lisbon',
        'Aris Thessaloniki' : 'Aris',
        'Iraklis Thessaloniki': 'Iraklis',
        'Asteras Aktor': 'Asteras Tripolis',
        'AOK Kerkyra': 'Kerkyra',
        'AO Kerkyra': 'Kerkyra',
        'Akhisarspor': 'Akhisar Belediyespor',
        'Büyüksehir Belediyesi Ankaraspor': 'Ankaraspor',
        'Excelsior Rotterdam': 'Excelsior',
        'FC Brüssel' : 'FC Brussels',
        'FC Molenbeek Brüssel' : 'FC Brussels',
        'FC Molenbeek Brüssel Strombeek' : 'FC Brussels',
        'Kardemir DC Karabükspor' : 'Karabukspor',
        'Kardemir Karabükspor' : 'Karabukspor',
        'Skoda Xanthi' : 'Xanthi',
        'AO Xanthi' : 'Xanthi',
        'Royal Excel Mouscron (-2022)' : 'Mouscron',
        'Excelsior Mouscron (-2009)' : 'Mouscron',
        'B SAD' : 'Belenses',
        'CF Os Belenenses' : 'Belenses',
        'RC Lens' : 'Lens',
        'Roda JC Kerkrade' : 'Roda',
        'Roda JC': 'Roda'

    })
    temp_df = temp_df.groupby('Club', as_index=False).first()
    temp_df.to_csv(file_path, index=False)


def save(auto_save=False):
    save_to_csv =""
    if not auto_save:
        save_to_csv = input("Czy chcesz stworzyć raport CSV z tych danych? (T/n): ").strip().upper()
    if (save_to_csv == 'T') or auto_save:
        filepath = '../Data/Club Info/'
        filename = 'clubs_report_from_transfermarkt.csv'
        os.makedirs(filepath, exist_ok=True)  # Tworzenie folderu jeśli nie istnieje

        headers_csv = ['Club'] + list(season_dict.keys())

        with open(filepath + filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers_csv)

            for club_name, values in all_clubs_data.items():
                row = [club_name]
                for season in season_dict.keys():
                    row.append(values.get(season, 'N/A'))
                writer.writerow(row)
        df = pd.read_csv(filepath+filename)
        modify_transfermarkt(df,filepath+filename)

        print(f"Raport został zapisany jako {filepath + filename}")
    else:
        print("Raport CSV nie został zapisany.")
def scrape_transfermarkt():
    scrape_leagues()
    save(True)