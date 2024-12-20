import os
import pandas as pd
import copy
from fuzzywuzzy import process
from unidecode import unidecode
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
    print(f'threshhold: {THRESHOLD}')
    print(f'matched len: {len(matched)}')
    print(f"matched: {matched}")
    print(f'unmatched len: {len(unmatched)}')
    print(f"unmatched: {unmatched}")
    print("")
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

def update_club_name(row, mapping):
    club_name = unidecode(str(row['Club']))
    for key, value in mapping.items():
        if value == club_name:
            return unidecode(key.strip())
    return club_name
data_transfer['Club'] = data_transfer.apply(update_club_name, axis=1, mapping=correct)
output_file_path = '../Data/Club Info/clubs_report_from_transfermarkt_updated.csv'
data_transfer.to_csv(output_file_path, index=False)

print(f"Zaktualizowany plik zapisany jako: {output_file_path}")
