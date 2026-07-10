from src.scraping.footballScrap import correct_scrape_top_11
from src.calculations.elo_calculator import process_all_matches_for_elo
from src.calculations.prediction import predict
def main():
    while True:
        print("1. Scrape top 11 leagues")
        print("2. Calculate ELO for all matches and predict")
        print("3. Generate ALL")
        choice = input("Enter your choice: ")
        if choice == '1':
            correct_scrape_top_11()
        elif choice == '2':
            process_all_matches_for_elo()
            predict()
        elif choice == '3':
            correct_scrape_top_11()
            process_all_matches_for_elo()
            predict()
        else:
            break
if __name__ == "__main__":
    main()
