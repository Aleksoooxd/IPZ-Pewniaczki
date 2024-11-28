import os
import pandas as pd
from collections import Counter

def process_files_in_leagues():
    # Define paths and league-country mappings
    path = '../Data/Matches Results/'
    leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat']
    countries = ['england', 'spain', 'germany', 'italy', 'france']

    # Create a directory to save results
    os.makedirs('../Data/Columns Info/', exist_ok=True)

    # List to store all column names across all leagues
    all_columns = []

    total_files_all_leagues = 0  # Initialize the counter for all files across leagues
    league_global_stats = {}  # Dictionary to hold global stats per league

    for i, league in enumerate(leagues):
        path2 = os.path.join(path, countries[i])
        league_columns = []  # List to store column names specific to the league

        try:
            files = os.listdir(path2)
            league_files = [file for file in files if file.endswith('.csv') and file.startswith(league)]
            total_files = len(league_files)  # Count the number of league-specific files
            total_files_all_leagues += total_files  # Add to the global total count

            if not league_files:
                print(f"No files found for {league} in {path2}")
                continue

            print(f"Processing {total_files} files for {league} in {path2}")

            for file in league_files:
                file_path = os.path.join(path2, file)
                try:
                    # Read the first row (column names) of the CSV file
                    df = pd.read_csv(file_path, nrows=0, encoding='unicode_escape')  # nrows=0 to read only the header
                    league_columns.extend(df.columns.tolist())  # Add column names to the league-specific list
                    all_columns.extend(df.columns.tolist())  # Add column names to the global list
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")

            # Count the occurrences of each column for the league
            league_column_counts = Counter(league_columns)

            # Calculate percentage of occurrences for each column in the league
            league_total_files = len(league_files)
            league_data = []
            for column, count in league_column_counts.items():
                percentage = (count / league_total_files) * 100
                league_data.append({'Column Name': column, 'Count': count, 'Percentage': percentage})

            # Save league-specific stats to a CSV file
            league_df = pd.DataFrame(league_data)
            league_output_file = f'../Data/Columns Info/{league}columns_stats.csv'
            league_df.to_csv(league_output_file, index=False)
            print(f"Saved column stats for {league} in {league_output_file}")

            # Add stats to global dictionary
            league_global_stats[league] = league_column_counts

        except Exception as e:
            print(f"Error processing {league}: {e}")

    # Print the total number of files across all leagues
    print(f"Total files across all leagues: {total_files_all_leagues}")

    # Check if any files were processed
    if total_files_all_leagues == 0:
        print("No files were processed. Make sure the paths and files are correct.")
    else:
        # Count the occurrences of each column across all leagues
        global_column_counts = Counter(all_columns)

        # Calculate the percentage of occurrences for each column relative to the total number of files across all leagues
        global_data = []
        for column, count in global_column_counts.items():
            percentage = (count / total_files_all_leagues) * 100
            global_data.append({'Column Name': column, 'Count': count, 'Percentage': percentage})

        # Save global stats to a CSV file
        global_df = pd.DataFrame(global_data)
        global_output_file = '../Data/Columns Info/All_Columns_Stats.csv'
        global_df.to_csv(global_output_file, index=False)
        print(f"Saved global column stats to {global_output_file}")

# Call the function to process files
process_files_in_leagues()
