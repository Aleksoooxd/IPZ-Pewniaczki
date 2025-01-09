from file_operator import FileOperator
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

additional_columns = ['HT','AT','PSH','PSD','PSA','PSCH', 'PSCD', 'PSCA','B365CH','B365CD','B365CA']

def generate_all_bookmakers(file_operator):
    """Generates a table containing all bookmakers."""
    selected_columns_dynamic = selected_columns+ additional_columns + all_bookmaker_columns

    for league, country in zip(file_operator.leagues, file_operator.countries):
        # Wczytaj dane z plików i przetwórz je
        merged_data = file_operator.merge_files(
            league_name=league,
            country_name=country,
            selected_columns=selected_columns_dynamic,
            output_suffix="AllBookmakers",
            use_book=True
        )

        # Sprawdź, czy dane zostały wczytane poprawnie
        if merged_data is None or merged_data.empty:
            print(f"Brak danych dla ligi {league} w kraju {country}")
            continue

        # Zamiana NaN na 1.0 we wszystkich kolumnach z kursami
        for column in all_bookmaker_columns:
            if column in merged_data.columns:
                merged_data[column] = merged_data[column].fillna(1.0)

        # Zapisanie pliku CSV
        output_dir = f"../Data/FinalData/AllBookmakers"
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"{league}_{country}_AllBookmakers.csv")
        try:
            merged_data.to_csv(output_file, index=False)
            print(f"Zapisano plik: {output_file}")
        except Exception as e:
            print(f"Nie udało się zapisać pliku {output_file}: {e}")

if __name__ == "__main__":
    file_op = FileOperator()
    generate_all_bookmakers(file_op)
