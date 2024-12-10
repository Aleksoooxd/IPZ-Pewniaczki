import os
import pandas as pd

class FileOperator():
    def __init__(self, save_path="../Data/Matches Results/"):
        self.save_path = save_path
        self.leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat', 'Ekstraklasa']
        self.countries = ['england', 'spain', 'germany', 'italy', 'france', 'poland']
        self.sessonCodes = ['0405', '0506', '0607', '0708', '0809', '0910', '1011', '1112', '1213', '1314', '1415', '1516', '1617', '1718', '1819', '1920', '2021', '2122', '2223', '2324', '2425']

    def detect_encoding(self, file_path):
        """Detect file encoding."""
        import chardet
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        return result['encoding']

    def merge_league_sessions(self, league_name, country_name, selected_columns):
        """Merge sessions for a league and save to a CSV file."""
        # Create the output directory for merged files if it doesn't exist
        output_dir = "../Data/Matches Results/Merged Results/Top4Bookmakers"
        os.makedirs(output_dir, exist_ok=True)

        # Path to the folder containing the league files
        league_path = os.path.join(self.save_path, country_name)
        if not os.path.exists(league_path):
            print(f"Directory not found: {league_path}")
            return

        # List of files to merge for the selected league and season codes
        files_to_merge = [
            os.path.join(league_path, f'{league_name}_{season}.csv')
            for season in self.sessonCodes
        ]

        merged_df = pd.DataFrame()

        # Process each file
        for file_path in files_to_merge:
            if os.path.exists(file_path):
                try:
                    # Detect file encoding
                    encoding = self.detect_encoding(file_path)

                    # Load only selected columns
                    temp_df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        on_bad_lines='skip',
                        usecols=lambda col: col in selected_columns  # Filter columns
                    )

                    # Concatenate the data into a merged dataframe
                    merged_df = pd.concat([merged_df, temp_df], ignore_index=True)
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
            else:
                print(f"File not found: {file_path}")

        # Drop completely empty columns
        try:
            merged_df.dropna(axis=1, how='all', inplace=True)
        except Exception as e:
            print(f"Error cleaning data: {e}")

        # Drop rows with any empty cells
        try:
            merged_df.dropna(axis=0, how='any', inplace=True)
        except Exception as e:
            print(f"Error dropping rows with empty cells: {e}")

        # Save the merged dataframe to a CSV file
        try:
            output_file = os.path.join(output_dir, f'{league_name}_Top4Bookmakers.csv')
            merged_df.to_csv(output_file, index=False)
            print(f"Merged file saved to {output_file}")
        except Exception as e:
            print(f"Error saving merged file: {e}")


# List of selected columns for top 6 bookmakers (6 columns for each bookmaker)
selected_columns_PremierLeague = [
    'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR',
    'HTHG', 'HTAG', 'HTR', 'Referee', 'HS', 'AS', 'HST',
    'AST', 'HC', 'AC', 'HF', 'AF', 'HY', 'AY', 'HR', 'AR',
    'Div',
    'B365H', 'B365D', 'B365A',  # Bookmaker B365 (Home, Draw, Away)
    'BWH', 'BWD', 'BWA',  # Bookmaker BWH (Home, Draw, Away)
    'VCH', 'VCD', 'VCA',  # Bookmaker VCH (Home, Draw, Away)
    'LBH', 'LBD', 'LBA',  # Bookmaker LBH (Home, Draw, Away)

]

# Initialize the FileOperator class
FileOp = FileOperator()

# Merge sessions for each league and save the results
FileOp.merge_league_sessions('PremierLeague', 'england', selected_columns_PremierLeague)
FileOp.merge_league_sessions('LaLigaPrimeraDivision', 'spain', selected_columns_PremierLeague)
FileOp.merge_league_sessions('Bundesliga1', 'germany', selected_columns_PremierLeague)
FileOp.merge_league_sessions('SerieA', 'italy', selected_columns_PremierLeague)
FileOp.merge_league_sessions('LeChampionnat', 'france', selected_columns_PremierLeague)
