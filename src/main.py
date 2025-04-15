from file_operator import FileOperator
from footballScrap import correct_scrape_top_11
from transfermarktScrap import scrape_transfermarkt
from helpfunctions import reset_data,merge_all_seasons
def main():
    while True:
        print("1. Scrape ALL")
        print("2. Scrape top 11 leagues")
        print("3. Scrape transfermarkt")
        print("4. Generate all seasons")
        print("5. Generate top bookmakers")
        print("6. Calculate consensus")
        print("7. Generate all in order")
        print("8. Calculate place in table")
        print("9. Do testowania roznych rzeczy")
        print("0. Quit")
        choice = input("Enter your choice: ")
        if choice == '1':
            scrape_transfermarkt()
            correct_scrape_top_11()
        elif choice == '2':
            correct_scrape_top_11()
        elif choice == '3':
            scrape_transfermarkt()
        elif choice == '4':
            file_op = FileOperator()
            file_op.generate_seasons_with_values()
            file_op.count_collumns()
        elif choice == '5':
            file_op = FileOperator()
            file_op.generate_all_bookmakers()
        elif choice == '6':
            file_op = FileOperator()
            file_op.add_statistics_and_consensus()
        elif choice == '7':
            reset_data()
            correct_scrape_top_11()
            scrape_transfermarkt()
            file_op = FileOperator()
            file_op.generate_seasons_with_values()
            file_op.count_collumns()
            file_op.generate_all_bookmakers()
            file_op.calculate_placements()
            file_op.add_statistics_and_consensus()
        elif choice == '8':
            file_op = FileOperator()
            file_op.calculate_placements()
        elif choice == '9':
            # Do testowania roznych rzeczy
            merge_all_seasons()
        else:
            break
if __name__ == "__main__":
    main()
