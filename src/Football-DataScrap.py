import os
import requests
from bs4 import BeautifulSoup
import datetime
#countries = ['england','spain','germany','xsds' ,'italy','france']
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}
curr_year = datetime.datetime.now().year
curr_year_2_digits = curr_year % 100
seasons = {
    f'{curr_year}/{curr_year+1}': f'{curr_year_2_digits}{curr_year_2_digits+1}',
    f'{curr_year-1}/{curr_year}': f'{curr_year_2_digits-1}{curr_year_2_digits}',
    f'{curr_year-2}/{curr_year-1}': f'{curr_year_2_digits-2}{curr_year_2_digits-1}',
    f'{curr_year-3}/{curr_year-2}': f'{curr_year_2_digits-3}{curr_year_2_digits-2}',
    f'{curr_year-4}/{curr_year-3}': f'{curr_year_2_digits-4}{curr_year_2_digits-3}'
}



countries = {
    'en': ['england', 'Premier League',],
    'sp': ['spain', 'La Liga Primera Division'],
    'de': ['germany', 'Bundesliga 1'],
    'it': ['italy', 'Serie A'],
    'fr': ['france', 'Le Championnat']
}



def get_data_from_top_5(countryInfo, seesonCode):
    url = f'https://www.football-data.co.uk/{countryInfo[0]}m.php'
    #print(url)
    response = requests.get(url,headers=headers)
    if response.status_code != 200:
        print('Failed to load page {}'.format(url))

    soup = BeautifulSoup(response.text, 'html.parser')


    all_a_tags = soup.find('a',string=f'{countryInfo[1]}')
    download_link = all_a_tags.get('href').split('/')

    download_link[1] = f'{seesonCode}'
    download_link = '/'.join(download_link)

    if download_link != None:
     download_url = f'https://www.football-data.co.uk/{download_link}'
     download_response = requests.get(download_url,headers=headers)

     if download_response.status_code != 200:
         print('Failed to load page {}'.format(download_url))
     filepath = '../Data/Matches Results/'
     filename = f'{countryInfo[1].replace(" ","")}_{seesonCode}' + '.csv'
     fullname = os.path.join(filepath, filename)
     with open(fullname, 'wb') as file:
         file.write(download_response.content)
     print(f"Plik został pobrany i zapisany! sciezka: {fullname}")



def get_data_from_poland():
    url = 'https://www.football-data.co.uk/poland.php'

    response = requests.get(url,headers=headers)
    if response.status_code != 200:
        print('Failed to load page {}'.format(url))

    soup = BeautifulSoup(response.text, 'html.parser')

    dowload_url = 'https://www.football-data.co.uk/new/POL.csv'
    dowload_response = requests.get(dowload_url,headers=headers)

    if dowload_response.status_code != 200:
        print('Failed to load page {}'.format(dowload_url))

    filepath = '../Data/Matches Results/'
    filename = 'Ekstraklasa_allSeasons' + '.csv'
    with open((filepath + filename), 'wb') as file:
        print(dowload_response.content)
        file.write(dowload_response.content)
    print(f"Plik został pobrany i zapisany! sciezka: {filepath + filename}")

for key, countryValues in countries.items():
    for key, seasonsCode in seasons.items():
        get_data_from_top_5(countryValues, seasonsCode)

get_data_from_poland()