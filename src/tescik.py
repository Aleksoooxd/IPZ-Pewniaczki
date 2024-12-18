import os
import pandas as pd
import copy
from fuzzywuzzy import process

# Initialize sets
teams_football_data = set()
teams_transfermarkt = set()
for file in os.listdir('../Data/Matches Results/Merged Results/allSeasons'):
    file_path = os.path.join('../Data/Matches Results/Merged Results/allSeasons', file)
    data = pd.read_csv(file_path, index_col=0, low_memory=False)
    for index, row in data.iterrows():
        if 'HomeTeam' in data.columns:
            teams_football_data.add(str(row['HomeTeam']))
        else:
            teams_football_data.add(str(row['Home']))

# Read data from Transfermarkt
file_path_transfer = '../Data/Club Info/clubs_report_from_transfermarkt.csv'
data_transfer = pd.read_csv(file_path_transfer, low_memory=False)
for index, row in data_transfer.iterrows():
    teams_transfermarkt.add(str(row['Club']))

# Find symmetric difference and sort lists
z = teams_football_data.symmetric_difference(teams_transfermarkt)
list_1 = sorted(list(teams_football_data))
list_2 = sorted(list(teams_transfermarkt))

# Copy lists for processing
temp_list_1 = copy.deepcopy(list_1)
temp_list_2 = copy.deepcopy(list_2)

# Define threshold and initialize variables
THRESHOLD = 95
correct = {}

while temp_list_1 and temp_list_2:
    mapping = {}

    # Match clubs from temp_list_1 to temp_list_2
    for club in temp_list_1:
        match, score = process.extractOne(club, temp_list_2)
        if score >= THRESHOLD:
            mapping[club] = match
        else:
            mapping[club] = None

    # Filter matched and unmatched items
    matched = {k: v for k, v in mapping.items() if v is not None}
    unmatched = {k: v for k, v in mapping.items() if v is None}
    print(THRESHOLD)
    print(len(matched))
    print(matched)
    print(temp_list_1)
    print(len(unmatched))
    print(unmatched)
    print(temp_list_2)
    print("\n")
    # Update the correct mapping
    correct.update(matched)

    # Remove matched items from lists
    for key, value in matched.items():
        if key in temp_list_1:
            temp_list_1.remove(key)
        if value in temp_list_2:  # Ensure value exists in temp_list_2 before removing
            temp_list_2.remove(value)
        else:
            print(f"Warning: {value} not found in temp_list_2")

    # If unmatched items exist, lower the threshold
    if unmatched:
        THRESHOLD -= 1
        if THRESHOLD < 0:  # Stop if the threshold becomes too low
            break
    else:
        break

# Print results
print("Final Matched Clubs:", correct)
print("Remaining Unmatched Clubs:", temp_list_1)

def update_club_name(row, mapping):
    club_name = str(row['Club'])
    return mapping.get(club_name, club_name)  # Zwróć wartość z mapping, jeśli istnieje, inaczej oryginalna nazwa

# Aktualizacja danych
data_transfer['Club'] = data_transfer.apply(update_club_name, axis=1, mapping=mapping)

# Zapis zaktualizowanego pliku CSV
output_file_path = '../Data/Club Info/clubs_report_from_transfermarkt_updated.csv'
data_transfer.to_csv(output_file_path, index=False)

print(f"Zaktualizowany plik zapisany jako: {output_file_path}")
