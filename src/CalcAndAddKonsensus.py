import pandas as pd
import os

# List of file names
file_names = [
    "Bundesliga1", "Eredivisie", "EthnikiKatigoria", "FutbolLigi1",
    "JupilerLeague", "LaLigaPrimeraDivision", "LeChampionnat",
    "LigaI", "PremierLeague", "ScotishPremierLeague", "SerieA"
]

# Define bookmaker columns for Top2, Top4, and Top6
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

# Function to calculate consensus using Majority Voting
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
def calculate_cons():
    # Process each group (Top2Bookmakers, Top4Bookmakers, Top6Bookmakers)
    for group, columns in bookmakers_columns.items():
        all_leagues_data = []  # Initialize list to store data for all leagues in this group

        for league in file_names:
            file_name = f"{league}_{group}.csv"
            input_path = os.path.join("..", "Data", "Matches Results", "Merged Results", group, file_name)
            output_dir = os.path.join("..", "Data", "MatchesResultsMarged+consensus", group)
            output_path = os.path.join(output_dir, file_name)

            try:
                # Load the file
                if not os.path.exists(input_path):
                    print(f"File not found: {input_path}")
                    continue

                data = pd.read_csv(input_path)

                # Convert odds to probabilities
                for col in columns["H"]:
                    data[f"{col}_Prob"] = round((1 / data[col]) * 100, 4)
                for col in columns["D"]:
                    data[f"{col}_Prob"] = round((1 / data[col]) * 100, 4)
                for col in columns["A"]:
                    data[f"{col}_Prob"] = round((1 / data[col]) * 100, 4)

                # Add consensus column using Majority Voting
                data['Consensus'] = data.apply(calculate_consensus, axis=1, columns=columns)

                # Aggregate probabilities (mean and standard deviation)
                data['Mean_Prob_H'] = round(data[[f"{col}_Prob" for col in columns["H"]]].mean(axis=1, skipna=True), 4)
                data['Std_Dev_Prob_H'] = round(data[[f"{col}_Prob" for col in columns["H"]]].std(axis=1, skipna=True), 4)

                data['Mean_Prob_D'] = round(data[[f"{col}_Prob" for col in columns["D"]]].mean(axis=1, skipna=True), 4)
                data['Std_Dev_Prob_D'] = round(data[[f"{col}_Prob" for col in columns["D"]]].std(axis=1, skipna=True), 4)

                data['Mean_Prob_A'] = round(data[[f"{col}_Prob" for col in columns["A"]]].mean(axis=1, skipna=True), 4)
                data['Std_Dev_Prob_A'] = round(data[[f"{col}_Prob" for col in columns["A"]]].std(axis=1, skipna=True), 4)

                # Add league name for identification
                data['League'] = league

                # Append the data to the list for all leagues
                all_leagues_data.append(data)

                # Save the processed file in the correct group folder
                os.makedirs(output_dir, exist_ok=True)
                data.to_csv(output_path, index=False)
                print(f"Processed and saved: {output_path}")

            except Exception as e:
                print(f"Error processing {file_name}: {e}")

        # Combine all leagues data into one DataFrame for the current group
        if all_leagues_data:
            combined_data = pd.concat(all_leagues_data, ignore_index=True)
            combined_output_path = os.path.join(output_dir, f"all_leagues_{group}.csv")
            combined_data.to_csv(combined_output_path, index=False)
            print(f"All leagues combined data saved: {combined_output_path}")
