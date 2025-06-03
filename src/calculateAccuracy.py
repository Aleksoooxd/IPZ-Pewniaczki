import pandas as pd
from sqlalchemy import create_engine, text
from flask_app.app.db import db, app, FootballMatch, Predicted # Assuming db and app are correctly imported from your Flask app

def calculate_prediction_accuracy():
    with app.app_context():
        football_matches = db.session.query(FootballMatch).filter(FootballMatch.result.isnot(None)).all()
        df_matches = pd.DataFrame([match.__dict__ for match in football_matches])
        df_matches = df_matches.drop(columns=['_sa_instance_state']) # Drop SQLAlchemy internal state column

        predictions = db.session.query(Predicted).all()
        df_predictions = pd.DataFrame([pred.__dict__ for pred in predictions])
        df_predictions = df_predictions.drop(columns=['_sa_instance_state']) # Drop SQLAlchemy internal state column

        if df_matches.empty:
            print("No finished matches found in the database.")
            return
        if df_predictions.empty:
            print("No predictions found in the database.")
            return

        df_merged = pd.merge(df_matches[['match_id', 'result']], df_predictions[['match_id', 'predicted_result']], on='match_id', how='inner')

        if df_merged.empty:
            print("No common matches between finished matches and predictions. Cannot calculate accuracy.")
            return

        total_predictions = len(df_merged)
        correct_predictions = (df_merged['result'] == df_merged['predicted_result']).sum()
        accuracy_percentage = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0

        print(f"Total predictions considered: {total_predictions}")
        print(f"Correct predictions: {correct_predictions}")
        print(f"Accuracy: {accuracy_percentage:.2f}%")

if __name__ == "__main__":
    calculate_prediction_accuracy()