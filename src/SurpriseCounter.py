import pandas as pd
import os

# Ścieżki do katalogów
input_base_directory = "../Data/Matches Results/Merged Results"
output_directory = "../Data/Suprise"

# Konfiguracja dla różnych grup bukmacherów
bookmakers_columns = {
    "Top2Bookmakers": ["B365H", "BWH", "B365D", "BWD", "B365A", "BWA"],
    "Top4Bookmakers": ["B365H", "BWH", "WHH", "IWH", "B365D", "BWD", "WHD", "IWD", "B365A", "BWA", "WHA", "IWA"],
    "Top6Bookmakers": ["B365H", "BWH", "WHH", "IWH", "VCH", "LBH", "B365D", "BWD", "WHD", "IWD", "VCD", "LBD", "B365A",
                       "BWA", "WHA", "IWA", "VCA", "LBA"]
}


# Funkcja obliczająca niespodzianki na podstawie średnich kursów
def analyze_average_odds_Surprise(df, file_name, columns):
    # Sprawdzamy, czy wymagane kolumny istnieją
    required_cols = columns + ['FTR']
    if not all(col in df.columns for col in required_cols):
        print(f"Brak wymaganych kolumn w pliku {file_name}")
        return None

    # Obliczamy średnie kursy dla każdego wyniku
    num_h_cols = len([col for col in columns if "H" in col])
    num_d_cols = len([col for col in columns if "D" in col])
    num_a_cols = len([col for col in columns if "A" in col])

    df['Avg_H'] = df[[col for col in columns if "H" in col]].mean(axis=1)
    df['Avg_D'] = df[[col for col in columns if "D" in col]].mean(axis=1)
    df['Avg_A'] = df[[col for col in columns if "A" in col]].mean(axis=1)

    total_matches = len(df)
    upsets = []

    # Iteracja przez każdy mecz
    for _, row in df.iterrows():
        avg_h = row['Avg_H']
        avg_d = row['Avg_D']
        avg_a = row['Avg_A']
        result = row['FTR']  # Wynik meczu: H, D, A

        # Znalezienie największego średniego kursu
        max_avg_odds = max(avg_h, avg_d, avg_a)

        # Sprawdzenie, czy wynik odpowiada najwyższemu kursowi
        if result == 'H' and avg_h == max_avg_odds:
            upsets.append(avg_h)
        elif result == 'D' and avg_d == max_avg_odds:
            upsets.append(avg_d)
        elif result == 'A' and avg_a == max_avg_odds:
            upsets.append(avg_a)

    # Obliczenie statystyk
    num_upsets = len(upsets)
    percent_upsets = round(((num_upsets / total_matches) * 100), 2)
    avg_upset_odds = round((sum(upsets) / num_upsets), 2) if upsets else 0

    return {
        "Total Matches": total_matches,
        "Number of Upsets": num_upsets,
        "Percentage of Upsets": percent_upsets,
        "Average Upset Odds": avg_upset_odds
    }

def surprise_counter():
    # Tworzenie katalogu wynikowego, jeśli nie istnieje
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Przetwarzanie plików dla każdej grupy bukmacherów
    all_results = []

    for group, columns in bookmakers_columns.items():
        group_results = []
        input_directory = os.path.join(input_base_directory, group)
        print(f"Przetwarzanie plików dla grupy: {group}")

        for filename in os.listdir(input_directory):
            if filename.endswith(f"_{group}.csv"):
                input_file = os.path.join(input_directory, filename)
                df = pd.read_csv(input_file)
                print(f"Przetwarzanie pliku: {filename}")

                stats = analyze_average_odds_Surprise(df, filename, columns)
                if stats:
                    stats["File"] = filename.split('_')[0]  # Dodajemy nazwę ligi
                    group_results.append(stats)

        # Dodanie wyników grupy do zbiorczego wyniku
        all_results.extend(group_results)

        # Tworzenie podsumowania wyników dla konkretnej grupy
        group_results_df = pd.DataFrame(group_results)
        group_output_file = os.path.join(output_directory, f"Surprise_AverageOdds_Statistics_{group}.csv")
        group_results_df.to_csv(group_output_file, index=False)
        print(f"Wyniki dla grupy {group} zapisano do pliku: {group_output_file}")


