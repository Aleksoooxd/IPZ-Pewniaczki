import os
import pandas as pd


def merge_files():
    path = '../Data/Matches Results/'
    leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat']
    country = ['england', 'spain', 'germany', 'italy', 'france']

    # Create the target directory if it doesn't exist
    os.makedirs('../Data/Matches Results/Merged Results/', exist_ok=True)

    for i, league in enumerate(leagues):
        path2 = os.path.join(path, country[i])

        try:
            files = os.listdir(path2)
            league_files = [file for file in files if file.endswith('.csv') and file.startswith(league)]

            if not league_files:
                print(f"No files found for {league} in {path2}")
                continue

            df = pd.DataFrame()
            for file in league_files:
                try:
                    temp_df = pd.read_csv(os.path.join(path2, file))
                    df = pd.concat([df, temp_df], ignore_index=True)
                except Exception as e:
                    print(f"Error reading file {file} in {path2}: {e}")

            output_path = f'../Data/Matches Results/Merged Results/{league}_allSeasons.csv'
            df.to_csv(output_path, index=False)
            print(f"Saved merged file for {league} to {output_path}")

        except Exception as e:
            print(f"Error processing {league}: {e}")


merge_files()
