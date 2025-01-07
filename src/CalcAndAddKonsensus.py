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
        "Top2Bookmakers": {
            "H": ["B365H", "BWH"],
            "D": ["B365D", "BWD"],
            "A": ["B365A", "BWA"]
        },
        "Top4Bookmakers": {
            "H": ["B365H", "BWH", "WHH", "IWH"],
            "D": ["B365D", "BWD", "WHD", "IWD"],
            "A": ["B365A", "BWA", "WHA", "IWA"]
        },
        "Top6Bookmakers": {
            "H": ["B365H", "BWH", "WHH", "IWH", "VCH", "LBH"],
            "D": ["B365D", "BWD", "WHD", "IWD", "VCD", "LBD"],
            "A": ["B365A", "BWA", "WHA", "IWA", "VCA", "LBA"]
        }
    }

    file_names = [
        "Bundesliga1", "Eredivisie", "EthnikiKatigoria", "FutbolLigi1",
        "JupilerLeague", "LaLigaPrimeraDivision", "LeChampionnat",
        "LigaI", "PremierLeague", "ScotishPremierLeague", "SerieA"
    ]

    for group, columns in bookmakers_columns.items():
        for league in file_names:
            file_name = f"{league}_{group}.csv"
            input_path = os.path.join("..", "Data", "Matches Results", "Merged Results", group, file_name)
            output_dir = os.path.join("..", "Data", "MatchesResultsMarged+consensus", group)
            output_path = os.path.join(output_dir, file_name)

            try:
                if not os.path.exists(input_path):
                    print(f"File not found: {input_path}")
                    continue

                data = pd.read_csv(input_path)

                # Tworzenie kolumn statystycznych dla H, D, A
                for result_type, cols in columns.items():
                    values = data[cols].dropna(axis=1).values
                    data[f"{result_type}_Mean"] = np.mean(values, axis=1)
                    data[f"{result_type}_Std"] = np.std(values, axis=1)
                    data[f"{result_type}_Shannon"] = [shannon_index(v) for v in values]
                    data[f"{result_type}_CV"] = [coefficient_of_variation(v) for v in values]
                    data[f"{result_type}_Gini"] = [gini_index(v) for v in values]
                    data[f"{result_type}_HHI"] = [hhi_index(v) for v in values]

                # Dodanie kolumny z konsensusem
                data['Consensus'] = data.apply(calculate_consensus, axis=1, columns=columns)

                # Zapisanie pliku
                os.makedirs(output_dir, exist_ok=True)
                data.to_csv(output_path, index=False)
                print(f"Processed and saved: {output_path}")

            except Exception as e:
                print(f"Error processing {file_name}: {e}")