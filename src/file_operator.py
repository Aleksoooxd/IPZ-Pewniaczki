import os
import pandas as pd
import chardet

class FileOperator:
    def __init__(self, save_path="../Data/Matches Results/"):
        self.save_path = save_path
        self.leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat', 'Ekstraklasa']
        self.countries = ['england', 'spain', 'germany', 'italy', 'france', 'poland']
        self.sessonCodes = ['0405', '0506', '0607', '0708', '0809', '0910', '1011', '1112', '1213', '1314', '1415', '1516', '1617', '1718', '1819', '1920', '2021', '2122', '2223', '2324', '2425']
        self.club_values = pd.read_csv('..\\IPZ-Pewniaczki\\Data\\Club Info\\clubs_report_from_transfermarkt')
    def detect_encoding(self, file_path):
        """Detect file encoding."""
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        return result['encoding']

    def merge_files(self, league_name, country_name, selected_columns=None, output_suffix="allSeasons"):
        """Merge all season files for a league and save to a CSV file."""
        output_dir = f"../Data/Matches Results/Merged Results/{output_suffix}"
        os.makedirs(output_dir, exist_ok=True)

        league_path = os.path.join(self.save_path, country_name)
        if not os.path.exists(league_path):
            print(f"Directory not found: {league_path}")
            return

        files_to_merge = [
            os.path.join(league_path, f'{league_name}_{season}.csv')
            for season in self.sessonCodes
        ]

        merged_df = pd.DataFrame()

        for file_path in files_to_merge:

            if os.path.exists(file_path):
                try:
                    encoding = self.detect_encoding(file_path)
                    temp_df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        on_bad_lines='skip',
                        usecols=(lambda col: col in selected_columns) if selected_columns else None
                    )
                    try:
                        temp_df = self.modify_df(temp_df)
                    except Exception as e:
                        print(f"Error cleaning date: {e}")
                    merged_df = pd.concat([merged_df, temp_df], ignore_index=True)
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
            else:
                print(f"File not found: {file_path}")

        try:
            merged_df.dropna(axis=1, how='all', inplace=True)
            #merged_df.dropna(axis=0, how='any', inplace=True)
        except Exception as e:
            print(f"Error cleaning data: {e}")

        try:
            output_file = os.path.join(output_dir, f'{league_name}_{output_suffix}.csv')
            merged_df.to_csv(output_file, index=False)
            print(f"Merged file saved to {output_file}")
        except Exception as e:
            print(f"Error saving merged file: {e}")
    def correct_date_format(self,val):
        if isinstance(val, str) and len(val) == 8:
            return val[:6] + "20" + val[6:]
        return val
    def get_club_value(self,club,season):
        try:
            return self.club_values.at[club, season]
        except KeyError:
            return None
    def modify_df(self,temp_df):
        temp_df["Date"] = temp_df["Date"].apply(self.correct_date_format)
        temp_df['Season'] = temp_df['Date'].dt.year.astype(str) + "/" + (temp_df['Date'].dt.year + 1).astype(str).str[
                                                                        2:]

        temp_df['HomeValue'] = temp_df.apply(
            lambda row: self.get_club_value(row['HomeTeam'], row['Season']), axis=1
        )

        temp_df['AwayValue'] = temp_df.apply(
            lambda row: self.get_club_value(row['AwayTeam'], row['Season']), axis=1
        )
        return temp_df