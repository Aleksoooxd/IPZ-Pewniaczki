import os
import pandas as pd
import chardet
import numpy as np
from collections import Counter
from helpfunctions import normalize_names,shannon_index,coefficient_of_variation,gini_index,hhi_index,calculate_consensus
class FileOperator:
    def __init__(self, save_path=os.path.join(os.getcwd(),'Data','Matches Results')):
        self.save_path = save_path
        self.leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat','PremierLeague','Eredivisie','JupilerLeague','LigaI','FutbolLigi1','EthnikiKatigoria']
        self.countries = ['england', 'spain', 'germany', 'italy', 'france','scotland','netherlands','belgium','portugal','turkey','greece']
        self.sessonCodes = ['0405', '0506', '0607', '0708', '0809', '0910', '1011', '1112', '1213', '1314', '1415', '1516', '1617', '1718', '1819', '1920', '2021', '2122', '2223', '2324', '2425']
        self.club_values = pd.read_csv(os.path.join(os.getcwd(),'Data','Club Info','clubs_report_from_transfermarkt.csv'), index_col=0)
    def detect_encoding(self, file_path):
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        return result['encoding']
    def update_club_vals(self):
        path = os.path.join(os.getcwd(),'Data','Club Info','clubs_report_from_transfermarkt.csv')
        self.club_values = pd.read_csv(path, index_col=0)

    def add_matchday_to_season(self):
        import os
        import pandas as pd

        path2 = os.path.join(self.save_path, "Merged Results/allSeasons")
        try:
            files = os.listdir(path2)
            league_files = [file for file in files if file.endswith('.csv')]
            for file in league_files:
                file_path = os.path.join(path2, file)
                encoding = self.detect_encoding(file_path)
                try:
                    df = pd.read_csv(file_path, encoding=encoding, low_memory=False)

                    # Initialize a dictionary to keep track of the matchday count for each team
                    matchday_counter = {}

                    # Function to assign matchday and update the counter
                    def assign_matchday(row):
                        season = row['Season']
                        home_team = row['HomeTeam']
                        away_team = row['AwayTeam']

                        # Initialize counters for the season if not present
                        if season not in matchday_counter:
                            matchday_counter[season] = {}
                        if home_team not in matchday_counter[season]:
                            matchday_counter[season][home_team] = 0
                        if away_team not in matchday_counter[season]:
                            matchday_counter[season][away_team] = 0

                        # Increment counters and assign values
                        matchday_counter[season][home_team] += 1
                        matchday_counter[season][away_team] += 1

                        row['HomeMatchday'] = matchday_counter[season][home_team]
                        row['AwayMatchday'] = matchday_counter[season][away_team]

                        return row

                    # Apply the function to each row
                    df = df.apply(assign_matchday, axis=1)

                    # Save updated DataFrame back to CSV
                    df.to_csv(file_path, index=False)
                    print(f"Added HomeMatchday and AwayMatchday columns to {file}")
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
        except Exception as e:
            print(f"Error reading file: {e}")

    def merge_files(self, league_name, country_name, selected_columns=None, output_suffix="allSeasons"):
        output_dir = os.path.join(os.getcwd(),'Data','Matches Results','Merged Results',f"{output_suffix}")
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
        temp_df.drop(temp_df[temp_df['FTR'] == 1.0].index, inplace=True)
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
    def count_collumns(self):

        os.makedirs(os.path.join(os.getcwd(),'Data/Columns Info'), exist_ok=True)
        # List to store all column names across all leagues
        all_columns = []
        total_files_all_leagues = 0  # Initialize the counter for all files across leagues
        league_global_stats = {}  # Dictionary to hold global stats per league
        for i, league in enumerate(self.leagues):
            path2 = os.path.join(self.save_path, self.countries[i])
            league_columns = []
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
                        df = pd.read_csv(file_path, nrows=0, encoding='unicode_escape')
                        league_columns.extend(df.columns.tolist())
                        all_columns.extend(df.columns.tolist())
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
                league_output_file = os.path.join(os.getcwd(),'Data/Columns Info',f'{league}columns_stats.csv')
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
            global_output_file = os.path.join(os.getcwd(),'Data/Columns Info/All_Columns_Stats.csv')
            global_df.to_csv(global_output_file, index=False)
            print(f"Saved global column stats to {global_output_file}")
    def generate_all_bookmakers(self):
        selected_columns = [
            'Div', 'Season', 'Date', 'HomeTeam', 'AwayTeam', 'FTR',
            'HomeValue', 'AwayValue','HomeMatchday','AwayMatchday','FTHG','FTAG'
        ]
        all_bookmaker_columns = [
            'B365H', 'B365D', 'B365A', 'BFH', 'BFD', 'BFA', 'BSH', 'BSD', 'BSA', 'BWH', 'BWD', 'BWA',
            'GBH', 'GBD', 'GBA', 'IWH', 'IWD', 'IWA', 'LBH', 'LBD', 'LBA', 'PSH', 'PSD', 'PSA',
            'SOH', 'SOD', 'SOA', 'SBH', 'SBD', 'SBA', 'SJH', 'SJD', 'SJA', 'SYH', 'SYD', 'SYA',
            'VCH', 'VCD', 'VCA', 'WHH', 'WHD', 'WHA'
        ]
        required_columns = selected_columns + all_bookmaker_columns
        input_path = os.path.join(self.save_path, 'Merged Results/allSeasons')
        output_dir = os.path.join(os.getcwd(),'Data/FinalData/AllBookmakers')
        os.makedirs(output_dir, exist_ok=True)
        files = os.listdir(input_path)
        for file in files:
            if file.endswith('.csv'):
                league = file.split('_')[0]
                file_path = os.path.join(input_path, file)
                try:
                    merged_data = pd.read_csv(file_path,low_memory=False)
                except Exception as e:
                    print(f"Nie udało się wczytać pliku dla ligi {league}: {e}")
                    continue
                for col in required_columns:
                    if col not in merged_data.columns:
                        merged_data[col] = pd.NA
                merged_data = merged_data[required_columns]
                merged_data = merged_data.fillna(1.0)
                #merged_data = merged_data.infer_objects(copy=False)
                output_file = os.path.join(output_dir, f"{league}_AllBookmakers.csv")
                try:
                    merged_data.to_csv(output_file, index=False)
                    print(f"Zapisano plik dla ligi {league}: {output_file}")
                except Exception as e:
                    print(f"Nie udało się zapisać pliku dla ligi {league}: {e}")
        self.add_isSuprise_column()
    def generate_all_seasons(self):
        for i, league in enumerate(self.leagues):
            self.merge_files(league, self.countries[i])
    def generate_seasons_with_values(self):
        self.generate_all_seasons()
        normalize_names()
        self.update_club_vals()
        self.generate_all_seasons()
        self.add_matchday_to_season()
    def add_isSuprise_column(self):
        input_base_directory = os.path.join(os.getcwd(),'Data/FinalData/AllBookmakers')
        output_directory = input_base_directory
        os.makedirs(output_directory, exist_ok=True)
        for filename in os.listdir(input_base_directory):
            if filename.endswith(".csv"):
                file_path = os.path.join(input_base_directory, filename)
                try:
                    print(f"Processing file: {filename}")
                    data = pd.read_csv(file_path)
                    home_stakeholders = [col for col in data.columns if col.endswith("H")]
                    draw_stakeholders = [col for col in data.columns if col.endswith("D")]
                    away_stakeholders = [col for col in data.columns if col.endswith("A")]
                    data['Avg_H'] = data[home_stakeholders].mean(axis=1)
                    data['Avg_D'] = data[draw_stakeholders].mean(axis=1)
                    data['Avg_A'] = data[away_stakeholders].mean(axis=1)
                    data['isSuprise_H'] = (
                        (data['FTR'] == 'H') & (data['Avg_H'] > data[['Avg_D', 'Avg_A']].max(axis=1))
                    ).astype(int)
                    data['isSuprise_D'] = (
                        (data['FTR'] == 'D') & (data['Avg_D'] > data[['Avg_H', 'Avg_A']].max(axis=1))
                    ).astype(int)
                    data['isSuprise_A'] = (
                        (data['FTR'] == 'A') & (data['Avg_A'] > data[['Avg_H', 'Avg_D']].max(axis=1))
                    ).astype(int)
                    data['isSuprise'] = data['isSuprise_H'] + data['isSuprise_D'] + data['isSuprise_A']
                    data = data.drop(columns=['Avg_H', 'Avg_D', 'Avg_A'])
                    output_path = os.path.join(output_directory, f"{filename}")
                    data.to_csv(output_path, index=False)
                    print(f"File processed successfully: {output_path}")
                except Exception as e:
                    print(f"Error processing file {filename}: {e}")
    def add_statistics_and_consensus(self):
        bookmakers_columns = {
            "AllBookmakers": {
                "H": ["B365H", "BFH", "BSH", "BWH", "GBH", "IWH", "LBH", "PSH", "SOH", "SBH", "SJH", "SYH", "VCH",
                      "WHH"],
                "D": ["B365D", "BFD", "BSD", "BWD", "GBD", "IWD", "LBD", "PSD", "SOD", "SBD", "SJD", "SYD", "VCD",
                      "WHD"],
                "A": ["B365A", "BFA", "BSA", "BWA", "GBA", "IWA", "LBA", "PSA", "SOA", "SBA", "SJA", "SYA", "VCA",
                      "WHA"]
            }
        }
        for league in self.leagues:
            file_name = f"{league}_AllBookmakers.csv"
            input_path = os.path.join(os.getcwd(), "Data", "FinalData", "AllBookmakers", file_name)
            output_dir = os.path.join(os.getcwd(), "Data", "FinalData", "AllBookmakers")
            output_path = os.path.join(output_dir, file_name)
            try:
                if not os.path.exists(input_path):
                    print(f"File not found: {input_path}")
                    continue
                data = pd.read_csv(input_path)
                # Tworzenie folderu, jeśli nie istnieje
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                # Tworzenie kolumn statystycznych dla H, D, A
                for result_type, cols in bookmakers_columns["AllBookmakers"].items():
                    values = data[cols].dropna(axis=1).values
                    data[f"{result_type}_Mean"] = np.round(np.mean(values, axis=1), 4)
                    data[f"{result_type}_Std"] = np.round(np.std(values, axis=1), 4)
                    data[f"{result_type}_Shannon"] = [shannon_index(v) for v in values]
                    data[f"{result_type}_CV"] = [coefficient_of_variation(v) for v in values]
                    data[f"{result_type}_Gini"] = [gini_index(v) for v in values]
                    data[f"{result_type}_HHI"] = [hhi_index(v) for v in values]
                # Dodanie kolumny z konsensusem
                data['Consensus'] = data.apply(calculate_consensus, axis=1, columns=bookmakers_columns["AllBookmakers"])
                # Zapisanie pliku
                data.to_csv(output_path, index=False)
                print(f"Processed and saved: {output_path}")
            except Exception as e:
                print(f"Error processing {file_name}: {e}")

    def create_placement_columns(self, dataframe):
        dataframe['FTHG'] = pd.to_numeric(dataframe['FTHG'], errors='coerce')
        dataframe['FTAG'] = pd.to_numeric(dataframe['FTAG'], errors='coerce')
        dataframe['HomeMatchday'] = pd.to_numeric(dataframe['HomeMatchday'], errors='coerce')
        dataframe['HomeTeamPlacement'] = None
        dataframe['AwayTeamPlacement'] = None
        dataframe['HomeForm3'] = 0
        dataframe['HomeForm5'] = 0
        dataframe['HomeFormSeason'] = 0
        dataframe['AwayForm3'] = 0
        dataframe['AwayForm5'] = 0
        dataframe['AwayFormSeason'] = 0
        dataframe['HomeGoals3'] = 0
        dataframe['HomeGoals5'] = 0
        dataframe['HomeGoalsSeason'] = 0
        dataframe['AwayGoals3'] = 0
        dataframe['AwayGoals5'] = 0
        dataframe['AwayGoalsSeason'] = 0
        dataframe['HTLSP'] = None
        dataframe['ATLSP'] = None

        def calculate_season_placements(season_df):
            standings = {}
            placements = []
            form_data = {}
            goals_data = {}

            for matchday in sorted(season_df['HomeMatchday'].unique()):
                matchday_df = season_df[season_df['HomeMatchday'] == matchday]

                for _, row in matchday_df.iterrows():
                    home_team = row['HomeTeam']
                    away_team = row['AwayTeam']
                    ftr = row['FTR']
                    fthg = row['FTHG']
                    ftag = row['FTAG']

                    if home_team not in standings:
                        standings[home_team] = {'points': 0, 'goal_diff': 0, 'goals_scored': 0}
                        form_data[home_team] = []
                        goals_data[home_team] = []
                    if away_team not in standings:
                        standings[away_team] = {'points': 0, 'goal_diff': 0, 'goals_scored': 0}
                        form_data[away_team] = []
                        goals_data[away_team] = []

                    if ftr == 'H':
                        standings[home_team]['points'] += 3
                        form_data[home_team].append(3)
                        form_data[away_team].append(0)
                    elif ftr == 'A':
                        standings[away_team]['points'] += 3
                        form_data[home_team].append(0)
                        form_data[away_team].append(3)
                    elif ftr == 'D':
                        standings[home_team]['points'] += 1
                        standings[away_team]['points'] += 1
                        form_data[home_team].append(1)
                        form_data[away_team].append(1)

                    standings[home_team]['goal_diff'] += fthg - ftag
                    standings[home_team]['goals_scored'] += fthg
                    standings[away_team]['goal_diff'] += ftag - fthg
                    standings[away_team]['goals_scored'] += ftag

                    goals_data[home_team].append(fthg)
                    goals_data[away_team].append(ftag)

                sorted_standings = sorted(standings.items(), key=lambda x: (
                    -x[1]['points'], -x[1]['goal_diff'], -x[1]['goals_scored'], x[0]))
                placement_map = {team[0]: idx + 1 for idx, team in enumerate(sorted_standings)}

                for _, row in matchday_df.iterrows():
                    placements.append((placement_map[row['HomeTeam']], placement_map[row['AwayTeam']]))

            return placements, form_data, goals_data, placement_map

        previous_season_placements = {}

        for season in sorted(dataframe['Season'].unique()):
            season_mask = dataframe['Season'] == season
            season_df = dataframe[season_mask].sort_values(by=['HomeMatchday', 'Date'])

            season_placements, form_data, goals_data, final_placements = calculate_season_placements(season_df)

            home_placements, away_placements = zip(*season_placements)
            dataframe.loc[season_mask, 'HomeTeamPlacement'] = home_placements
            dataframe.loc[season_mask, 'AwayTeamPlacement'] = away_placements

            for index, row in season_df.iterrows():
                home_team = row['HomeTeam']
                away_team = row['AwayTeam']
                matchday = row['HomeMatchday']

                home_form3 = sum(form_data[home_team][max(0, matchday - 3):matchday])
                home_form5 = sum(form_data[home_team][max(0, matchday - 5):matchday])
                home_form_season = sum(form_data[home_team][:matchday])

                away_form3 = sum(form_data[away_team][max(0, matchday - 3):matchday])
                away_form5 = sum(form_data[away_team][max(0, matchday - 5):matchday])
                away_form_season = sum(form_data[away_team][:matchday])

                home_goals3 = sum(goals_data[home_team][max(0, matchday - 3):matchday])
                home_goals5 = sum(goals_data[home_team][max(0, matchday - 5):matchday])
                home_goals_season = sum(goals_data[home_team][:matchday])

                away_goals3 = sum(goals_data[away_team][max(0, matchday - 3):matchday])
                away_goals5 = sum(goals_data[away_team][max(0, matchday - 5):matchday])
                away_goals_season = sum(goals_data[away_team][:matchday])

                dataframe.at[index, 'HomeForm3'] = home_form3
                dataframe.at[index, 'HomeForm5'] = home_form5
                dataframe.at[index, 'HomeFormSeason'] = home_form_season
                dataframe.at[index, 'AwayForm3'] = away_form3
                dataframe.at[index, 'AwayForm5'] = away_form5
                dataframe.at[index, 'AwayFormSeason'] = away_form_season
                dataframe.at[index, 'HomeGoals3'] = home_goals3
                dataframe.at[index, 'HomeGoals5'] = home_goals5
                dataframe.at[index, 'HomeGoalsSeason'] = home_goals_season
                dataframe.at[index, 'AwayGoals3'] = away_goals3
                dataframe.at[index, 'AwayGoals5'] = away_goals5
                dataframe.at[index, 'AwayGoalsSeason'] = away_goals_season
                dataframe.at[index, 'HTLSP'] = previous_season_placements.get(home_team, 0)
                dataframe.at[index, 'ATLSP'] = previous_season_placements.get(away_team, 0)

            previous_season_placements = final_placements

        return dataframe

    def calculate_placements(self):
        input_path = os.path.join(os.getcwd(),'Data/FinalData/AllBookmakers')
        os.makedirs(input_path, exist_ok=True)
        files = os.listdir(input_path)
        for file in files:
            if file.endswith('.csv'):
                league = file.split('_')[0]

                input_file = os.path.join(input_path, f'{league}_AllBookmakers.csv')

                if os.path.exists(input_file):
                    print(f"Processing {league}...")

                    df_new = pd.read_csv(input_file)
                    df_updated = self.create_placement_columns(df_new)

                    output_path = os.path.join(input_path, f'{league}_AllBookmakers.csv')
                    df_updated.to_csv(output_path, index=False)
                    print(f"File saved to {output_path}")
                else:
                    print(f"File {input_file} does not exist. Skipping...")

        return "Processing complete"