import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sqlalchemy import select
from sqlalchemy.orm import aliased
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from tqdm import tqdm

from flask_app.app.db import db, app, MatchStats, League, Season, Team
from flask_app.app.db import (
    FootballMatch, TeamValue, MatchForm, Predicted
)

def create_match_dataframe_sql():
    with app.app_context():
        engine = db.engine


        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)
        HomeValue = aliased(TeamValue)
        AwayValue = aliased(TeamValue)

        stmt_main = (
            select(
                FootballMatch.match_id,
                FootballMatch.date,
                FootballMatch.result,
                FootballMatch.fthg.label('home_goals'),
                FootballMatch.ftag.label('away_goals'),
                League.code.label('league'),
                Season.name.label('season'),
                HomeTeam.name.label('home_team'),
                AwayTeam.name.label('away_team'),
                HomeValue.value.label('home_value'),
                AwayValue.value.label('away_value'),
                FootballMatch.home_matchday,
                FootballMatch.away_matchday,
                FootballMatch.is_surprise,
                FootballMatch.is_suprise_h.label('is_surprise_h'),
                FootballMatch.is_suprise_d.label('is_surprise_d'),
                FootballMatch.is_suprise_a.label('is_surprise_a'),
                FootballMatch.consensus,
                FootballMatch.home_elo,
                FootballMatch.away_elo,
                FootballMatch.home_elo_change,
                FootballMatch.away_elo_change,
                (FootballMatch.home_elo - FootballMatch.away_elo).label('elo_difference')
            )
            .outerjoin(League, FootballMatch.league)
            .outerjoin(Season, FootballMatch.season)
            .outerjoin(HomeTeam, FootballMatch.home_team)
            .outerjoin(AwayTeam, FootballMatch.away_team)
            .outerjoin(HomeValue, FootballMatch.home_value_ref)
            .outerjoin(AwayValue, FootballMatch.away_value_ref)
        )
        df_main = pd.read_sql_query(stmt_main, engine)

        stmt_stats = select(
            MatchStats.match_id,
            MatchStats.team_side,
            MatchStats.mean,
            MatchStats.std,
            MatchStats.shannon,
            MatchStats.cv,
            MatchStats.gini,
            MatchStats.hhi
        )
        df_stats = pd.read_sql_query(stmt_stats, engine)
        if not df_stats.empty:
            df_stats_pivot = df_stats.pivot(
                index='match_id',
                columns='team_side'
            )
            df_stats_pivot.columns = [f"{side}_{stat}" for stat, side in df_stats_pivot.columns]
            df_stats_pivot = df_stats_pivot.reset_index()
            df_main = df_main.merge(df_stats_pivot, on='match_id', how='left')

        stmt_form = select(
            MatchForm.match_id,
            MatchForm.team_side,
            MatchForm.form_last_3,
            MatchForm.form_last_5,
            MatchForm.form_season,
            MatchForm.goals_last_3,
            MatchForm.goals_last_5,
            MatchForm.goals_season,
            MatchForm.team_placement,
            MatchForm.h2h_wins,
            MatchForm.h2h_draws,
            MatchForm.h2h_losses,
            MatchForm.h2h_matches,
            MatchForm.h2h_goals_for,
            MatchForm.h2h_goals_against,
            MatchForm.h2h_last_5_points
        )
        df_form = pd.read_sql_query(stmt_form, engine)
        if not df_form.empty:
            df_form_pivot = df_form.pivot(
                index='match_id',
                columns='team_side'
            )
            df_form_pivot.columns = [f"{side}_{field}" for field, side in df_form_pivot.columns]
            df_form_pivot = df_form_pivot.reset_index()
            df_main = df_main.merge(df_form_pivot, on='match_id', how='left')

        if 'home_elo' in df_main and 'away_elo' in df_main:
            df_main['home_win_probability'] = 1.0 / (
                        1.0 + 10 ** ((df_main['away_elo'] - (df_main['home_elo'] + 100)) / 400))
            df_main['draw_probability'] = 1 - df_main['home_win_probability'] - (
                        1.0 / (1.0 + 10 ** ((df_main['home_elo'] - df_main['away_elo']) / 400)))
            df_main['away_win_probability'] = 1.0 / (
                        1.0 + 10 ** ((df_main['home_elo'] + 100 - df_main['away_elo']) / 400))

        return df_main


def drop_non_predictive_columns(df):
    """
    Drop columns that are typically not statistically significant for prediction models.
    """
    non_predictive_cols = [
        'match_id',
        'date',
        'home_team',
        'away_team',
        'home_matchday',
        'away_matchday',
        'league',
        'season',
        'home_goals',
        'away_goals',
        'home_elo_change',
        'away_elo_change',
        'is_surprise',
    ]
    cols_to_drop = [col for col in non_predictive_cols if col in df.columns]

    print(f"Dropping non-predictive columns: {cols_to_drop}")
    return df.drop(columns=cols_to_drop)


class MatchDataset(Dataset):
    def __init__(self, features, targets=None):
        self.features = torch.tensor(features, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=torch.long) if targets is not None else None

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        if self.targets is not None:
            return self.features[idx], self.targets[idx]
        return self.features[idx]


class NeuralNet(nn.Module):
    def __init__(self, input_size, num_classes):
        super(NeuralNet, self).__init__()
        self.fc1 = nn.Linear(input_size, 128)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(0.3)
        self.fc2 = nn.Linear(128, 64)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(0.3)
        self.fc3 = nn.Linear(64, num_classes)

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu1(x)
        x = self.dropout1(x)
        x = self.fc2(x)
        x = self.relu2(x)
        x = self.dropout2(x)
        x = self.fc3(x)
        return x


def train_neural_network(df_model, features_list, result_map):
    X = df_model[features_list].values
    y = df_model['target'].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)

    train_dataset = MatchDataset(X_train, y_train)
    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)

    input_size = X_train.shape[1]
    num_classes = len(result_map)
    model = NeuralNet(input_size, num_classes)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.002)

    num_epochs = 100

    for epoch in range(num_epochs):
        model.train()
        for i, (inputs, labels) in enumerate(train_loader):
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        print(f'Epoch [{epoch + 1}/{num_epochs}], Loss: {loss.item():.4f}')

    return model, scaler


def predict_future_matches_nn(model, scaler, features_list, result_map):
    with app.app_context():
        engine = db.engine

        matches_to_predict_df = create_match_dataframe_sql()

        existing_predictions_df = pd.read_sql_table('predicted', engine)
        if not existing_predictions_df.empty:
            predicted_match_ids = existing_predictions_df['match_id'].unique()
            matches_to_predict_df = matches_to_predict_df[~matches_to_predict_df['match_id'].isin(predicted_match_ids)]

        match_ids = matches_to_predict_df['match_id'].copy()

        matches_to_predict_df_processed = drop_non_predictive_columns(matches_to_predict_df.copy())

        matches_to_predict_df_processed['match_id'] = match_ids

        if 'consensus' in matches_to_predict_df_processed.columns and matches_to_predict_df_processed['consensus'].dtype == 'object':
            matches_to_predict_df_processed = pd.get_dummies(matches_to_predict_df_processed, columns=['consensus'], prefix='consensus')

        expected_consensus_dummy_cols = [col for col in features_list if col.startswith('consensus_')]

        for col in expected_consensus_dummy_cols:
            if col not in matches_to_predict_df_processed.columns:
                matches_to_predict_df_processed[col] = 0

        current_consensus_dummy_cols = [col for col in matches_to_predict_df_processed.columns if col.startswith('consensus_')]
        extra_dummy_cols_to_drop = [col for col in current_consensus_dummy_cols if col not in expected_consensus_dummy_cols]
        if extra_dummy_cols_to_drop:
            matches_to_predict_df_processed.drop(columns=extra_dummy_cols_to_drop, inplace=True)

        matches_to_predict_df_processed.dropna(subset=features_list, inplace=True)

        X_to_predict = matches_to_predict_df_processed[features_list].values
        X_to_predict_scaled = scaler.transform(X_to_predict)

        predict_dataset = MatchDataset(X_to_predict_scaled)
        predict_loader = DataLoader(predict_dataset, batch_size=64, shuffle=False)

        label_map = {0: 'H', 1: 'D', 2: 'A'}
        predictions_to_save = []

        model.eval()
        with torch.no_grad():
            original_indices = matches_to_predict_df_processed.index.tolist()

            for i, inputs in enumerate(tqdm(predict_loader, desc="Processing matches", unit="batch")):
                outputs = model(inputs)
                probabilities = torch.softmax(outputs, dim=1)
                confidences, predicted_classes = torch.max(probabilities, 1)

                batch_original_indices = original_indices[i * predict_loader.batch_size: (i + 1) * predict_loader.batch_size]
                batch_match_ids = matches_to_predict_df_processed.loc[batch_original_indices]['match_id'].tolist()


                for j in range(len(batch_match_ids)):
                    match_id = batch_match_ids[j]
                    predicted_label = label_map[predicted_classes[j].item()]
                    confidence = confidences[j].item()
                    predictions_to_save.append({
                        'match_id': match_id,
                        'predicted_result': predicted_label,
                        'confidence': confidence
                    })

        with db.session.begin_nested():
            for pred_data in tqdm(predictions_to_save, desc="Saving predictions to database", unit="prediction"):
                match_id = pred_data['match_id']
                predicted_label = pred_data['predicted_result']
                confidence = pred_data['confidence']

                existing_prediction = db.session.execute(
                    select(Predicted).filter_by(match_id=match_id)
                ).scalar_one_or_none()

                if existing_prediction:
                    existing_prediction.predicted_result = predicted_label
                    existing_prediction.confidence = confidence
                else:
                    prediction = Predicted(
                        match_id=match_id,
                        predicted_result=predicted_label,
                        confidence=confidence
                    )
                    db.session.add(prediction)
        db.session.commit()
        return pd.DataFrame(predictions_to_save)


def main():
    df = create_match_dataframe_sql()
    df = drop_non_predictive_columns(df)

    features_list = [
        'home_value', 'away_value', 'home_form_season', 'away_form_season',
        'home_elo', 'away_elo', 'elo_difference',
        'home_win_probability', 'draw_probability', 'away_win_probability',
        'home_form_last_3', 'away_form_last_3',
        'home_form_last_5', 'away_form_last_5',
        'home_goals_last_3', 'away_goals_last_3',
        'home_goals_last_5', 'away_goals_last_5',
        'home_goals_season', 'away_goals_season',
        'home_mean', 'away_mean',
        'home_std', 'away_std',
        'home_shannon', 'away_shannon',
        'home_cv', 'away_cv',
        'home_gini', 'away_gini',
        'home_hhi', 'away_hhi',
        'consensus','home_h2h_wins', 'home_h2h_draws', 'home_h2h_losses','home_h2h_matches','home_h2h_goals_for','home_h2h_goals_against','home_h2h_last_5_points'
    ]

    result_map = {'H': 0, 'D': 1, 'A': 2}
    df['target'] = df['result'].map(result_map)
    df_model = df.dropna(subset=features_list + ['target'])

    if 'consensus' in features_list and df_model['consensus'].dtype == 'object':
        df_model = pd.get_dummies(df_model, columns=['consensus'], prefix='consensus')
        features_list.remove('consensus')
        features_list.extend([col for col in df_model.columns if col.startswith('consensus_')])

    print("Training Neural Network model...")
    model, scaler = train_neural_network(df_model, features_list, result_map)

    print("Predicting future matches with Neural Network...")
    df_predictions = predict_future_matches_nn(model, scaler, features_list, result_map)

    print("✅ Zapisano predykcje do bazy danych:")
    print(df_predictions.head())


if __name__ == '__main__':
    main()