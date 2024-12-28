import pandas as pd
import numpy as np
from scipy.stats import entropy, skew, kurtosis, pearsonr
import os


# Funkcja obliczająca indeks Shannona (entropię)
def shannon_index(values):
    probabilities = values / np.sum(values)
    return entropy(probabilities, base=2)


# Funkcja obliczająca współczynnik zmienności (CV)
def coefficient_of_variation(values):
    mean = np.mean(values)
    return np.std(values) / mean if mean != 0 else None


# Funkcja obliczająca indeks Gini'ego
def gini_index(values):
    sorted_values = np.sort(values)
    n = len(values)
    cumulative = np.cumsum(sorted_values)
    return (1 - (2 * np.sum(cumulative) / (n * cumulative[-1])) + (1 / n)) if n > 0 else None


# Funkcja obliczająca wskaźnik HHI (Herfindahl-Hirschman Index)
def hhi_index(values):
    probabilities = 1 / values  # Prawdopodobieństwa z kursów
    probabilities /= np.sum(probabilities)  # Normalizacja
    return np.sum(probabilities ** 2)


# Ścieżki katalogów
input_directory = "../Data/Matches Results/Merged Results/Top4Bookmakers"
output_directory = "../Data/BooksStatistic"

# Lista kolumn z kursami bukmacherów
bukmacher_cols = ["B365H", "BWH", "WHH", "IWH", "B365D", "BWD", "WHD", "IWD","B365A", "BWA", "WHA", "IWA"]

# Tworzenie katalogu wynikowego, jeśli nie istnieje
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Przetwarzanie plików CSV w katalogu wejściowym
for filename in os.listdir(input_directory):
    if filename.endswith("_Top4Bookmakers.csv"):
        input_file = os.path.join(input_directory, filename)
        output_file_indeksy = os.path.join(output_directory,
                                           filename.replace("_Top4Bookmakers.csv", "_Statistica_Indeksy.csv"))
        output_file_korelacje = os.path.join(output_directory,
                                             filename.replace("_Top4Bookmakers.csv", "_Statistica_Korelacje.csv"))

        try:
            # Wczytanie danych
            df = pd.read_csv(input_file)
            print(f"Przetwarzanie pliku: {filename}")

            # Sprawdzenie dostępnych kolumn
            kursy_cols = [col for col in bukmacher_cols if col in df.columns]
            if not kursy_cols:
                raise ValueError(f"Brak wymaganych kolumn z kursami w pliku {filename}!")

            # Statystyki ogólne
            stats = {
                "Średnia kursów": [],
                "Odchylenie standardowe": [],
                "Skośność": [],
                "Kurtoza": [],
                "Indeks Shannona": [],
                "Współczynnik Zmienności (CV)": [],
                "Indeks Gini'ego": [],
                "Wskaźnik HHI": []
            }

            for col in kursy_cols:
                values = df[col].dropna().values
                if len(values) > 0:
                    stats["Średnia kursów"].append(np.mean(values))
                    stats["Odchylenie standardowe"].append(np.std(values))
                    stats["Skośność"].append(skew(values))
                    stats["Kurtoza"].append(kurtosis(values))
                    stats["Indeks Shannona"].append(shannon_index(values))
                    stats["Współczynnik Zmienności (CV)"].append(coefficient_of_variation(values))
                    stats["Indeks Gini'ego"].append(gini_index(values))
                    stats["Wskaźnik HHI"].append(hhi_index(values))
                else:
                    # Dodaj NaN dla pustych kolumn
                    for key in stats.keys():
                        stats[key].append(None)

            # Korelacje pomiędzy kursami
            korelacje = {}
            for i, col1 in enumerate(kursy_cols):
                for j, col2 in enumerate(kursy_cols):
                    if i < j:  # Unikamy duplikatów
                        col1_values = df[col1].dropna()
                        col2_values = df[col2].dropna()
                        common_values = pd.concat([col1_values, col2_values], axis=1).dropna()
                        if len(common_values) > 1:
                            korelacja, _ = pearsonr(common_values.iloc[:, 0], common_values.iloc[:, 1])
                            korelacje[f"{col1} vs {col2}"] = korelacja
                        else:
                            korelacje[f"{col1} vs {col2}"] = None

            # Tworzenie DataFrame z wynikami
            stats_df = pd.DataFrame(stats, index=kursy_cols)
            korelacje_df = pd.DataFrame(list(korelacje.items()), columns=["Pary Bukmacherów", "Korelacja"])

            # Zapis indeksów do osobnego pliku CSV
            stats_df.to_csv(output_file_indeksy, encoding='utf-8')
            print(f"Indeksy zapisane do pliku: {output_file_indeksy}")

            # Zapis korelacji do osobnego pliku CSV
            korelacje_df.to_csv(output_file_korelacje, index=False, encoding='utf-8')
            print(f"Korelacje zapisane do pliku: {output_file_korelacje}")

        except Exception as e:
            print(f"Błąd podczas przetwarzania pliku {filename}: {e}")
