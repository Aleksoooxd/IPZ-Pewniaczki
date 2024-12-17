import pandas as pd
import os

# Ścieżki do katalogów
input_directory = "../Data/Matches Results/Merged Results/Top4Bookmakers"
output_directory = "../Data/"

# Funkcja obliczająca niespodzianki na podstawie średnich kursów
def analyze_average_odds_Surprise(df, file_name):
    # Sprawdzamy, czy potrzebne kolumny istnieją
    required_cols = ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA',
                     'LBH', 'LBD', 'LBA', 'VCH', 'VCD', 'VCA', 'FTR']
    if not all(col in df.columns for col in required_cols):
        print(f"Brak wymaganych kolumn w pliku {file_name}")
        return None

    # Obliczamy średnie kursy dla każdego wyniku
    df['Avg_H'] = df[['B365H', 'BWH', 'LBH', 'VCH']].mean(axis=1)
    df['Avg_D'] = df[['B365D', 'BWD', 'LBD', 'VCD']].mean(axis=1)
    df['Avg_A'] = df[['B365A', 'BWA', 'LBA', 'VCA']].mean(axis=1)

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
    percent_upsets = (num_upsets / total_matches) * 100
    avg_upset_odds = sum(upsets) / num_upsets if upsets else 0

    return {
        "Total Matches": total_matches,
        "Number of Upsets": num_upsets,
        "Percentage of Upsets": percent_upsets,
        "Average Upset Odds": avg_upset_odds
    }

# Tworzenie katalogu wynikowego, jeśli nie istnieje
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Przetwarzanie plików CSV
results = []
for filename in os.listdir(input_directory):
    if filename.endswith("_Top4Bookmakers.csv"):
        input_file = os.path.join(input_directory, filename)
        df = pd.read_csv(input_file)
        print(f"Przetwarzanie pliku: {filename}")

        stats = analyze_average_odds_Surprise(df, filename)
        if stats:
            stats["File"] = filename
            results.append(stats)

# Tworzenie podsumowania wyników
results_df = pd.DataFrame(results)
output_file = os.path.join(output_directory, "Surprise_AverageOdds_Statistics.csv")
results_df.to_csv(output_file, index=False)
print(f"Wyniki niespodzianek na podstawie średnich kursów zapisano do pliku: {output_file}")
