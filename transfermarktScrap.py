import requests
from bs4 import BeautifulSoup
import csv

# Adres strony głównej
site = "https://www.transfermarkt.com/"

# Ścieżki do poszczególnych lig
leagues_dict = {
    'Premier League': "premier-league/startseite/wettbewerb/GB1",
    'La Liga': "laliga/startseite/wettbewerb/ES1",
    'Bundesliga': "bundesliga/startseite/wettbewerb/L1",
    'Serie A': "serie-a/startseite/wettbewerb/IT1",
    'Ligue 1': "ligue-1/startseite/wettbewerb/FR1",
    'PKO BP Ekstraklasa': "pko-bp-ekstraklasa/startseite/wettbewerb/PL1"
}
season_dict = {
    '2024/25': "/saison_id/2024",
    '2023/24': "/saison_id/2023"
    #'2022/23': "/saison_id/2022",
    #'2021/22': "/saison_id/2021",
    #'2020/21': "/saison_id/2020"
}

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
            print(f"Success for {league}")
        else:
            raise Exception(f"Error response for {league}: {response.status_code}")

    # Parsowanie treści strony
        soup = BeautifulSoup(response.text, 'html.parser')


        club_names = soup.find_all('td', class_='hauptlink no-border-links')


        club_values = soup.find_all('td', class_='rechts')

        print(f"Clubs in {league}:")
        for i, name_td in enumerate(club_names):

            club_name = name_td.text.strip()
            club_value = club_values[((i + 1) * 2) + 1].text.strip()
            if club_name in all_clubs_data:
                all_clubs_data.update({club_name: club_value})
            else:
                all_clubs_data[club_name] = club_value

            print(f"- {club_name}: {club_value}")



save_to_csv = input("Czy chcesz stworzyć raport CSV z tych danych? (T/n): ")

if save_to_csv.upper() == 'T':
    filename = 'clubs_report_from_transfermarkt.csv'
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Club', 'Value of Club'])
        writer.writerows(all_clubs_data)
    print(f"Raport został zapisany jako {filename}")
else:
    print("Raport CSV nie został zapisany.")