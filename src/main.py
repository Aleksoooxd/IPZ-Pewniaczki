selected_columns = [
    'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR',
    'HTHG', 'HTAG', 'HTR', 'Referee', 'HS', 'AS', 'HST',
    'AST', 'HC', 'AC', 'HF', 'AF', 'HY', 'AY', 'HR', 'AR',
    'Div','Season','HomeValue','AwayValue',
]
suffix = 2
bookmaker_columns = {
        2: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA'],
        4: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA', 'VCH', 'VCD', 'VCA','LBH', 'LBD', 'LBA'],
        6: ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA', 'VCH', 'VCD', 'VCA', 'LBH', 'LBD', 'LBA','PSCH', 'PSCD', 'PSCA', 'GBH', 'GBD', 'GBA'],
    }
selected_columns_dynamic = selected_columns[:] + bookmaker_columns.get(suffix, [])
print(selected_columns_dynamic)