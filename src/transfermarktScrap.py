import requests
from bs4 import BeautifulSoup
import csv
import datetime
# Adres strony głównej
site = "https://www.transfermarkt.com/"
curr_year = datetime.datetime.now().year
curr_year_2_digits = curr_year % 100
deadline = curr_year-2003
# Ścieżki do poszczególnych lig
leagues_dict = {
    'Premier League': "premier-league/startseite/wettbewerb/GB1",
    'La Liga': "laliga/startseite/wettbewerb/ES1",
    'Bundesliga': "bundesliga/startseite/wettbewerb/L1",
    'Serie A': "serie-a/startseite/wettbewerb/IT1",
    'Ligue 1': "ligue-1/startseite/wettbewerb/FR1",
    'PKO BP Ekstraklasa': "pko-bp-ekstraklasa/startseite/wettbewerb/PL1"
}
season_dict = {}
generate_season_entry = lambda year, offset: {
    f'{year-offset}/{(year-offset) % 100 + 1}': f"/saison_id/{year-offset}"
}
for i in range(deadline):
    season_dict.update(generate_season_entry(curr_year, i))

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}


all_clubs_data = {}

for league, path in leagues_dict.items():
    for season, spath in season_dict.items():
        url = site + path + spath
        print(f'Requesting URL for {league}: {url}')
        response = requests.get(url, headers=headers)

    # Sprawdzenie odpowiedzi serwera
        if response.status_code == 200:
            print(f"Success response for {league} {season}")
        else:
            raise Exception(f"Error response for {league} {season}: {response.status_code}")

    # Parsowanie treści strony
        soup = BeautifulSoup(response.text, 'html.parser')


        club_names = soup.find_all('td', class_='hauptlink no-border-links')


        club_values = soup.find_all('td', class_='rechts')

        print(f"Clubs in {league} {season}:")
        for i, name_td in enumerate(club_names):

            club_name = name_td.text.strip()
            club_value = club_values[((i + 1) * 2) + 1].text.strip()

            if club_name not in all_clubs_data:
                all_clubs_data[club_name] = {}

            all_clubs_data[club_name][season] = club_value

            print(f"- {club_name}: {club_value}")



save_to_csv = input("Czy chcesz stworzyć raport CSV z tych danych? (T/n): ")

if save_to_csv.upper() == 'T':
    filepath = '../Data/Club Info/'
    filename = 'clubs_report_from_transfermarkt.csv'


    headers = ['Club'] + list(season_dict.keys())

    with open(filepath + filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)


        writer.writerow(headers)


        for club_name, values in all_clubs_data.items():
            row = [club_name]
            for season in season_dict.keys():
                row.append(values.get(season, 'N/A'))
            writer.writerow(row)

    print(f"Raport został zapisany jako {filename}")
else:
    print("Raport CSV nie został zapisany.")