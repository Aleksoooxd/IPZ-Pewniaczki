import os
import pandas as pd
from collections import Counter


def count_columns_files():
    # Define paths and league-country mappings
    path = '../Data/Matches Results/'
    leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat']
    countries = ['england', 'spain', 'germany', 'italy', 'france']

    # Create the target directory if it doesn't exist
    os.makedirs('../Data/Columns Info/', exist_ok=True)

    # Dictionary to hold column statistics for each league
    league_columns_stats = {}

    for i, league in enumerate(leagues):
        path2 = os.path.join(path, countries[i])
        column_counter = Counter()

        try:
            files = os.listdir(path2)
            league_files = [file for file in files if file.endswith('.csv') and file.startswith(league)]

            if not league_files:
                print(f"No files found for {league} in {path2}")
                continue

            for file in league_files:
                try:
                    # Read the file and extract columns
                    temp_df = pd.read_csv(os.path.join(path2, file))
                    columns = temp_df.columns.tolist()
                    column_counter.update(columns)  # Count the occurrences of each column
                except Exception as e:
                    print(f"Error reading file {file} in {path2}: {e}")

            # Calculate total column occurrences
            total_occurrences = sum(column_counter.values())

            # Add percentage to the column statistics
            column_stats = {
                column: {"Count": count, "Percentage": (count / total_occurrences) * 10000}
                for column, count in column_counter.items()
            }

            # Save the column statistics for the league
            league_columns_stats[league] = column_stats

            # Convert stats to a DataFrame for better readability and save to CSV
            column_stats_df = pd.DataFrame.from_dict(column_stats, orient='index')
            column_stats_df = column_stats_df.sort_index()  # Sort columns alphabetically
            output_path = f'../Data/Columns Info/{league}_columns_stats.csv'
            column_stats_df.to_csv(output_path)
            print(f"Saved column stats for {league} to {output_path}")

        except Exception as e:
            print(f"Error processing {league}: {e}")

    # Merge all leagues' stats into a single CSV file
    combined_stats = pd.DataFrame()
    for league, stats in league_columns_stats.items():
        league_df = pd.DataFrame.from_dict(stats, orient='index')[["Count"]]
        league_df.rename(columns={"Count": league}, inplace=True)
        combined_stats = pd.concat([combined_stats, league_df], axis=1)

    combined_stats = combined_stats.fillna(0).astype(int)  # Replace NaN with 0 and ensure integer type
    combined_output_path = '../Data/Columns Info/Combined_Columns_Stats.csv'
    combined_stats.to_csv(combined_output_path)
    print(f"Saved combined column stats for all leagues to {combined_output_path}")


count_columns_files()
