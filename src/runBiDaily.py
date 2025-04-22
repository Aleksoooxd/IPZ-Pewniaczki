from file_operator import FileOperator
from footballScrap import correct_scrape_top_11
from transfermarktScrap import scrape_transfermarkt
def main():
    scrape_transfermarkt()
    correct_scrape_top_11()
    # file_op = FileOperator()
    # file_op.generate_seasons_with_values()
    # file_op.count_collumns()
    # file_op.generate_all_bookmakers()
    # file_op.calculate_placements()
    # file_op.add_statistics_and_consensus()
    # file_op.final_merge()
if __name__ == "__main__":
    main()