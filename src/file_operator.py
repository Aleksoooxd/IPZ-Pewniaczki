import os
import pandas as pd
import chardet

class FileOperator:
    def __init__(self, save_path="../Data/Matches Results/"):
        self.save_path = save_path
        self.leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat','PremierLeague','Eredivisie','JupilerLeague','LigaI','FutbolLigi1','EthnikiKatigoria']
        self.countries = ['england', 'spain', 'germany', 'italy', 'france','scotland','netherlands','belgium','portugal','turkey','greece']
        self.sessonCodes = ['0405', '0506', '0607', '0708', '0809', '0910', '1011', '1112', '1213', '1314', '1415', '1516', '1617', '1718', '1819', '1920', '2021', '2122', '2223', '2324', '2425']
        self.club_values = pd.read_csv('../Data/Club Info/clubs_report_from_transfermarkt_updated.csv', index_col=0)
    def detect_encoding(self, file_path):
        """Detect file encoding."""
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        return result['encoding']

    def merge_files(self, league_name, country_name, selected_columns=None, output_suffix="allSeasons", use_book=False):
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
                        temp_df = self.modify_df(temp_df,file_path)
                    except Exception as e:
                        print(f"Error cleaning date: {e}")
                    merged_df = pd.concat([merged_df, temp_df], ignore_index=True)
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
            else:
                print(f"File not found: {file_path}")

        try:
            if use_book:
                merged_df.dropna(axis=0, how='any', inplace=True)
        except Exception as e:
            print(f"Error cleaning data: {e}")

        try:
            output_file = os.path.join(output_dir, f'{league_name}_{output_suffix}.csv')
            if country_name == 'scotland':
                output_file = os.path.join(output_dir, f'Scotish{league_name}_{output_suffix}.csv')
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
            return self.club_values.loc[club,season]
        except KeyError:
            return None
    def modify_df(self,temp_df,file_path):
        if "HT" in temp_df.columns:
            temp_df.rename(columns={'HT': 'HomeTeam', 'AT': 'AwayTeam'}, inplace=True)
        temp_df.dropna(axis=1, how='all', inplace=True)
        temp_df.dropna(axis=0, how='all', inplace=True)
        temp_df.dropna(axis=0, how='all',subset=['Div'], inplace=True)
        temp_df["Date"] = temp_df["Date"].apply(self.correct_date_format)
        season = self.extract_season_from_path(file_path)
        temp_df['Season'] = season
        temp_df["HomeTeam"] = temp_df["HomeTeam"].apply(self.correct_clubs)
        temp_df["AwayTeam"] = temp_df["AwayTeam"].apply(self.correct_clubs)
        HomeVals = []
        AwayVals = []
        for i,j in temp_df.iterrows():
            Home = j['HomeTeam']
            Away = j['AwayTeam']
            Season = j['Season']
            HomeVals.append(self.get_club_value(Home,Season))
            AwayVals.append(self.get_club_value(Away,Season))
        temp_df['HomeValue'] = HomeVals
        temp_df['AwayValue'] = AwayVals
        return temp_df
    def correct_clubs(self,val):
        if val =="QPR":
            return "Queens Park Rangers"
        elif val =="Rennes":
            return "Stade Rennais FC"
        elif val=="Verona":
            return "Hellas Verona"
        elif val=="Ajax ":
            return "Ajax"
        elif val=="Feyenoord ":
            return "Feyenoord"
        elif val=="Graafschap ":
            return "Graafschap"
        elif val=="Groningen ":
            return "Groningen"
        elif val=="Heracles ":
            return "Heracles"
        elif val=="Roda ":
            return "Roda"
        elif val=="Utrecht ":
            return "Utrecht"
        elif val=="Vitesse ":
            return "Vitesse"
        elif val=="Willem II ":
            return "Willem II"
        elif val=="Kalithea":
            return "Kallithea"
        elif val=="Aves":
            return "AVS"
        elif val=="Feirense ":
            return "Feirense"
        elif val=="Sparta":
            return "Sparta Rotterdam"
        elif val=="OFI":
            return "OFI Crete"
        elif val=="Roda JC":
            return "Roda"
        else:
            return val
    def extract_season_from_path(self,file_path):
        base_name = os.path.basename(file_path)
        season_code = base_name.split('_')[-1].replace('.csv', '')
        if season_code[2] == '0':
            return '20' + season_code[:2] + '/' + season_code[3:]
        return '20'+season_code[:2] + '/' + season_code[2:]
    def merge_top_books(self):
        output_dir = f"../Data/Matches Results/Merged Results/Merged Books/"
        input_dir = f"../Data/Matches Results/Merged Results/Top4Bookmakers/"
        os.makedirs(output_dir, exist_ok=True)
        files = os.listdir(input_dir)
        merged_df = pd.DataFrame()
        for file in files:
            if file.endswith(".csv"):
                file_path = os.path.join(input_dir, file)
                try:
                    encoding = self.detect_encoding(file_path)
                    temp_df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        on_bad_lines='skip',
                    )
                    try:
                        temp_df = self.modify_df(temp_df,file_path)
                    except Exception as e:
                        pass
                        #print(f"Error cleaning date: {e}")
                    merged_df = pd.concat([merged_df, temp_df], ignore_index=True)
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
        try:
            output_file = os.path.join(output_dir, f'top4combined.csv')
            merged_df.to_csv(output_file, index=False)
            print(f"Merged file saved to {output_file}")
        except Exception as e:
            print(f"Error saving merged file: {e}")
