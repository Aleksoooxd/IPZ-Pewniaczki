"""Interactive CLI entry point driving the data pipeline."""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.flask_app.app import create_app
from src.scraping.footballScrap import correct_scrape_top_11, compute_and_save_stats
import time

def main():
    """Run the interactive pipeline menu loop.

    Builds the Flask app, then presents a numbered menu (scrape / ELO+predict /
    predict / full run / fixtures+predict) and dispatches the chosen stage(s)
    within an app context. Entering any other value exits the loop.

    Args:
        None

    Returns:
        None:
    """
    app = create_app()

    while True:
        print("1. Scrape top 11 leagues")
        print("2. Calculate ELO for all matches and predict")
        print("3. Predict future matches (XGBoost)")
        print("4. Generate ALL")
        print("5. Download future fixtures & predict")
        choice = input("Enter your choice: ")

        if choice == '1':
            from src.flask_app.app.db import db
            with app.app_context():
                correct_scrape_top_11(db.session)
        elif choice == '2':
            from src.calculations.elo_calculator import process_all_matches_for_elo
            from src.calculations.predict_all_future import run_predictions
            from src.flask_app.app.db import db
            with app.app_context():
                process_all_matches_for_elo(db.session)
                run_predictions(db.session, db.engine)
        elif choice == '3':
            from src.calculations.predict_all_future import run_predictions
            from src.flask_app.app.db import db
            with app.app_context():
                run_predictions(db.session, db.engine)
        elif choice == '4':
            from src.calculations.elo_calculator import process_all_matches_for_elo
            from src.calculations.predict_all_future import run_predictions
            from src.flask_app.app.db import db
            with app.app_context():
                t0 = time.perf_counter()
                correct_scrape_top_11(db.session)
                scraping_time = time.perf_counter() - t0


                t1 = time.perf_counter()
                process_all_matches_for_elo(db.session)
                elo_time = time.perf_counter() - t1

                t2 = time.perf_counter()
                run_predictions(db.session, db.engine)
                pred_time = time.perf_counter() - t2

                # Pull upcoming fixtures for tracked leagues, then predict them.
                from src.scraping.footballScrap import scrape_fixtures
                scrape_fixtures(db.session)
                run_predictions(db.session, db.engine)

                compute_and_save_stats(
                    db.session,
                    scraping_time=scraping_time,
                    elo_calc_time=elo_time,
                    prediction_time=pred_time,
                )
        elif choice == '5':
            from src.calculations.predict_all_future import run_predictions
            from src.scraping.footballScrap import scrape_fixtures
            from src.flask_app.app.db import db
            with app.app_context():
                scrape_fixtures(db.session)
                run_predictions(db.session, db.engine)
        else:
            break


if __name__ == "__main__":
    main()