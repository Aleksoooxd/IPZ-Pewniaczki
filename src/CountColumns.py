import os
import pandas as pd
from collections import Counter

def process_files_in_leagues():
    # Define paths and league-country mappings
    path = '../Data/Matches Results/'
    leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat']
    countries = ['england', 'spain', 'germany', 'italy', 'france']

    # List to store all column names
    all_columns = []

    total_files_all_leagues = 0  # Initialize the counter for all files across leagues

    for i, league in enumerate(leagues):
        path2 = os.path.join(path, countries[i])

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
                    df = pd.read_csv(file_path, nrows=0,encoding='unicode_escape')  # nrows=0 to read only the header
                    all_columns.extend(df.columns.tolist())  # Add column names to the list
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")

        except Exception as e:
            print(f"Error processing {league}: {e}")

    # Print the total number of files across all leagues
    print(f"Total files across all leagues: {total_files_all_leagues}")

    # Check if any files were processed
    if total_files_all_leagues == 0:
        print("No files were processed. Make sure the paths and files are correct.")
    else:
        # Count the occurrences of each column
        column_counts = Counter(all_columns)

        # Calculate the percentage of occurrences for each column relative to the total number of files
        output_data = []
        for column, count in column_counts.items():
            percentage = (count / total_files_all_leagues) * 100
            output_data.append({'Column Name': column, 'Count': count, 'Percentage': percentage})

        # Create a DataFrame with the results
        output_df = pd.DataFrame(output_data)

        # Save the results to a CSV file
        output_file = '../Data/Columns Info/All_Columns_Stats.csv'
        output_df.to_csv(output_file, index=False)

        print(f"Results saved in file: {output_file}")

# Call the function to process files
process_files_in_leagues()
