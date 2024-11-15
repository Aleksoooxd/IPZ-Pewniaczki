import requests
from bs4 import BeautifulSoup

#countries = ['england','spain','germany','xsds' ,'italy','france']
headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}

seasons = {
    '2024/2025':2425,
    '2023/2024':2324,
    '2022/2023':2223,
    '2021/2022':2122,
    '2020/2021':2021
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
    dowloand_link = all_a_tags.get('href').split('/')

    dowloand_link[1] = f'{seesonCode}'
    dowloand_link = '/'.join(dowloand_link)

    if dowloand_link != None:
     dowloand_url = f'https://www.football-data.co.uk/{dowloand_link}'
     dowloand_response = requests.get(dowloand_url,headers=headers)

     if dowloand_response.status_code != 200:
         print('Failed to load page {}'.format(dowloand_url))

     filepath = 'Data/Matches Results/'
     filename = f'{countryInfo[1].replace(" ","")}_{seesonCode}' + '.csv'
     with open((filepath + filename), 'wb') as file:
         file.write(dowloand_response.content)
     print(f"Plik został pobrany i zapisany! sciezka: {filepath + filename}")



def get_data_from_poland():
    url = 'https://www.football-data.co.uk/poland.php'

    response = requests.get(url,headers=headers)
    if response.status_code != 200:
        print('Failed to load page {}'.format(url))

    soup = BeautifulSoup(response.text, 'html.parser')

    dowloand_url = 'https://www.football-data.co.uk/new/POL.csv'
    dowloand_response = requests.get(dowloand_url,headers=headers)

    if dowloand_response.status_code != 200:
        print('Failed to load page {}'.format(dowloand_url))

    filepath = 'Data/Matches Results/'
    filename = 'Ekstraklasa_allSeasons' + '.csv'
    with open((filepath + filename), 'wb') as file:
        file.write(dowloand_response.content)
    print(f"Plik został pobrany i zapisany! sciezka: {filepath + filename}")



for key, countryValues in countries.items():
    for key, seasonsCode in seasons.items():
        get_data_from_top_5(countryValues, seasonsCode)

get_data_from_poland()