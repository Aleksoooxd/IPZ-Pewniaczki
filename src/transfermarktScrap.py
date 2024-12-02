import requests
from bs4 import BeautifulSoup
import csv
import datetime
from concurrent.futures import ThreadPoolExecutor
import os

# Adres strony głównej
site = "https://www.transfermarkt.com/"
curr_year = datetime.datetime.now().year
deadline = curr_year - 2003

# Ścieżki do poszczególnych lig
leagues_dict = {
    'Premier League': "premier-league/startseite/wettbewerb/GB1",
    'La Liga': "laliga/startseite/wettbewerb/ES1",
    'Bundesliga': "bundesliga/startseite/wettbewerb/L1",
    'Serie A': "serie-a/startseite/wettbewerb/IT1",
    'Ligue 1': "ligue-1/startseite/wettbewerb/FR1",
    'PKO BP Ekstraklasa': "pko-bp-ekstraklasa/startseite/wettbewerb/PL1"
}

# Generowanie sezonów
season_dict = {}
for i in range(deadline):
    year = curr_year - i
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
            for season, spath in season_dict.items():
                futures.append(
                    executor.submit(fetch_league_data, league, season, path, spath)
                )
        for future in futures:
            future.result()  # Czekanie na zakończenie

scrape_leagues()

# Zapis do CSV
save_to_csv = input("Czy chcesz stworzyć raport CSV z tych danych? (T/n): ").strip().upper()
if save_to_csv == 'T':
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

    print(f"Raport został zapisany jako {filepath + filename}")
else:
    print("Raport CSV nie został zapisany.")
