import pandas as pd
import os

# List of file names
file_names = [
    "Bundesliga1_Top4Bookmakers.csv",
    "Eredivisie_Top4Bookmakers.csv",
    "EthnikiKatigoria_Top4Bookmakers.csv",
    "FutbolLigi1_Top4Bookmakers.csv",
    "JupilerLeague_Top4Bookmakers.csv",
    "LaLigaPrimeraDivision_Top4Bookmakers.csv",
    "LeChampionnat_Top4Bookmakers.csv",
    "LigaI_Top4Bookmakers.csv",
    "PremierLeague_Top4Bookmakers.csv",
    "ScotishPremierLeague_Top4Bookmakers.csv",
    "SerieA_Top4Bookmakers.csv"
]

# Define bookmaker columns
bookmakers_columns = {
    "H": ["B365H", "BWH", "LBH", "VCH"],
    "D": ["B365D", "BWD", "LBD", "VCD"],
    "A": ["B365A", "BWA", "LBA", "VCA"]
}

# Function to calculate consensus using Majority Voting
def calculate_consensus(row):
    # Count the number of votes for each outcome (H, D, A)
    votes_H = sum([1 for col in bookmakers_columns["H"] if row[col] < row[bookmakers_columns["D"][0]] and row[col] < row[bookmakers_columns["A"][0]]])
    votes_D = sum([1 for col in bookmakers_columns["D"] if row[col] < row[bookmakers_columns["H"][0]] and row[col] < row[bookmakers_columns["A"][0]]])
    votes_A = sum([1 for col in bookmakers_columns["A"] if row[col] < row[bookmakers_columns["H"][0]] and row[col] < row[bookmakers_columns["D"][0]]])

    # Majority Voting - select the outcome with the most votes
    if votes_H > max(votes_D, votes_A):
        return 'H'
    elif votes_D > max(votes_H, votes_A):
        return 'D'
    elif votes_A > max(votes_H, votes_D):
        return 'A'
    else:
        return 'No Consensus'

# Process each file
for file_name in file_names:
    file_path = f"../Data/Matches Results/Merged Results/Top4Bookmakers/{file_name}"

    try:
        # Load the file
        data = pd.read_csv(file_path)

        # Convert odds to probabilities
        for col in bookmakers_columns["H"]:
            data[f"{col}_Prob"] = (1 / data[col]) * 100
        for col in bookmakers_columns["D"]:
            data[f"{col}_Prob"] = (1 / data[col]) * 100
        for col in bookmakers_columns["A"]:
            data[f"{col}_Prob"] = (1 / data[col]) * 100

        # Add consensus column using Majority Voting
        data['Consensus'] = data.apply(calculate_consensus, axis=1)

        # Aggregate probabilities (mean and standard deviation)
        data['Mean_Prob_H'] = data[[f"{col}_Prob" for col in bookmakers_columns["H"]]].mean(axis=1, skipna=True)
        data['Std_Dev_Prob_H'] = data[[f"{col}_Prob" for col in bookmakers_columns["H"]]].std(axis=1, skipna=True)

        data['Mean_Prob_D'] = data[[f"{col}_Prob" for col in bookmakers_columns["D"]]].mean(axis=1, skipna=True)
        data['Std_Dev_Prob_D'] = data[[f"{col}_Prob" for col in bookmakers_columns["D"]]].std(axis=1, skipna=True)

        data['Mean_Prob_A'] = data[[f"{col}_Prob" for col in bookmakers_columns["A"]]].mean(axis=1, skipna=True)
        data['Std_Dev_Prob_A'] = data[[f"{col}_Prob" for col in bookmakers_columns["A"]]].std(axis=1, skipna=True)

        output_path = f"../Data/MatchesResultsMarged+consensus/{file_name}"
        data.to_csv(output_path, index=False)
        print(f"Processed and saved: {output_path}")

    except Exception as e:
        print(f"Error processing {file_name}: {e}")
