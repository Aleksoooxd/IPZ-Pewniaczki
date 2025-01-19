from file_operator import FileOperator
from footballScrap import scrape_top_11
from transfermarktScrap import scrape_transfermarkt
from helpfunctions import reset_data
def main():
    scrape_top_11()
    scrape_transfermarkt()
    file_op = FileOperator()
    #file_op.generate_seasons_with_values()
    #file_op.count_collumns()
    #file_op.generate_all_bookmakers()
    #file_op.calculate_placements()
    #file_op.add_statistics_and_consensus()
if __name__ == "__main__":
    main()