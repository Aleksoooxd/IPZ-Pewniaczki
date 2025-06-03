import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import aliased
from flask_app.app.db import db, app, MatchStats
from flask_app.app.db import (
    FootballMatch, FutureMatch, TeamValue, MatchForm, TeamElo, League, Season, Team, PredictedFuture
)


def create_full_dataframe_for_xgboost():
    """
    Creates a comprehensive DataFrame from FootballMatch and FutureMatch tables,
    including team values, ELO ratings, form, and H2H statistics.
    This function will serve as the unified data preparation for both training and prediction.
    """
    with app.app_context():
        engine = db.engine

        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)
        HomeValue = aliased(TeamValue)
        AwayValue = aliased(TeamValue)

        form_cols = [
            'form_last_3', 'form_last_5', 'form_season', 'goals_last_3', 'goals_last_5',
            'goals_season', 'team_placement', 'h2h_wins', 'h2h_draws', 'h2h_losses',
            'h2h_matches', 'h2h_goals_for', 'h2h_goals_against', 'h2h_last_5_points'
        ]
        stats_cols = ['mean', 'std', 'shannon', 'cv', 'gini', 'hhi']

        stmt_football_match = (
            select(
                FootballMatch.match_id,
                FootballMatch.date,
                FootballMatch.result,
                League.code.label('league'),
                Season.name.label('season'),
                HomeTeam.team_id.label('home_team_id'),
                HomeTeam.name.label('home_team_name'),
                AwayTeam.team_id.label('away_team_id'),
                AwayTeam.name.label('away_team_name'),
                FootballMatch.home_elo,
                FootballMatch.away_elo,
                (FootballMatch.home_elo - FootballMatch.away_elo).label('elo_difference'),
                HomeValue.value.label('home_value'),
                AwayValue.value.label('away_value'),
                FootballMatch.consensus,
                FootballMatch.is_surprise,
                FootballMatch.fthg,
                FootballMatch.ftag
            )
            .outerjoin(League, FootballMatch.league)
            .outerjoin(Season, FootballMatch.season)
            .outerjoin(HomeTeam, FootballMatch.home_team)
            .outerjoin(AwayTeam, FootballMatch.away_team)
            .outerjoin(HomeValue, FootballMatch.home_value_ref)
            .outerjoin(AwayValue, FootballMatch.away_value_ref)
        )
        df_football = pd.read_sql_query(stmt_football_match, engine)
        df_football['is_future_match'] = False

        stmt_future_match = (
            select(
                FutureMatch.match_id,
                FutureMatch.date,
                db.null().label('result'),
                League.code.label('league'),
                Season.name.label('season'),
                HomeTeam.team_id.label('home_team_id'),
                HomeTeam.name.label('home_team_name'),
                AwayTeam.team_id.label('away_team_id'),
                AwayTeam.name.label('away_team_name'),
                db.null().label('home_elo'),
                db.null().label('away_elo'),
                db.null().label('elo_difference'),
                db.null().label('home_value'),
                db.null().label('away_value'),
                db.null().label('consensus'),
                db.null().label('is_surprise'),
                db.null().label('fthg'),
                db.null().label('ftag')
            )
            .outerjoin(League, FutureMatch.league)
            .outerjoin(Season, FutureMatch.season)
            .outerjoin(HomeTeam, FutureMatch.home_team)
            .outerjoin(AwayTeam, FutureMatch.away_team)
        )
        df_future = pd.read_sql_query(stmt_future_match, engine)
        df_future['is_future_match'] = True

        df_full = pd.concat([df_football, df_future], ignore_index=True)

        latest_team_values = db.session.execute(
            select(TeamValue.team_id, TeamValue.value)
            .order_by(TeamValue.season_id.desc())
        ).fetchall()
        latest_team_values_df = pd.DataFrame(latest_team_values, columns=['team_id', 'value']).drop_duplicates(
            subset=['team_id'], keep='first')

        df_full.loc[df_full['home_value'].isnull(), 'home_value'] = df_full.loc[
            df_full['home_value'].isnull(), 'home_team_id'].map(latest_team_values_df.set_index('team_id')['value'])
        df_full.loc[df_full['away_value'].isnull(), 'away_value'] = df_full.loc[
            df_full['away_value'].isnull(), 'away_team_id'].map(latest_team_values_df.set_index('team_id')['value'])

        latest_elos = db.session.execute(
            select(TeamElo.team_id, TeamElo.rating)
            .order_by(TeamElo.last_updated.desc())
        ).fetchall()
        latest_elos_df = pd.DataFrame(latest_elos, columns=['team_id', 'rating']).drop_duplicates(subset=['team_id'],keep='first')
        df_full.loc[df_full['home_elo'].isnull(), 'home_elo'] = df_full.loc[
            df_full['home_elo'].isnull(), 'home_team_id'].map(latest_elos_df.set_index('team_id')['rating'])
        df_full.loc[df_full['away_elo'].isnull(), 'away_elo'] = df_full.loc[
            df_full['away_elo'].isnull(), 'away_team_id'].map(latest_elos_df.set_index('team_id')['rating'])
        df_full['elo_difference'] = df_full['home_elo'] - df_full['away_elo']
        df_full['home_win_probability'] = 1.0 / (
                    1.0 + 10 ** ((df_full['away_elo'] - (df_full['home_elo'] + 100)) / 400))
        df_full['draw_probability'] = 1 - df_full['home_win_probability'] - (1.0 / (1.0 + 10 ** (
                    (df_full['home_elo'] + 100 - df_full['away_elo']) / 400)))
        df_full['away_win_probability'] = 1.0 / (1.0 + 10 ** ((df_full['home_elo'] + 100 - df_full['away_elo']) / 400))

        stmt_form = select(
            MatchForm.match_id, MatchForm.team_side,
            MatchForm.form_last_3, MatchForm.form_last_5, MatchForm.form_season,
            MatchForm.goals_last_3, MatchForm.goals_last_5, MatchForm.goals_season,
            MatchForm.team_placement,
            MatchForm.h2h_wins, MatchForm.h2h_draws, MatchForm.h2h_losses,
            MatchForm.h2h_matches, MatchForm.h2h_goals_for, MatchForm.h2h_goals_against, MatchForm.h2h_last_5_points
        )
        df_form = pd.read_sql_query(stmt_form, engine)

        stmt_stats = select(
            MatchStats.match_id, MatchStats.team_side,
            MatchStats.mean, MatchStats.std, MatchStats.shannon, MatchStats.cv, MatchStats.gini, MatchStats.hhi
        )
        df_stats = pd.read_sql_query(stmt_stats, engine)

        if not df_past_match_forms_stats.empty:
            df_past_match_forms_stats_pivot = df_past_match_forms_stats.pivot(
                index='match_id', columns='team_side'
            )
            df_past_match_forms_stats_pivot.columns = [f"{side}_{field}" for field, side in
                                                       df_past_match_forms_stats_pivot.columns]
            df_past_match_forms_stats_pivot = df_past_match_forms_stats_pivot.reset_index()

            df_full = pd.merge(df_full, df_past_match_forms_stats_pivot, on='match_id', how='left')
        else:
            for col in form_cols:
                df_full[f'home_{col}'] = np.nan
                df_full[f'away_{col}'] = np.nan
            for col in stats_cols:
                df_full[f'home_{col}'] = np.nan
                df_full[f'away_{col}'] = np.nan

        future_matches_to_update = df_full[df_full['is_future_match'] & df_full['home_form_season'].isnull()]

        for index, row in future_matches_to_update.iterrows():
            home_team_id = row['home_team_id']
            away_team_id = row['away_team_id']
            match_date = row['date']

            latest_home_past_match = db.session.query(FootballMatch).filter(
                or_(FootballMatch.home_team_id == home_team_id, FootballMatch.away_team_id == home_team_id),
                FootballMatch.date < match_date,
                FootballMatch.result.isnot(None)
            ).order_by(desc(FootballMatch.date), desc(FootballMatch.match_id)).first()

            if latest_home_past_match:
                team_side_in_last_match = 'home' if latest_home_past_match.home_team_id == home_team_id else 'away'
                home_form_latest = db.session.query(MatchForm).filter_by(match_id=latest_home_past_match.match_id,
                                                                         team_side=team_side_in_last_match).first()
                home_stats_latest = db.session.query(MatchStats).filter_by(match_id=latest_home_past_match.match_id,
                                                                           team_side=team_side_in_last_match).first()

                if home_form_latest:
                    for col in form_cols:
                        df_full.loc[index, f'home_{col}'] = getattr(home_form_latest, col)
                if home_stats_latest:
                    for col in stats_cols:
                        df_full.loc[index, f'home_{col}'] = getattr(home_stats_latest, col)

            latest_away_past_match = db.session.query(FootballMatch).filter(
                or_(FootballMatch.home_team_id == away_team_id, FootballMatch.away_team_id == away_team_id),
                FootballMatch.date < match_date,
                FootballMatch.result.isnot(None)
            ).order_by(desc(FootballMatch.date), desc(FootballMatch.match_id)).first()

            if latest_away_past_match:
                team_side_in_last_match = 'home' if latest_away_past_match.home_team_id == away_team_id else 'away'
                away_form_latest = db.session.query(MatchForm).filter_by(match_id=latest_away_past_match.match_id,
                                                                         team_side=team_side_in_last_match).first()
                away_stats_latest = db.session.query(MatchStats).filter_by(match_id=latest_away_past_match.match_id,
                                                                           team_side=team_side_in_last_match).first()

                if away_form_latest:
                    for col in form_cols:
                        df_full.loc[index, f'away_{col}'] = getattr(away_form_latest, col)
                if away_stats_latest:
                    for col in stats_cols:
                        df_full.loc[index, f'away_{col}'] = getattr(away_stats_latest, col)

            past_h2h_matches = db.session.query(FootballMatch).filter(
                and_(
                    or_(
                        and_(FootballMatch.home_team_id == home_team_id, FootballMatch.away_team_id == away_team_id),
                        and_(FootballMatch.home_team_id == away_team_id, FootballMatch.away_team_id == home_team_id)
                    ),
                    FootballMatch.date < match_date,
                    FootballMatch.result.isnot(None)
                )
            ).order_by(desc(FootballMatch.date)).all()

            h2h_home_wins = 0
            h2h_draws = 0
            h2h_losses = 0
            h2h_goals_for_home = 0
            h2h_goals_against_home = 0
            h2h_last_5_points_home_sum = 0

            for h2h_match in past_h2h_matches:
                home_points = 0
                away_points = 0
                if h2h_match.home_team_id == home_team_id:
                    if h2h_match.result == 'H':
                        home_points = 3
                    elif h2h_match.result == 'D':
                        home_points = 1
                    else:
                        home_points = 0
                    h2h_goals_for_home += h2h_match.fthg or 0
                    h2h_goals_against_home += h2h_match.ftag or 0
                else:
                    if h2h_match.result == 'A':
                        home_points = 3
                    elif h2h_match.result == 'D':
                        home_points = 1
                    else:
                        home_points = 0
                    h2h_goals_for_home += h2h_match.ftag or 0
                    h2h_goals_against_home += h2h_match.fthg or 0

                h2h_last_5_points_home_sum += home_points

            df_full.loc[index, 'home_h2h_matches'] = len(past_h2h_matches)
            df_full.loc[index, 'home_h2h_wins'] = h2h_home_wins
            df_full.loc[index, 'home_h2h_draws'] = h2h_draws
            df_full.loc[index, 'home_h2h_losses'] = len(
                past_h2h_matches) - h2h_home_wins - h2h_draws
            df_full.loc[index, 'home_h2h_goals_for'] = h2h_goals_for_home
            df_full.loc[index, 'home_h2h_goals_against'] = h2h_goals_against_home
            df_full.loc[index, 'home_h2h_last_5_points'] = h2h_last_5_points_home_sum

            df_full.loc[index, 'away_h2h_matches'] = len(past_h2h_matches)
            df_full.loc[index, 'away_h2h_wins'] = df_full.loc[index, 'home_h2h_losses']
            df_full.loc[index, 'away_h2h_draws'] = h2h_draws
            df_full.loc[index, 'away_h2h_losses'] = h2h_home_wins
            df_full.loc[index, 'away_h2h_goals_for'] = h2h_goals_against_home
            df_full.loc[index, 'away_h2h_goals_against'] = h2h_goals_for_home
            df_full.loc[
                index, 'away_h2h_last_5_points'] = h2h_last_5_points_home_sum

        df_full = df_full.drop(columns=['fthg', 'ftag', 'home_team_name', 'away_team_name'])

        return df_full


def load_training_data():
    """
    Loads and prepares data for model training from the combined DataFrame.
    """
    df_full = create_full_dataframe_for_xgboost()
    df_model = df_full[df_full['is_future_match'] == False].copy()
    df_model = df_model[df_model['result'].isin(['H', 'D', 'A'])]

    result_map = {'H': 0, 'D': 1, 'A': 2}
    df_model['target'] = df_model['result'].map(result_map)

    features_list = [
        'home_value', 'away_value',
        'home_elo', 'away_elo', 'elo_difference',
        'home_win_probability', 'draw_probability', 'away_win_probability',
        'home_form_last_3', 'away_form_last_3',
        'home_form_last_5', 'away_form_last_5',
        'home_form_season', 'away_form_season',
        'home_goals_last_3', 'away_goals_last_3',
        'home_goals_last_5', 'away_goals_last_5',
        'home_goals_season', 'away_goals_season',
        'home_team_placement', 'away_team_placement',
        'home_mean', 'away_mean',
        'home_std', 'away_std',
        'home_shannon', 'away_shannon',
        'home_cv', 'away_cv',
        'home_gini', 'away_gini',
        'home_hhi', 'away_hhi',
        'home_h2h_matches', 'away_h2h_matches',
        'home_h2h_wins', 'away_h2h_wins',
        'home_h2h_draws', 'away_h2h_draws',
        'home_h2h_losses', 'away_h2h_losses',
        'home_h2h_goals_for', 'away_h2h_goals_for',
        'home_h2h_goals_against', 'away_h2h_goals_against',
        'home_h2h_last_5_points', 'away_h2h_last_5_points'
    ]
    cols_to_drop = [
        'match_id', 'date', 'result', 'league', 'season', 'is_future_match',
        'home_team_id', 'away_team_id', 'is_surprise'
    ]

    if 'consensus' in df_model.columns:
        df_model = pd.get_dummies(df_model, columns=['consensus'], prefix='consensus', dummy_na=False)
        for col in df_model.columns:
            if col.startswith('consensus_') and col not in features_list:
                features_list.append(col)

    final_features = [f for f in features_list if f in df_model.columns]

    df_model_filtered = df_model[final_features + ['target']].dropna(subset=final_features + ['target'])

    X = df_model_filtered[final_features]
    y = df_model_filtered['target']

    return X, y, final_features, result_map


def train_model(X, y):
    """
    Trains the XGBoost model.
    """
    X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42,stratify=y)

    model = xgb.XGBClassifier(
        objective='multi:softprob',
        num_class=3,
        eval_metric='mlogloss',
        use_label_encoder=False,
        n_estimators=100,
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X_train, y_train)

    return model


def predict_and_save_future_matches(model, features, result_map):
    """
    Predicts future matches using the trained model and saves predictions to the database.
    """
    df_full = create_full_dataframe_for_xgboost()
    df_to_predict = df_full[df_full['is_future_match'] == True].copy()

    if df_to_predict.empty:
        print("No future matches to predict.")
        return pd.DataFrame()

    with app.app_context():
        engine = db.engine
        existing_predictions_df = pd.read_sql_table('predicted_future', engine)

    if not existing_predictions_df.empty:
        predicted_match_ids = existing_predictions_df['match_id'].unique()
        df_to_predict = df_to_predict[~df_to_predict['match_id'].isin(predicted_match_ids)]

    if df_to_predict.empty:
        print("All future matches already have predictions.")
        return pd.DataFrame()
    if 'consensus' in df_to_predict.columns and (
            'consensus_H' in features or 'consensus_D' in features or 'consensus_A' in features or 'consensus_No Consensus' in features):
        df_to_predict = pd.get_dummies(df_to_predict, columns=['consensus'], prefix='consensus', dummy_na=False)
        for col in [f for f in features if f.startswith('consensus_')]:
            if col not in df_to_predict.columns:
                df_to_predict[col] = 0
        current_consensus_dummy_cols = [col for col in df_to_predict.columns if col.startswith('consensus_')]
        extra_dummy_cols_to_drop = [col for col in current_consensus_dummy_cols if col not in features]
        if extra_dummy_cols_to_drop:
            df_to_predict.drop(columns=extra_dummy_cols_to_drop, inplace=True)
    elif 'consensus' in df_to_predict.columns:
        df_to_predict.drop(columns=['consensus'], inplace=True)

    X_to_predict = df_to_predict[features].dropna()

    df_to_predict_filtered = df_to_predict.loc[X_to_predict.index]

    if X_to_predict.empty:
        print("No future matches with complete data to predict after filtering missing features.")
        return pd.DataFrame()

    proba = model.predict_proba(X_to_predict)
    predicted_classes = np.argmax(proba, axis=1)
    confidences = np.max(proba, axis=1)

    label_map = {v: k for k, v in result_map.items()}
    predictions_to_save = []

    for i in range(len(predicted_classes)):
        match_id = df_to_predict_filtered.iloc[i]['match_id']
        predicted_label = label_map[predicted_classes[i]]
        confidence = float(confidences[i])

        predictions_to_save.append({
            'match_id': int(match_id),
            'predicted_result': predicted_label,
            'confidence': confidence
        })

    with app.app_context():
        with db.session.begin_nested():
            for pred_data in predictions_to_save:
                match_id = pred_data['match_id']
                predicted_label = pred_data['predicted_result']
                confidence = pred_data['confidence']

                prediction = PredictedFuture(
                    match_id=match_id,
                    predicted_result=predicted_label,
                    confidence=confidence
                )
                db.session.add(prediction)
        db.session.commit()

    return pd.DataFrame(predictions_to_save)


def main():
    X_train, y_train, features, result_map = load_training_data()

    if X_train.empty:
        print("Not enough data to train the model. Exiting.")
        return

    print("Training XGBoost model...")
    model = train_model(X_train, y_train)

    print("Predicting future matches with XGBoost...")
    df_predictions = predict_and_save_future_matches(model, features, result_map)

    if not df_predictions.empty:
        print("✅ Zapisano predykcje do bazy danych:")
        print(df_predictions.head())
    else:
        print("No new predictions were made or saved.")

if __name__ == '__main__':
    main()