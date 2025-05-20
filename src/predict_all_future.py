import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split

from flask_app.app.db import db, app
from flask_app.app.db import (
    FootballMatch, FutureMatch, TeamValue, MatchForm, Predicted
)


def load_training_data():
    with app.app_context():
        engine = db.engine

        df = pd.read_sql_table('football_match', engine)
        df = df[df['result'].isin(['H', 'D', 'A'])]
        df = df.dropna(subset=['home_value_id', 'away_value_id'])

        team_values = pd.read_sql_table('team_value', engine)
        df = df.merge(team_values.rename(columns={'value_id': 'home_value_id', 'value': 'home_value'}), on='home_value_id')
        df = df.merge(team_values.rename(columns={'value_id': 'away_value_id', 'value': 'away_value'}), on='away_value_id')

        form = pd.read_sql_table('match_form', engine)
        form_home = form[form['team_side'] == 'home'].rename(columns={'form_season': 'home_form_season'})
        form_away = form[form['team_side'] == 'away'].rename(columns={'form_season': 'away_form_season'})
        df = df.merge(form_home[['match_id', 'home_form_season']], on='match_id', how='left')
        df = df.merge(form_away[['match_id', 'away_form_season']], on='match_id', how='left')

        result_map = {'H': 0, 'D': 1, 'A': 2}
        df['target'] = df['result'].map(result_map)

        df_model = df[['home_value', 'away_value', 'home_form_season', 'away_form_season', 'target']].dropna()
        return df_model, result_map


def train_model(df_model):
    X = df_model.drop('target', axis=1)
    y = df_model['target']

    X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(objective='multi:softprob', num_class=3, eval_metric='mlogloss')
    model.fit(X_train, y_train)

    return model, X.columns.tolist()


def predict_future_matches(model, features, result_map):
    with app.app_context():
        engine = db.engine

        future_matches = pd.read_sql_table('future_match', engine)
        team_values = pd.read_sql_table('team_value', engine)
        form = pd.read_sql_table('match_form', engine)

        label_map = {0: 'H', 1: 'D', 2: 'A'}
        predictions = []

        for _, match in future_matches.iterrows():
            home_team_id = match['home_team_id']
            away_team_id = match['away_team_id']
            season_id = match['season_id']
            match_id = match['match_id']


            home_value = team_values[
                (team_values['team_id'] == home_team_id) & (team_values['season_id'] == season_id)
            ]['value']
            away_value = team_values[
                (team_values['team_id'] == away_team_id) & (team_values['season_id'] == season_id)
            ]['value']

            if home_value.empty or away_value.empty:
                continue


            home_form = form[
                (form['team_side'] == 'home') & (form['match_id'] == match_id)
            ]['form_season']
            away_form = form[
                (form['team_side'] == 'away') & (form['match_id'] == match_id)
            ]['form_season']

            if home_form.empty or away_form.empty:
                continue

            X_input = pd.DataFrame([{
                'home_value': home_value.values[0],
                'away_value': away_value.values[0],
                'home_form_season': home_form.values[0],
                'away_form_season': away_form.values[0]
            }])

            if X_input.isnull().any(axis=1).values[0]:
                continue

            proba = model.predict_proba(X_input)[0]
            predicted_class = int(np.argmax(proba))
            predicted_label = label_map[predicted_class]
            confidence = float(proba[predicted_class])


            prediction = Predicted(
                match_id=match_id,
                predicted_result=predicted_label,
                confidence=confidence
            )
            db.session.add(prediction)

            predictions.append({
                'match_id': match_id,
                'predicted_result': predicted_label,
                'confidence': confidence
            })

        db.session.commit()
        return pd.DataFrame(predictions)


def main():
    df_model, result_map = load_training_data()
    model, features = train_model(df_model)
    df_predictions = predict_future_matches(model, features, result_map)

    print("✅ Zapisano predykcje do bazy danych:")
    print(df_predictions.head())


if __name__ == '__main__':
    main()
