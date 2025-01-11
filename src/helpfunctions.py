import os
import pandas as pd
import copy
from fuzzywuzzy import process
from unidecode import unidecode
import numpy as np
from scipy.stats import entropy
def normalize():
    teams_football_data = set()
    teams_transfermarkt = set()
    for file in os.listdir('../Data/Matches Results/Merged Results/allSeasons'):
        file_path = os.path.join('../Data/Matches Results/Merged Results/allSeasons', file)
        data = pd.read_csv(file_path, index_col=0, low_memory=False)
        for index, row in data.iterrows():
            teams_football_data.add(unidecode(str(row['HomeTeam'])))
    file_path_transfer = '../Data/Club Info/clubs_report_from_transfermarkt.csv'
    data_transfer = pd.read_csv(file_path_transfer, low_memory=False)
    for index, row in data_transfer.iterrows():
        teams_transfermarkt.add(unidecode(str(row['Club'])))
    list_1 = sorted(list(teams_football_data))
    list_2 = sorted(list(teams_transfermarkt))
    temp_list_1 = copy.deepcopy(list_1)
    temp_list_2 = copy.deepcopy(list_2)
    THRESHOLD = 95
    correct = {}
    while temp_list_1 and temp_list_2:
        mapping = {}
        for club in temp_list_1:
            match, score = process.extractOne(club, temp_list_2)
            if score >= THRESHOLD:
                mapping[club] = match
            else:
                mapping[club] = None
        matched = {k: v for k, v in mapping.items() if v is not None}
        unmatched = {k: v for k, v in mapping.items() if v is None}
        correct.update(matched)
        for key, value in matched.items():
            if key in temp_list_1:
                temp_list_1.remove(key)
            if value in temp_list_2:
                temp_list_2.remove(value)
            else:
                pass
                print(f"Warning: {value} not found in temp_list_2")
        if unmatched:
            THRESHOLD -= 1
            if THRESHOLD < 0:
                break
        else:
            break
    print("Final Matched Clubs:", correct)
    print("Remaining Unmatched Clubs:", temp_list_1)
    return data_transfer, correct
def update_club_name(row, mapping):
    club_name = unidecode(str(row['Club']))
    for key, value in mapping.items():
        if value == club_name:
            return unidecode(key.strip())
    return club_name
def normalize_names():
    data_transfer, correct = normalize()
    data_transfer['Club'] = data_transfer.apply(update_club_name, axis=1, mapping=correct)
    output_file_path = '../Data/Club Info/clubs_report_from_transfermarkt.csv'
    data_transfer.to_csv(output_file_path, index=False)
    normalize_values(output_file_path)
    print(f"Zaktualizowany plik zapisany jako: {output_file_path}")
def shannon_index(values):
    probabilities = values / np.sum(values)
    return np.round(entropy(probabilities, base=2),4)
def coefficient_of_variation(values):
    mean = np.mean(values)
    return np.round((np.std(values) / mean),4) if mean != 0 else None
def gini_index(values):
    sorted_values = np.sort(values)
    n = len(values)
    cumulative = np.cumsum(sorted_values)
    return np.round((1 - (2 * np.sum(cumulative) / (n * cumulative[-1])) + (1 / n)),4) if n > 0 else None
def hhi_index(values):
    probabilities = 1 / values
    probabilities /= np.sum(probabilities)
    return np.round(np.sum(probabilities ** 2),4)
def calculate_consensus(row, columns):
    votes_H = sum([1 for col in columns["H"] if row[col] < row[columns["D"][0]] and row[col] < row[columns["A"][0]]])
    votes_D = sum([1 for col in columns["D"] if row[col] < row[columns["H"][0]] and row[col] < row[columns["A"][0]]])
    votes_A = sum([1 for col in columns["A"] if row[col] < row[columns["H"][0]] and row[col] < row[columns["D"][0]]])
    if votes_H > max(votes_D, votes_A):
        return 'H'
    elif votes_D > max(votes_H, votes_A):
        return 'D'
    elif votes_A > max(votes_H, votes_D):
        return 'A'
    else:
        return 'No Consensus'
def normalize_values(file_path):
    data = pd.read_csv(file_path, low_memory=False)
    def convert_value(value):
        if isinstance(value, str):
            value = value.strip()
            if value.endswith('bn'):
                return float(value[1:-2]) * 1000
            elif value.endswith('m'):
                return float(value[1:-1])
        return value
    for column in data.columns[1:]:
        data[column] = data[column].apply(convert_value)
    data.to_csv(file_path, index=False)
    print(f"Updated file saved as: {file_path}")
def get_club_matches_in_season(club_name= 'Stuttgart', season= '2004/5'):
    df = merge_all_seasons()
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    home_matches = df[(df['HomeTeam'] == club_name) & (df['Season'] == season)]
    away_matches = df[(df['AwayTeam'] == club_name) & (df['Season'] == season)]
    all_matches = pd.concat([home_matches, away_matches])
    all_matches_sorted = all_matches.sort_values(by='Date').reset_index(drop=True)
    all_matches_sorted['Matchday'] = all_matches_sorted.index + 1
    return all_matches_sorted
def merge_all_seasons():
    all_seasons = pd.DataFrame()
    path = '../Data/Matches Results/Merged Results/allSeasons'
    for file in os.listdir(path):
        file_path = os.path.join(path, file)
        data = pd.read_csv(file_path, low_memory=False)
        all_seasons = pd.concat([all_seasons, data])
    return all_seasons
def get_matchdays_in_season(club, season):
    matches = get_club_matches_in_season(club, season)
    return matches['Matchday'].max()
def calculate_form_and_goals(club,matches, matchday, i):
    filtered_matches = matches[matches['Matchday'] <= matchday]
    last_i_matches = filtered_matches.tail(i)
    home_goals = last_i_matches[last_i_matches['HomeTeam'] == club]['FTHG'].sum()
    away_goals = last_i_matches[last_i_matches['AwayTeam'] == club]['FTAG'].sum()
    total_goals = home_goals + away_goals
    form_points = 0
    for _, match in last_i_matches.iterrows():
        if match['HomeTeam'] == club:
            if match['FTR'] == 'H':
                form_points += 3
            elif match['FTR'] == 'D':
                form_points += 1
        elif match['AwayTeam'] == club:
            if match['FTR'] == 'A':
                form_points += 3
            elif match['FTR'] == 'D':
                form_points += 1
    return int(total_goals), int(form_points)
def get_info():
    club = 'Stuttgart'
    season = '2004/5'
    matchday = get_matchdays_in_season(club,season)
    matches = get_club_matches_in_season(club,season)
    goals3,form3 = calculate_form_and_goals(club,matches,matchday,3)
    goals5, form5 = calculate_form_and_goals(club, matches, matchday, 5)
    goalss, forms = calculate_form_and_goals(club, matches, matchday, matchday)
    print(f"Goals in last 3 matches: {goals3}")
    print(f"Form in last 3 matches: {form3}")
    print(f"Goals in last 5 matches: {goals5}")
    print(f"Form in last 5 matches: {form5}")
    print(f"Goals in all matches: {goalss}")
    print(f"Form in all matches: {forms}")
get_info()