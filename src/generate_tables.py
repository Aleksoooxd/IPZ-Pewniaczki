from file_operator import FileOperator

#Top6 Bookmacherow
selected_columns = [
    'Div','Season','Date', 'HomeTeam', 'AwayTeam', 'FTR',
    'HomeValue','AwayValue'
]
additional_columns = ['HT','AT','PSH','PSD','PSA','PSCH', 'PSCD', 'PSCA','B365CH','B365CD','B365CA']

def generate_top_bookmakers(file_operator, suffix):
    """Generates files with a dynamic suffix."""
    dynamic_suffix = f"Top{suffix}Bookmakers"
    bookmaker_columns = {
        2: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA'],
        4: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA','WHH','WHD','WHA','IWH','IWD','IWA'],
        6: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA','WHH','WHD','WHA','IWH','IWD','IWA','VCH','VCD','VCA','LBH','LBD','LBA'],
    }
    selected_columns_dynamic = additional_columns[::]+ selected_columns[::] + bookmaker_columns.get(suffix, [])
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
