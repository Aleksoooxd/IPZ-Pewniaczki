import os
import pandas as pd
import numpy as np

# home_stakeholders = ["B365H", "BFH", "BSH", "BWH", "GBH", "IWH", "LBH", "PSH", "PH", "SOH", "SBH", "SJH", "SYH", "VCH", "WHH"]
# draw_stakeholders = ["B365D", "BFD", "BSD", "BWD", "GBD", "IWD", "LBD", "PSD", "PD", "SOD", "SBD", "SJD", "SYD", "VCD", "WHD"]
# away_stakeholders = ["B365A", "BFA", "BSA", "BWA", "GBA", "IWA", "LBA", "PSA", "PA", "SOA", "SBA", "SJA", "SYA", "VCA", "WHA"]

def add_isSupriseColumn():
    input_base_directory = "../Data/FinalData/allBookmakers"
    output_directory = "../Data/FinalData/allBookmakers_isSuprise"



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

                # Dodanie kolumn z oznaczeniem niespodzianki
                data['isSuprise_H'] = (
                    (data['FTR'] == 'H') & (data['Avg_H'] > data[['Avg_D', 'Avg_A']].max(axis=1))
                ).astype(int)
                data['isSuprise_D'] = (
                    (data['FTR'] == 'D') & (data['Avg_D'] > data[['Avg_H', 'Avg_A']].max(axis=1))
                ).astype(int)
                data['isSuprise_A'] = (
                    (data['FTR'] == 'A') & (data['Avg_A'] > data[['Avg_H', 'Avg_D']].max(axis=1))
                ).astype(int)

                data = data.drop(columns=['Avg_H', 'Avg_D', 'Avg_A'])
                # Zapisanie pliku do nowego folderu
                output_path = os.path.join(output_directory, f"{filename}_isSuprise.csv")
                data.to_csv(output_path, index=False)
                print(f"File processed successfully: {output_path}")
            except Exception as e:
                print(f"Error processing file {filename}: {e}")

add_isSupriseColumn()
