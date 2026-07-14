from src.flask_app.app import create_app
from src.scraping.footballScrap import correct_scrape_top_11, compute_and_save_stats
import time

def main():
    app = create_app()

    while True:
        print("1. Scrape top 11 leagues")
        print("2. Calculate ELO for all matches and predict")
        print("3. Predict future matches (XGBoost)")
        print("4. Generate ALL")
        choice = input("Enter your choice: ")

        if choice == '1':
            from src.flask_app.app.db import db
            with app.app_context():
                correct_scrape_top_11(db.session)
        elif choice == '2':
            from src.calculations.elo_calculator import process_all_matches_for_elo
            from src.calculations.prediction import predict
            from src.flask_app.app.db import db
            with app.app_context():
                process_all_matches_for_elo(db.session)
                predict(db.session, db.engine)
        elif choice == '3':
            from src.calculations.predict_all_future import main as predict_future_main
            from src.flask_app.app.db import db
            with app.app_context():
                predict_future_main(db.session, db.engine)
        elif choice == '4':
            from src.calculations.elo_calculator import process_all_matches_for_elo
            from src.calculations.prediction import predict
            from src.flask_app.app.db import db
            with app.app_context():
                t0 = time.perf_counter()
                correct_scrape_top_11(db.session)
                scraping_time = time.perf_counter() - t0


                t1 = time.perf_counter()
                process_all_matches_for_elo(db.session)
                elo_time = time.perf_counter() - t1

                t2 = time.perf_counter()
                predict(db.session, db.engine)
                pred_time = time.perf_counter() - t2

                compute_and_save_stats(
                    db.session,
                    scraping_time=scraping_time,
                    elo_calc_time=elo_time,
                    prediction_time=pred_time,
                )
        else:
            break


if __name__ == "__main__":
    main()