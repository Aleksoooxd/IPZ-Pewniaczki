import os
import requests
import io
from bs4 import BeautifulSoup
import datetime
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
# Ustawienia nagłówków
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}
# Obliczenia związane z sezonami
curr_year = datetime.datetime.now().year
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
# Informacje o krajach i ligach
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
# Funkcja do pobierania danych dla top 5 lig
def get_data_from_top_11(countryInfo, seasonCode):
    url = f'https://www.football-data.co.uk/{countryInfo[0]}m.php'
    with requests.Session() as session:
        response = session.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to load page {url}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        # Znajdowanie linków do plików CSV
        all_a_tags = soup.find('a', string=f'{countryInfo[1]}')
        if not all_a_tags:
            print(f"Link for {countryInfo[1]} {seasonCode} not found")
            return

        download_link = all_a_tags.get('href').split('/')
        download_link[1] = f'{seasonCode}'
        download_link = '/'.join(download_link)

        # Pobieranie pliku CSV
        download_url = f'https://www.football-data.co.uk/{download_link}'
        download_response = session.get(download_url, headers=headers)
        if download_response.status_code != 200:
            print(f"Failed to load page {download_url}")
            return

        # Zapis pliku do odpowiedniego folderu
        filepath = f'../Data/Matches Results/{countryInfo[0]}/'
        os.makedirs(filepath, exist_ok=True)  # Tworzenie folderu, jeśli nie istnieje
        filename = f'{countryInfo[1].replace(" ", "")}_{seasonCode}.csv'
        fullname = os.path.join(filepath, filename)
        with open(fullname, 'wb') as file:
            file.write(download_response.content)
        print(f"Plik został pobrany i zapisany! Ścieżka: {fullname}")
# Pobieranie danych dla top 5 lig równolegle
def scrape_top_11():
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for country, countryValues in countries.items():
            for season, seasonCode in seasons.items():
                futures.append(executor.submit(get_data_from_top_11, countryValues, seasonCode))
        for future in futures:
            future.result()  # Czekanie na zakończenie
# Wywołanie funkcji
scrape_top_11()
