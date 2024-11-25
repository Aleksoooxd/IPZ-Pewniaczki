import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
}


curr_year = datetime.datetime.now().year
curr_year_2_digits = curr_year % 100

seasons = {
    f'{curr_year}/{curr_year+1}': f'{curr_year_2_digits}{curr_year_2_digits+1}', #24/25 (current season)
    f'{curr_year-1}/{curr_year}': f'{curr_year_2_digits-1}{curr_year_2_digits}', #23/24
    f'{curr_year-2}/{curr_year-1}': f'{curr_year_2_digits-2}{curr_year_2_digits-1}', #22/23
    f'{curr_year-3}/{curr_year-2}': f'{curr_year_2_digits-3}{curr_year_2_digits-2}', #21/22
    f'{curr_year-4}/{curr_year-3}': f'{curr_year_2_digits-4}{curr_year_2_digits-3}', #20/21
    f'{curr_year-5}/{curr_year-4}': f'{curr_year_2_digits-5}{curr_year_2_digits-4}', #19/20
    f'{curr_year-6}/{curr_year-5}': f'{curr_year_2_digits-6}{curr_year_2_digits-5}', #18/19
    f'{curr_year-7}/{curr_year-6}': f'{curr_year_2_digits-7}{curr_year_2_digits-6}', #17/18
    f'{curr_year-8}/{curr_year-7}': f'{curr_year_2_digits-8}{curr_year_2_digits-7}', #16/17
    f'{curr_year-9}/{curr_year-8}': f'{curr_year_2_digits-9}{curr_year_2_digits-8}', #15/16
    f'{curr_year-10}/{curr_year-9}': f'{curr_year_2_digits-10}{curr_year_2_digits-9}', #14/15
    f'{curr_year-11}/{curr_year-10}': f'{curr_year_2_digits-11}{curr_year_2_digits-10}', #13/14
    f'{curr_year-12}/{curr_year-11}': f'{curr_year_2_digits-12}{curr_year_2_digits-11}', #12/13
    f'{curr_year-13}/{curr_year-12}': f'{curr_year_2_digits-13}{curr_year_2_digits-12}', #11/12
    f'{curr_year-14}/{curr_year-13}': f'{curr_year_2_digits-14}{curr_year_2_digits-13}', #10/11
    f'{curr_year-15}/{curr_year-14}': f'0{curr_year_2_digits-15}{curr_year_2_digits-14}', #9/10
    f'{curr_year-16}/{curr_year-15}': f'0{curr_year_2_digits-16}0{curr_year_2_digits-15}', #8/9
    f'{curr_year-17}/{curr_year-16}': f'0{curr_year_2_digits-17}0{curr_year_2_digits-16}', #7/8
    f'{curr_year-18}/{curr_year-17}': f'0{curr_year_2_digits-18}0{curr_year_2_digits-17}', #6/7
    f'{curr_year-19}/{curr_year-18}': f'0{curr_year_2_digits-19}0{curr_year_2_digits-18}', #5/6
    f'{curr_year-20}/{curr_year-19}': f'0{curr_year_2_digits-20}0{curr_year_2_digits-19}', #4/5
    f'{curr_year-21}/{curr_year-20}': f'0{curr_year_2_digits-21}0{curr_year_2_digits-20}', #3/4
    f'{curr_year-22}/{curr_year-21}': f'0{curr_year_2_digits-22}0{curr_year_2_digits-21}', #2/3
    f'{curr_year-23}/{curr_year-22}': f'0{curr_year_2_digits-23}0{curr_year_2_digits-22}', #1/2
    f'{curr_year-24}/{curr_year-23}': f'0{curr_year_2_digits-24}0{curr_year_2_digits-23}', #0/1
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
     filepath = f'../Data/Matches Results/{countryInfo[0]}/'
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

    filepath = '../Data/Matches Results/poland/'
    filename = 'Ekstraklasa_allSeasons' + '.csv'
    with open((filepath + filename), 'wb') as file:
        file.write(dowload_response.content)
    df = pd.read_csv(filepath + filename)
    df['Year']=df['Season'].str[0:4]
    df = df.drop(df[df.Year<=f'{curr_year-5}'].index)
    df.to_csv(filepath + filename, index=False)
    print(f"Plik został pobrany i zapisany! sciezka: {filepath + filename}")

for key, countryValues in countries.items():
    for key, seasonsCode in seasons.items():
        get_data_from_top_5(countryValues, seasonsCode)

get_data_from_poland()