import os
from collections import Counter
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import shutil
import chardet
import csv



class FileOperator():
    def __init__(self,save_path="../Data/Matches Results/"):
        self.save_path = save_path
        self.leagues = ['PremierLeague', 'LaLigaPrimeraDivision', 'Bundesliga1', 'SerieA', 'LeChampionnat', 'Ekstraklasa']
        self.countries = ['england', 'spain', 'germany', 'italy', 'france', 'poland']
    def merge_files(self):
        output_dir = '../Data/Matches Results/Merged Results/'
        os.makedirs(output_dir, exist_ok=True)
        for i, league in enumerate(self.leagues):
            path2 = os.path.join(self.save_path, self.countries[i])

            try:
                files = os.listdir(path2)
                league_files = [file for file in files if file.endswith('.csv') and file.startswith(league)]

                if not league_files:
                    print(f"No files found for {league} in {path2}")
                    continue

                df = pd.DataFrame()

                for file in league_files:
                    file_path = os.path.join(path2, file)
                    try:
                        # Wykrywanie kodowania pliku
                        encoding = self.detect_encoding(file_path)

                        # Wczytywanie pliku z automatycznym omijaniem problematycznych wierszy
                        temp_df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')

                        # Scalanie danych
                        df = pd.concat([df, temp_df], ignore_index=True)
                    except Exception as e:
                        print(f"Error reading file {file} in {path2}: {e}")

                # Zapisanie połączonego pliku CSV
                output_path = os.path.join(output_dir, f'{league}_allSeasons.csv')
                df.to_csv(output_path, index=False)
                print(f"Saved merged file for {league} to {output_path}")

            except Exception as e:
                print(f"Error processing {league}: {e}")
    def count_collumns(self):
        os.makedirs('../Data/Columns Info/', exist_ok=True)

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
                        df = pd.read_csv(file_path, nrows=0,encoding='unicode_escape')
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

    def detect_encoding(self,file_path):
        """Wykrywanie kodowania pliku."""
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
        return result['encoding']
    # def fill_na_with_data(self,main_file, helper_file, output_file):
    #     helper_data = {}
    #     with open(helper_file, mode='r', encoding='utf-8') as hfile:
    #         reader = csv.reader(hfile)
    #         helper_header = next(reader)
    #         for row in reader:
    #             club = row[0]
    #             year_data = dict(zip(helper_header[1:], row[1:]))
    #             helper_data[club] = year_data
    #     with open(main_file, mode='r', encoding='utf-8') as mfile:
    #         reader = csv.reader(mfile)
    #         main_header = next(reader)
    #         updated_data = [main_header]
    #         for row in reader:
    #             club = row[0]
    #             updated_row = row[:]
    #             if club in helper_data:
    #                 for i, value in enumerate(row[1:], start=1):
    #                     if value.strip().upper() == 'N/A':
    #                         year = main_header[i]
    #                         updated_row[i] = helper_data[club].get(year, 'N/A')
    #             updated_data.append(updated_row)
    #     with open(output_file, mode='w', encoding='utf-8', newline='') as ofile:
    #         writer = csv.writer(ofile)
    #         writer.writerows(updated_data)

FileOp = FileOperator()
FileOp.merge_files()
FileOp.count_collumns()
