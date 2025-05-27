from footballScrap import correct_scrape_top_11
from transfermarktScrap import scrape_transfermarkt
from elo_calculator import process_all_matches_for_elo  # Add this import
def main():
    while True:
        print("1. Scrape ALL")
        print("2. Scrape top 11 leagues")
        print("3. Scrape transfermarkt")
        print("4. Calculate ELO for all matches")
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
            process_all_matches_for_elo()
        elif choice == '9':
            pass
        else:
            break
if __name__ == "__main__":
    main()
