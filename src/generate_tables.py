from file_operator import FileOperator

#Top6 Bookmacherow
selected_columns = [
    'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR',
    'HTHG', 'HTAG', 'HTR', 'Referee', 'HS', 'AS', 'HST',
    'AST', 'HC', 'AC', 'HF', 'AF', 'HY', 'AY', 'HR', 'AR',
    'Div','Season','HomeValue','AwayValue',
]

def generate_top_bookmakers(file_operator, suffix):
    """Generates files with a dynamic suffix."""
    dynamic_suffix = f"Top{suffix}Bookmakers"
    bookmaker_columns = {
        2: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA'],
        4: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA', 'VCH', 'VCD', 'VCA','LBH', 'LBD', 'LBA'],
        6: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA', 'VCH', 'VCD', 'VCA', 'LBH', 'LBD', 'LBA','PSCH', 'PSCD', 'PSCA', 'GBH', 'GBD', 'GBA'],
    }
    selected_columns_dynamic = selected_columns[:] + bookmaker_columns.get(suffix, [])
    for league, country in zip(file_operator.leagues, file_operator.countries):
        file_operator.merge_files(
            league_name=league,
            country_name=country,
            selected_columns=selected_columns_dynamic,
            output_suffix=dynamic_suffix,
            use_book=True
        )

if __name__ == "__main__":
    suffixes = [2,4,6]
    file_op = FileOperator()
    for suffix in suffixes:
        generate_top_bookmakers(file_op, suffix)
