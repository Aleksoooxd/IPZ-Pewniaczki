import requests
from bs4 import BeautifulSoup
import csv
import os


site = "https://www.transfermarkt.com/"

next_leagues_dict = {
    'Championship': "Championship/startseite/wettbewerb/GB2",
    'La Liga 2': "laliga2/startseite/wettbewerb/ES2",
    'Bundesliga 2': "2-bundesliga/startseite/wettbewerb/L2",
    'Serie B': "serie-b/startseite/wettbewerb/IT2",
    'Ligue 2': "ligue-2/startseite/wettbewerb/FR2",
    'PKO BP Ekstraklasa': "betclic-1-liga/startseite/wettbewerb/PL2"
}

season_dict = {
    '2023/24': "/plus/?saison_id=2023",
    '2022/23': "/plus/?saison_id=2022",
    '2021/22': "/plus/?saison_id=2021",
    '2020/21': "/plus/?saison_id=2020"
}
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}

all_clubs_data = {}

for league, path in next_leagues_dict.items():
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
    filename = 'filtred_clubs_report_from_transfermarkt.csv'
    full_path = os.path.join(filepath, filename)

    # Create the directory if it doesn't exist
    os.makedirs(filepath, exist_ok=True)

    # Write the CSV
    headers = ['Club'] + list(season_dict.keys())

    with open(full_path, mode='w', newline='', encoding='utf-8') as file:
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
