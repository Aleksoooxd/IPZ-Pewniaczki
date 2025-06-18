from src.scraping.footballScrap import correct_scrape_top_11
from src.scraping.transfermarktScrap import scrape_transfermarkt
from src.calculations.elo_calculator import process_all_matches_for_elo
from src.calculations.predicion import predict
def main():
    while True:
        print("1. Scrape ALL")
        print("2. Scrape top 11 leagues")
        print("3. Scrape transfermarkt")
        print("4. Calculate ELO for all matches and predict")
        print("5. Generate ALL")
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
            predict()
        elif choice == '5':
            #scrape_transfermarkt()
            correct_scrape_top_11()
            process_all_matches_for_elo()
            predict()
        else:
            break
if __name__ == "__main__":
    main()
