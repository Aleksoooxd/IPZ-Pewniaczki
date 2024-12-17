import os
import pandas as pd
from fuzzywuzzy import process
teams_football_data = set()
teams_transfermarkt = set()
for file in os.listdir('../Data/Matches Results/Merged Results/allSeasons'):
    file_path = os.path.join('../Data/Matches Results/Merged Results/allSeasons',file)
    data = pd.read_csv(file_path,index_col=0,low_memory=False)
    for index,row in data.iterrows():
        if 'HomeTeam' in data:
            teams_football_data.add(str(row['HomeTeam']))
        else:
            teams_football_data.add(str(row['Home']))
file_path_transfer = '../Data/Club Info/clubs_report_from_transfermarkt.csv'
data_transfer = pd.read_csv(file_path_transfer,low_memory=False)
for index,row in data_transfer.iterrows():
    teams_transfermarkt.add(str(row['Club']))
z = teams_football_data.symmetric_difference(teams_transfermarkt)
list_1 = list(sorted(list(teams_football_data)))
list_2 = list(sorted(list(teams_transfermarkt)))
THRESHOLD = 95

mapping = {}
for club in list_1:
    match, score = process.extractOne(club, list_2)
    if score >= THRESHOLD:
        mapping[club] = match
    else:
        mapping[club] = None

# Wyświetl wyniki
matched = {k: v for k, v in mapping.items() if v is not None}
print("Len Matched:", len(matched))
print("Matched:", matched)

# Wyświetl kluby bez przypisania
unmatched = {k: v for k, v in mapping.items() if v is None}
print("Len Unmatched:", len(unmatched))
print("Unmatched:", unmatched)

def update_club_name(row, mapping):
    club_name = str(row['Club'])
    return mapping.get(club_name, club_name)  # Zwróć wartość z mapping, jeśli istnieje, inaczej oryginalna nazwa

# Aktualizacja danych
data_transfer['Club'] = data_transfer.apply(update_club_name, axis=1, mapping=mapping)

# Zapis zaktualizowanego pliku CSV
output_file_path = '../Data/Club Info/clubs_report_from_transfermarkt_updated.csv'
data_transfer.to_csv(output_file_path, index=False)

print(f"Zaktualizowany plik zapisany jako: {output_file_path}")
