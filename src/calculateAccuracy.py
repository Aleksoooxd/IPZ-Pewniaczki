import pandas as pd
from sqlalchemy import create_engine, text
from flask_app.app.db import db, app, FootballMatch, Predicted, MatchStats

def calculate_prediction_accuracy_odds_confidence():
    with app.app_context():
        football_matches = db.session.query(FootballMatch).filter(FootballMatch.result.isnot(None)).all()
        df_matches = pd.DataFrame([match.__dict__ for match in football_matches])
        df_matches = df_matches.drop(columns=['_sa_instance_state'])

        predictions = db.session.query(Predicted).all()
        df_predictions = pd.DataFrame([pred.__dict__ for pred in predictions])
        df_predictions = df_predictions.drop(columns=['_sa_instance_state'])

        match_stats = db.session.query(MatchStats).all()
        df_match_stats = pd.DataFrame([stats.__dict__ for stats in match_stats])
        df_match_stats = df_match_stats.drop(columns=['_sa_instance_state'])

        if df_matches.empty:
            print("No finished matches found in the database.")
            return
        if df_predictions.empty:
            print("No predictions found in the database.")
            return
        if df_match_stats.empty:
            print("No match statistics found in the database.")
            return

        df_merged = pd.merge(df_matches[['match_id', 'result']], df_predictions[['match_id', 'predicted_result', 'confidence']], on='match_id', how='inner')

        if df_merged.empty:
            print("No common matches between finished matches and predictions. Cannot calculate accuracy.")
            return

        total_predictions = len(df_merged)
        correct_predictions_df = df_merged[df_merged['result'] == df_merged['predicted_result']].copy()
        correct_predictions_count = len(correct_predictions_df)
        accuracy_percentage = (correct_predictions_count / total_predictions) * 100 if total_predictions > 0 else 0

        print(f"Total predictions considered: {total_predictions}")
        print(f"Correct predictions: {correct_predictions_count}")
        print(f"Accuracy: {accuracy_percentage:.2f}%")

        if correct_predictions_count > 0:
            correct_predictions_df['predicted_team_side'] = correct_predictions_df['predicted_result'].map({
                'H': 'home',
                'D': 'draw',
                'A': 'away'
            })

            df_correct_predictions_with_odds = pd.merge(
                correct_predictions_df,
                df_match_stats[['match_id', 'team_side', 'mean']],
                left_on=['match_id', 'predicted_team_side'],
                right_on=['match_id', 'team_side'],
                how='inner'
            )
            df_correct_predictions_with_odds.dropna(subset=['mean'], inplace=True)

            if not df_correct_predictions_with_odds.empty:
                average_odds_for_correct_predictions = df_correct_predictions_with_odds['mean'].mean()
                print(f"Average odds for correctly predicted outcomes: {average_odds_for_correct_predictions:.2f}")
            else:
                print("No valid odds data found for correctly predicted outcomes to calculate average.")

            average_confidence_for_correct_predictions = correct_predictions_df['confidence'].mean()
            print(f"Average confidence for correctly predicted outcomes: {average_confidence_for_correct_predictions:.2f}")

        else:
            print("No correct predictions to calculate average odds or confidence for.")

if __name__ == "__main__":
    calculate_prediction_accuracy_odds_confidence()
# Total predictions considered: 71883
# Correct predictions: 61073
# Accuracy: 84.96%
# Average odds for correctly predicted outcomes: 1.86
# Average confidence for correctly predicted outcomes: 0.86
# 30 dni 1 zaklad dziennie o wartosci np 10 zl
# 30* 84.96% ~= 25
# 25 * 10zl * 1.86 ~= 465 zl
# 10zl * 30 dni = 300 zl
# 465 - 300 = 165 zl zarobku :O zakladajac ze mamy kursy bukmacherskie :(