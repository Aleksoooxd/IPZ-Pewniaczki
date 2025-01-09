import pandas as pd
import os

# Kolumny główne + wszystkie bukmacherów
selected_columns = [
    'Div', 'Season', 'Date', 'HomeTeam', 'AwayTeam', 'FTR',
    'HomeValue', 'AwayValue'
]

all_bookmaker_columns = [
    'B365H', 'B365D', 'B365A', 'BFH', 'BFD', 'BFA', 'BSH', 'BSD', 'BSA', 'BWH', 'BWD', 'BWA',
    'GBH', 'GBD', 'GBA', 'IWH', 'IWD', 'IWA', 'LBH', 'LBD', 'LBA', 'PSH', 'PSD', 'PSA',
    'SOH', 'SOD', 'SOA', 'SBH', 'SBD', 'SBA', 'SJH', 'SJD', 'SJA', 'SYH', 'SYD', 'SYA',
    'VCH', 'VCD', 'VCA', 'WHH', 'WHD', 'WHA'
]

# Wszystkie wymagane kolumny
required_columns = selected_columns + all_bookmaker_columns

# Słownik z nazwami lig i odpowiadającymi im ścieżkami plików
leagues = {
    'PremierLeague': '../Data/Matches Results/Merged Results/allSeasons/PremierLeague_allSeasons.csv',
    'LaLigaPrimeraDivision': '../Data/Matches Results/Merged Results/allSeasons/LaLigaPrimeraDivision_allSeasons.csv',
    'Bundesliga1': '../Data/Matches Results/Merged Results/allSeasons/Bundesliga1_allSeasons.csv',
    'SerieA': '../Data/Matches Results/Merged Results/allSeasons/SerieA_allSeasons.csv',
    'LeChampionnat': '../Data/Matches Results/Merged Results/allSeasons/LeChampionnat_allSeasons.csv',
    'Eredivisie': '../Data/Matches Results/Merged Results/allSeasons/Eredivisie_allSeasons.csv',
    'JupilerLeague': '../Data/Matches Results/Merged Results/allSeasons/JupilerLeague_allSeasons.csv',
    'LigaI': '../Data/Matches Results/Merged Results/allSeasons/LigaI_allSeasons.csv',
    'FutbolLigi1': '../Data/Matches Results/Merged Results/allSeasons/FutbolLigi1_allSeasons.csv',
    'EthnikiKatigoria': '../Data/Matches Results/Merged Results/allSeasons/EthnikiKatigoria_allSeasons.csv'
}

def generate_all_bookmakers():
    """Generates a table containing all bookmakers for each league."""
    for league, path in leagues.items():
        # Wczytaj dane z pliku CSV
        try:
            merged_data = pd.read_csv(path)
        except Exception as e:
            print(f"Nie udało się wczytać pliku dla ligi {league}: {e}")
            continue

        # Dodaj brakujące kolumny
        for col in required_columns:
            if col not in merged_data.columns:
                merged_data[col] = pd.NA  # Wypełnij brakujące kolumny wartościami NaN

        # Filtruj wymagane kolumny (upewniamy się, że kolumny są w odpowiedniej kolejności)
        merged_data = merged_data[required_columns]

        # Zamiana NaN na 1.0 w razie potrzeby (opcjonalne)
        merged_data = merged_data.fillna(1.0)

        # Zapisanie pliku CSV
        output_dir = f"../Data/FinalData/AllBookmakers"
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"{league}_AllBookmakers.csv")
        try:
            merged_data.to_csv(output_file, index=False)
            print(f"Zapisano plik dla ligi {league}: {output_file}")
        except Exception as e:
            print(f"Nie udało się zapisać pliku dla ligi {league}: {e}")

if __name__ == "__main__":
    generate_all_bookmakers()
