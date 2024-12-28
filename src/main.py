import os
import pandas as pd
path = "../Data/MatchesResultsMarged+consensus/"
output_directory = "../Data/"
files = os.listdir(path)
merged_df = pd.DataFrame()
for file in files:
    file_path = os.path.join(path+file)
    temp_df = pd.read_csv(file_path,on_bad_lines='skip')
    merged_df = pd.concat([merged_df, temp_df], ignore_index=True)
output_file = os.path.join(output_directory, "AllLeaguesTop4BooksConsensus.csv")
merged_df.to_csv(output_file, index=False)