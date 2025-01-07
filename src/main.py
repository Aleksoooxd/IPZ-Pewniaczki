from file_operator import FileOperator
from generate_tables import generate_top_bookmakers
from all_seasons import generate_all_seasons
from footballScrap import scrape_top_11
from transfermarktScrap import scrape_transfermarkt
from normalizenames import normalize_names
from Statistica_calculation import statistica_calc
from SurpriseCounter import surprise_counter
from CalcAndAddKonsensus import calculate_cons
from time import sleep
def main():
    while True:
        print("1. Scrape ALL")
        print("2. Scrape top 11 leagues")
        print("3. Scrape transfermarkt")
        print("4. Generate all seasons")
        print("5. Normalize names")
        print("6. Generate top bookmakers")
        print("7. Statistics calculation")
        print("8. Surprises")
        print("9. Calculate consensus")
        print("10. Generate all in order")
        print("0. Generate all in order")
        choice = input("Enter your choice: ")
        if choice == '1':
            scrape_top_11()
            scrape_transfermarkt()
        elif choice == '2':
            scrape_top_11()
        elif choice == '3':
            scrape_transfermarkt()
        elif choice == '4':
            file_op = FileOperator()
            generate_all_seasons(file_op)
            file_op.count_collumns()
        elif choice == '5':
            file_op = FileOperator()
            generate_all_seasons(file_op)
            normalize_names()
            generate_all_seasons(file_op)
            suffixes = [2, 4, 6]
            for suffix in suffixes:
                generate_top_bookmakers(file_op, suffix)
        elif choice == '6':
            file_op = FileOperator()
            suffixes = [2,4,6]
            for suffix in suffixes:
                generate_top_bookmakers(file_op, suffix)
        elif choice == '7':
            statistica_calc()
        elif choice == '8':
            surprise_counter()
        elif choice == '9':
            calculate_cons()
        elif choice == '10':
            scrape_top_11()
            scrape_transfermarkt()
            file_op = FileOperator()
            generate_all_seasons(file_op)
            normalize_names()
            sleep(2)
            file_op2 = FileOperator()
            generate_all_seasons(file_op2)
            suffixes = [2, 4, 6]
            for suffix in suffixes:
                generate_top_bookmakers(file_op2, suffix)
            file_op2.count_collumns()
            statistica_calc()
            surprise_counter()
            calculate_cons()
        else:
            break

if __name__ == "__main__":
    main()
