import os
import pandas as pd

def merge_files():
    path = '../Data/Matches Results/'
    leagues = ['PremierLeague','LaLigaPrimeraDivision','Bundesliga1','SerieA','LeChampionnat']
    files = os.listdir(path)
    for league in leagues:
        league_files = [file for file in files if file.endswith('.csv') and file.startswith(league)]
        df = pd.DataFrame()
        for file in league_files:
            df = pd.concat([df, pd.read_csv(path + file)], ignore_index=True)
        df.to_csv(f'../Data/Matches Results/{league}_allSeasons.csv', index=False)
merge_files()