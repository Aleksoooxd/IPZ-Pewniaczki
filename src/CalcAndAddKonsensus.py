import pandas as pd
import numpy as np
from scipy.stats import entropy
import os

# Funkcje statystyczne
def shannon_index(values):
    probabilities = values / np.sum(values)
    return entropy(probabilities, base=2)

def coefficient_of_variation(values):
    mean = np.mean(values)
    return np.std(values) / mean if mean != 0 else None

def gini_index(values):
    sorted_values = np.sort(values)
    n = len(values)
    cumulative = np.cumsum(sorted_values)
    return (1 - (2 * np.sum(cumulative) / (n * cumulative[-1])) + (1 / n)) if n > 0 else None

def hhi_index(values):
    probabilities = 1 / values
    probabilities /= np.sum(probabilities)
    return np.sum(probabilities ** 2)

# Funkcja do obliczania konsensusu metodą majority voting
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

# Funkcja przetwarzająca dane
def calculate_cons():
    bookmakers_columns = {
        "AllBookmakers": {
            "H": ["B365H", "BFH", "BSH", "BWH", "GBH", "IWH", "LBH", "PSH", "SOH", "SBH", "SJH", "SYH", "VCH", "WHH"],
            "D": ["B365D", "BFD", "BSD", "BWD", "GBD", "IWD", "LBD", "PSD", "SOD", "SBD", "SJD", "SYD", "VCD", "WHD"],
            "A": ["B365A", "BFA", "BSA", "BWA", "GBA", "IWA", "LBA", "PSA", "SOA", "SBA", "SJA", "SYA", "VCA", "WHA"]
        }
    }

    file_names = [
        "Bundesliga1", "Eredivisie", "EthnikiKatigoria", "FutbolLigi1",
        "JupilerLeague", "LaLigaPrimeraDivision", "LeChampionnat",
        "LigaI", "PremierLeague", "SerieA"
    ]

    for league in file_names:
        file_name = f"{league}_AllBookmakers.csv_isSuprise.csv"
        input_path = os.path.join("..", "Data", "FinalData", "allBookmakers_isSuprise", file_name)
        output_dir = os.path.join("..", "Data", "FinalData", "allBookmakers_isSuprise+StatisticCalcAndConesnsus")
        output_path = os.path.join(output_dir, file_name)

        try:
            if not os.path.exists(input_path):
                print(f"File not found: {input_path}")
                continue

            data = pd.read_csv(input_path)

            # Tworzenie folderu, jeśli nie istnieje
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Tworzenie kolumn statystycznych dla H, D, A
            for result_type, cols in bookmakers_columns["AllBookmakers"].items():
                values = data[cols].dropna(axis=1).values
                data[f"{result_type}_Mean"] = np.mean(values, axis=1)
                data[f"{result_type}_Std"] = np.std(values, axis=1)
                data[f"{result_type}_Shannon"] = [shannon_index(v) for v in values]
                data[f"{result_type}_CV"] = [coefficient_of_variation(v) for v in values]
                data[f"{result_type}_Gini"] = [gini_index(v) for v in values]
                data[f"{result_type}_HHI"] = [hhi_index(v) for v in values]

            # Dodanie kolumny z konsensusem
            data['Consensus'] = data.apply(calculate_consensus, axis=1, columns=bookmakers_columns["AllBookmakers"])

            # Zapisanie pliku
            data.to_csv(output_path, index=False)
            print(f"Processed and saved: {output_path}")

        except Exception as e:
            print(f"Error processing {file_name}: {e}")

# Wywołanie funkcji
calculate_cons()
