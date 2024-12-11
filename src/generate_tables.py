from file_operator import FileOperator

#Top6 Bookmacherow
selected_columns = [
    'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR',
    'HTHG', 'HTAG', 'HTR', 'Referee', 'HS', 'AS', 'HST',
    'AST', 'HC', 'AC', 'HF', 'AF', 'HY', 'AY', 'HR', 'AR',
    'Div',
    'B365H', 'B365D', 'B365A',  # Bookmaker B365 (Home, Draw, Away)
    'BWH', 'BWD', 'BWA',  # Bookmaker BWH (Home, Draw, Away)
    #'VCH', 'VCD', 'VCA',  # Bookmaker VCH (Home, Draw, Away)
   # 'LBH', 'LBD', 'LBA',  # Bookmaker LBH (Home, Draw, Away)
  #  'PSCH', 'PSCD', 'PSCA',  # Bookmaker PSCH (Home, Draw, Away)
   # 'GBH', 'GBD', 'GBA'   # Bookmaker GBH (Home, Draw, Away)
]

def generate_top_bookmakers(file_operator, suffix):
    """Generates files with a dynamic suffix."""
    dynamic_suffix = f"Top{suffix}Bookmakers"
    for league, country in zip(file_operator.leagues, file_operator.countries):
        file_operator.merge_files(
            league_name=league,
            country_name=country,
            selected_columns=selected_columns,
            output_suffix=dynamic_suffix
        )

if __name__ == "__main__":
    suffix = input("Enter the suffix for TopBookmakers files: ")
    file_op = FileOperator()
    generate_top_bookmakers(file_op, suffix)
