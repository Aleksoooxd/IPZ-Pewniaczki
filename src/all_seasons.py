import os
import pandas as pd
from file_operator import FileOperator

# Funkcja generująca allSeasons dla wszystkich lig
def generate_all_seasons(file_operator):
    for league, country in zip(file_operator.leagues, file_operator.countries):
        file_operator.merge_files(
            league_name=league,
            country_name=country,
            selected_columns=None,
            output_suffix="allSeasons"
        )

if __name__ == "__main__":
    file_op = FileOperator()
    generate_all_seasons(file_op)
