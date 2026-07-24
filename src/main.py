"""Interactive CLI entry point driving the data pipeline."""

import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.flask_app.app import create_app
from src.flask_app.app.db import db
from src.calculations.elo_calculator import process_all_matches_for_elo
from src.calculations.predict_all_future import run_predictions
from src.scraping.footballScrap import (
    compute_and_save_stats,
    correct_scrape_top_11,
    scrape_fixtures,
)


def run_full_pipeline(session=None, engine=None):
    """Run the complete data-refresh pipeline used by menu option 4.

    The caller must have an active Flask application context. Passing explicit
    session/engine values makes the function reusable from the CLI and web UI.
    """
    session = session or db.session
    engine = engine or db.engine

    t0 = time.perf_counter()
    correct_scrape_top_11(session)
    scraping_time = time.perf_counter() - t0

    t1 = time.perf_counter()
    process_all_matches_for_elo(session)
    elo_time = time.perf_counter() - t1

    t2 = time.perf_counter()
    run_predictions(session, engine)
    prediction_time = time.perf_counter() - t2

    scrape_fixtures(session)
    run_predictions(session, engine)
    compute_and_save_stats(
        session,
        scraping_time=scraping_time,
        elo_calc_time=elo_time,
        prediction_time=prediction_time,
    )

    return {
        "scraping_time": scraping_time,
        "elo_calc_time": elo_time,
        "prediction_time": prediction_time,
    }


def main():
    """Run the interactive data-pipeline menu."""
    app = create_app()

    while True:
        print("1. Scrape top 11 leagues")
        print("2. Calculate ELO for all matches and predict")
        print("3. Predict future matches (XGBoost)")
        print("4. Generate ALL")
        print("5. Download future fixtures & predict")
        choice = input("Enter your choice: ")

        with app.app_context():
            if choice == "1":
                correct_scrape_top_11(db.session)
            elif choice == "2":
                process_all_matches_for_elo(db.session)
                run_predictions(db.session, db.engine)
            elif choice == "3":
                run_predictions(db.session, db.engine)
            elif choice == "4":
                run_full_pipeline(db.session, db.engine)
            elif choice == "5":
                scrape_fixtures(db.session)
                run_predictions(db.session, db.engine)
            else:
                break


if __name__ == "__main__":
    main()