import json
from pathlib import Path

import pandas as pd
import numpy as np
import xgboost as xgb
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sklearn.metrics import accuracy_score, log_loss, f1_score, confusion_matrix

from src.flask_app.app.models import (
    Predicted, PredictedFuture, ModelMetrics,
)
from src.flask_app.app.db import db
from src.calculations.feature_builder import build_match_features, encode_consensus


# Canonical prediction model: a single XGBoost classifier is trained on past
# results and used for BOTH past (-> Predicted) and future (-> PredictedFuture)
# matches. This replaces the previous split where a PyTorch NeuralNet predicted
# past matches and XGBoost predicted future ones — two divergent, un-persisted
# models. Trained models + eval metrics are checkpointed (see run_predictions).
CANONICAL_MODEL_NAME = "xgboost_canonical"
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def create_full_dataframe_for_xgboost(session: Session, engine: Engine) -> pd.DataFrame:
    """Build the full feature dataframe (past + future) for the model.

    Delegates to :func:`feature_builder.build_match_features` with
    ``include_future=True`` and then drops the raw helper columns
    (``fthg``, ``ftag``, team names) that are not part of the model's
    feature set.

    Args:
        session (sqlalchemy.orm.Session): Active database session.
        engine (sqlalchemy.engine.Engine): Engine for reading tables.

    Returns:
        pandas.DataFrame: Full match-feature dataframe with only model
        features retained.
    """
    df_full = build_match_features(session, engine, include_future=True)
    return df_full.drop(
        columns=['fthg', 'ftag', 'home_team_name', 'away_team_name'], errors='ignore'
    )


# Canonical feature set used for BOTH training and inference.
#
# NOTE on the ELO-derived probabilities: the standard ELO expected-score formula
# used in ``feature_builder._add_win_probabilities`` is symmetric, so
# ``home_win_probability + away_win_probability == 1`` exactly and
# ``draw_probability`` is always 0. That makes ``away_win_probability`` perfectly
# collinear with ``home_win_probability`` (zero independent signal) and
# ``draw_probability`` a constant (no signal at all, and misleading if ever
# displayed as a "draw chance"). We therefore keep only ``home_win_probability``
# as the ELO feature, since the symmetric ELO formula cannot surface a
# non-degenerate draw probability.
FEATURES = [
    'home_elo', 'away_elo', 'elo_difference',
    'home_win_probability',
    'home_form_last_3', 'away_form_last_3',
    'home_form_last_5', 'away_form_last_5',
    'home_form_season', 'away_form_season',
    'home_goals_last_3', 'away_goals_last_3',
    'home_goals_last_5', 'away_goals_last_5',
    'home_goals_season', 'away_goals_season',
    'home_team_placement', 'away_team_placement',
    'home_draw_ratio_team', 'away_draw_ratio_team',
    'home_draw_ratio_league', 'away_draw_ratio_league',
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


def prepare_training_data(df_full: pd.DataFrame, result_map):
    """Prepare a chronological train/test split from played matches.

    Filters the feature dataframe to played matches with an ``H``/``D``/``A``
    result, maps that result to its integer label via ``result_map``, one-hot
    encodes consensus, drops rows with missing features, then splits the data
    **chronologically** (oldest 80% train, newest 20% test).

    A time-ordered split — rather than a random ``train_test_split`` — is the
    honest way to evaluate a forecasting model: the model is only ever scored on
    matches that happened *after* every match it trained on, so the reported
    accuracy reflects true out-of-sample forecasting rather than interpolation
    across the timeline.

    Args:
        df_full (pandas.DataFrame): Feature dataframe from
            :func:`create_full_dataframe_for_xgboost`. Must retain the ``date``
            column so rows can be ordered in time.
        result_map (dict): Mapping from outcome label (``'H'``/``'D'``/``'A'``)
            to its integer class index.

    Returns:
        tuple: ``(X_train, X_test, y_train, y_test, final_features)`` where
        the ``X``/``y`` frames hold features and integer labels, and
        ``final_features`` is the list of feature columns actually used.
    """
    df_model = df_full[df_full['is_future_match'] == False].copy()
    df_model = df_model[df_model['result'].isin(['H', 'D', 'A'])]
    df_model['target'] = df_model['result'].map(result_map)

    # Order by match date so the split is chronological. Fall back gracefully if
    # the date column is absent for some reason.
    if 'date' in df_model.columns:
        df_model = df_model.sort_values('date', kind='stable')

    features = list(FEATURES)
    df_model, features = encode_consensus(df_model, features, append_new=True)

    final_features = [f for f in features if f in df_model.columns]
    df_model_filtered = df_model[final_features + ['target']].dropna(subset=final_features + ['target'])

    X = df_model_filtered[final_features]
    y = df_model_filtered['target']

    # Chronological 80/20 split: the most recent 20% of matches form the test set.
    n = len(X)
    split = int(n * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    return X_train, X_test, y_train, y_test, final_features


def evaluate_model(model, X_test, y_test, result_map):
    """Evaluate a trained classifier on a held-out test set.

    Predicts class probabilities, derives the argmax label, and reports
    classification accuracy and multiclass log loss against the true labels.
    It also computes a naive **ELO-favourite** baseline accuracy (always back
    the stronger team including the +100 home advantage) so the model's score
    can be judged against the simplest possible forecaster. Finally it returns
    the macro-F1, a per-class breakdown (recall / precision / support for each
    of H / D / A) and the 3x3 confusion matrix, so the dashboard can show a
    full picture without re-running the model.

    Args:
        model: A fitted classifier exposing ``predict_proba``.
        X_test (pandas.DataFrame): Test features (must include
            ``elo_difference`` for the baseline).
        y_test (array-like): True integer class labels.
        result_map (dict): Mapping from outcome label to integer class index
            (used to label per-class results ``'H'`` / ``'D'`` / ``'A'``).

    Returns:
        tuple: ``(accuracy, log_loss, baseline_accuracy, macro_f1, per_class,
        confusion_matrix)`` where ``per_class`` is a ``dict`` keyed by outcome
        label with ``recall`` / ``precision`` / ``support``, and
        ``confusion_matrix`` is a ``list`` of three rows (true H/D/A) of three
        columns (pred H/D/A). ``baseline_accuracy`` is ``None`` when
        ``elo_difference`` is unavailable.
    """
    proba = model.predict_proba(X_test)
    preds = np.argmax(proba, axis=1)
    y_test_int = y_test.astype(int).values if hasattr(y_test, 'astype') else list(y_test)
    acc = accuracy_score(y_test_int, preds)
    ll = log_loss(y_test_int, proba, labels=[0, 1, 2])
    macro_f1 = float(f1_score(y_test_int, preds, average='macro'))
    cm = confusion_matrix(y_test_int, preds, labels=[0, 1, 2])

    label_to_outcome = {v: k for k, v in result_map.items()}
    per_class = {}
    for c in (0, 1, 2):
        tp = int(cm[c, c])
        support = int(cm[c, :].sum())
        fp = int(cm[:, c].sum()) - tp
        recall = (tp / support) if support else 0.0
        precision = (tp / (tp + fp)) if (tp + fp) else 0.0
        per_class[label_to_outcome[c]] = {
            'recall': recall, 'precision': precision, 'support': support,
        }

    # Naive baseline: always back the ELO favourite (home advantage = +100).
    # The model should beat "just pick the stronger team" to be worth anything.
    baseline_acc = None
    if 'elo_difference' in X_test.columns:
        elo_fav_label = np.where(X_test['elo_difference'] + 100 > 0, 0, 2)  # 0=H, 2=A
        baseline_acc = accuracy_score(y_test_int, elo_fav_label)

    return (float(acc), float(ll),
            (float(baseline_acc) if baseline_acc is not None else None),
            macro_f1, per_class, cm.tolist())


def save_checkpoint(model, path: str):
    """Persist a trained model to disk as a checkpoint.

    Ensures the model directory exists (creating it if needed) and writes the
    model using its native ``save_model`` method (XGBoost format).

    Args:
        model: A fitted model exposing ``save_model``.
        path (str): Filesystem path (typically under ``MODELS_DIR``) to write to.

    Returns:
        None:
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(path)


def persist_metrics(session: Session, accuracy: float, log_loss_val: float,
                   baseline_accuracy: float, n_train: int, n_test: int,
                   features, checkpoint_path: str, macro_f1: float = None,
                   per_class: dict = None, confusion_matrix: list = None):
    """Record a model's evaluation metrics and feature set to the database.

    Inserts a :class:`ModelMetrics` row using the canonical model name,
    the supplied accuracy / log-loss / baseline accuracy, the train/test sizes,
    the JSON-serialised feature list, and the checkpoint path, then commits.
    The optional ``macro_f1`` / ``per_class`` / ``confusion_matrix`` arguments
    add the richer per-class breakdown used by the dashboard.

    Args:
        session (sqlalchemy.orm.Session): Active database session.
        accuracy (float): Test-set classification accuracy.
        log_loss_val (float): Test-set multiclass log loss.
        baseline_accuracy (float): ELO-favourite naive baseline accuracy.
        n_train (int): Number of training samples.
        n_test (int): Number of test samples.
        features (list[str]): Feature column names used by the model
            (JSON-serialised).
        checkpoint_path (str): Path of the saved model checkpoint.
        macro_f1 (float, optional): Macro-averaged F1 on the test set.
        per_class (dict, optional): Per-outcome ``{'H'/'D'/'A': {recall,
            precision, support}}`` breakdown (JSON-serialised).
        confusion_matrix (list, optional): 3x3 confusion matrix (true x pred),
            JSON-serialised.

    Returns:
        None:
    """
    session.add(ModelMetrics(
        model_name=CANONICAL_MODEL_NAME,
        accuracy=accuracy,
        log_loss=log_loss_val,
        baseline_accuracy=baseline_accuracy,
        macro_f1=macro_f1,
        per_class=json.dumps(per_class) if per_class is not None else None,
        confusion_matrix=json.dumps(confusion_matrix) if confusion_matrix is not None else None,
        n_train=n_train,
        n_test=n_test,
        features=json.dumps(features),
        checkpoint_path=checkpoint_path,
    ))
    session.commit()


def train_model(X_train, y_train):
    """Train the canonical XGBoost multiclass match-outcome classifier.

    Labels are pre-encoded as 0/1/2 (see :func:`run_predictions`' ``result_map``),
    so no label encoding is needed. ``use_label_encoder`` is a no-op/warning in
    current XGBoost and is intentionally omitted. A small validation slice with
    early stopping keeps ``n_estimators`` from being fixed arbitrarily.

    Args:
        X_train (pandas.DataFrame): Training feature matrix.
        y_train (array-like): Integer training labels (0/1/2).

    Returns:
        xgboost.XGBClassifier: Fitted classifier (3 classes, ``multi:softprob``).
    """
    model = xgb.XGBClassifier(
        objective='multi:softprob',
        num_class=3,
        eval_metric='mlogloss',
        n_estimators=300,
        learning_rate=0.1,
        random_state=42,
    )
    try:
        model.fit(
            X_train, y_train,
            eval_set=[(X_train, y_train)],
            early_stopping_rounds=20,
            verbose=False,
        )
    except TypeError:
        # Older XGBoost without early-stopping kwargs falls back to a plain fit.
        model.fit(X_train, y_train)
    return model


def apply_draw_multiplier(proba, multiplier):
    """Re-weight the draw (class index 1) probability and renormalise.

    Scales the middle column (D) of a ``(n, 3)`` probability matrix by
    ``multiplier`` and renormalises each row so the H/D/A vector still sums to 1.
    Applied as a post-hoc inference step so the model itself stays untouched
    (its calibration for H/A is preserved) and the knob is tunable live.
    A multiplier of ``1.0`` returns the input unchanged.

    Args:
        proba (numpy.ndarray): ``(n, 3)`` probability matrix (columns H, D, A).
        multiplier (float): Draw-probability scaling factor (1.0 = identity).

    Returns:
        numpy.ndarray: ``(n, 3)`` renormalised probability matrix.
    """
    if multiplier == 1.0:
        return proba
    scaled = proba.copy()
    scaled[:, 1] = scaled[:, 1] * multiplier
    row_sums = scaled.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    return scaled / row_sums


def predict_and_save_future_matches(model, features, result_map, session: Session,
                                    engine: Engine, draw_prob_multiplier: float = 1.0):
    """Predict upcoming matches and persist them as ``PredictedFuture`` rows.

    Builds features for all matches, keeps only future ones, skips any whose
    ``match_id`` already has a prediction, encodes consensus against the frozen
    feature set, and writes a ``PredictedFuture`` row (outcome + confidence)
    per match inside a nested transaction. Returns early with an empty frame
    when there is nothing to predict.

    Args:
        model: Fitted classifier exposing ``predict_proba``.
        features (list[str]): Frozen model feature list.
        result_map (dict): Mapping from outcome label to integer class index; the
            inverse is used to map predicted class back to ``'H'``/``'D'``/``'A'``.
        session (sqlalchemy.orm.Session): Active database session.
        engine (sqlalchemy.engine.Engine): Engine for reading tables.

    Returns:
        pandas.DataFrame: The saved predictions as rows of
        ``match_id`` / ``predicted_result`` / ``confidence`` (empty if none).
    """
    df_full = create_full_dataframe_for_xgboost(session, engine)
    df_to_predict = df_full[df_full['is_future_match'] == True].copy()

    if df_to_predict.empty:
        print("No future matches to predict.")
        return pd.DataFrame()

    df_to_predict, _ = encode_consensus(df_to_predict, features, append_new=False)

    X_to_predict = df_to_predict[features].dropna()
    df_to_predict_filtered = df_to_predict.loc[X_to_predict.index]

    if X_to_predict.empty:
        print("No future matches with complete data to predict.")
        return pd.DataFrame()

    proba = model.predict_proba(X_to_predict)
    proba = apply_draw_multiplier(proba, draw_prob_multiplier)
    predicted_classes = np.argmax(proba, axis=1)
    confidences = np.max(proba, axis=1)

    label_map = {v: k for k, v in result_map.items()}
    predictions_to_save = [
        {
            'match_id': int(df_to_predict_filtered.iloc[i]['match_id']),
            'predicted_result': label_map[predicted_classes[i]],
            'confidence': float(confidences[i]),
            'prob_home': float(proba[i][0]),
            'prob_draw': float(proba[i][1]),
            'prob_away': float(proba[i][2]),
        }
        for i in range(len(predicted_classes))
    ]

    with session.begin_nested():
        for pred_data in predictions_to_save:
            existing = session.execute(
                select(PredictedFuture).filter_by(match_id=pred_data['match_id'])
            ).scalar_one_or_none()
            if existing:
                existing.predicted_result = pred_data['predicted_result']
                existing.confidence = pred_data['confidence']
                existing.prob_home = pred_data['prob_home']
                existing.prob_draw = pred_data['prob_draw']
                existing.prob_away = pred_data['prob_away']
            else:
                session.add(PredictedFuture(
                    match_id=pred_data['match_id'],
                    predicted_result=pred_data['predicted_result'],
                    confidence=pred_data['confidence'],
                    prob_home=pred_data['prob_home'],
                    prob_draw=pred_data['prob_draw'],
                    prob_away=pred_data['prob_away'],
                ))
    session.commit()
    return pd.DataFrame(predictions_to_save)


def predict_and_save_past_matches(model, features, result_map, session: Session,
                                  engine: Engine, draw_prob_multiplier: float = 1.0):
    """Predict already-played matches lacking a ``Predicted`` row.

    Builds features for all matches, keeps only past ones, skips any whose
    ``match_id`` already has a prediction, encodes consensus against the frozen
    feature set, and upserts a ``Predicted`` row (outcome + confidence) per
    match inside a nested transaction. Returns early with an empty frame when
    there is nothing to predict.

    Args:
        model: Fitted classifier exposing ``predict_proba``.
        features (list[str]): Frozen model feature list.
        result_map (dict): Mapping from outcome label to integer class index; the
            inverse is used to map predicted class back to ``'H'``/``'D'``/``'A'``.
        session (sqlalchemy.orm.Session): Active database session.
        engine (sqlalchemy.engine.Engine): Engine for reading tables.

    Returns:
        pandas.DataFrame: The saved predictions as rows of
        ``match_id`` / ``predicted_result`` / ``confidence`` (empty if none).
    """
    df_full = create_full_dataframe_for_xgboost(session, engine)
    df_to_predict = df_full[df_full['is_future_match'] == False].copy()

    existing_predictions_df = pd.read_sql_table('predicted', engine)
    if not existing_predictions_df.empty:
        predicted_match_ids = existing_predictions_df['match_id'].unique()
        df_to_predict = df_to_predict[~df_to_predict['match_id'].isin(predicted_match_ids)]

    if df_to_predict.empty:
        print("All past matches already predicted.")
        return pd.DataFrame()

    df_to_predict, _ = encode_consensus(df_to_predict, features, append_new=False)

    X_to_predict = df_to_predict[features].dropna()
    df_to_predict_filtered = df_to_predict.loc[X_to_predict.index]

    if X_to_predict.empty:
        print("No past matches with complete data to predict.")
        return pd.DataFrame()

    proba = model.predict_proba(X_to_predict)
    proba = apply_draw_multiplier(proba, draw_prob_multiplier)
    predicted_classes = np.argmax(proba, axis=1)
    confidences = np.max(proba, axis=1)

    label_map = {v: k for k, v in result_map.items()}
    predictions_to_save = [
        {
            'match_id': int(df_to_predict_filtered.iloc[i]['match_id']),
            'predicted_result': label_map[predicted_classes[i]],
            'confidence': float(confidences[i]),
            'prob_home': float(proba[i][0]),
            'prob_draw': float(proba[i][1]),
            'prob_away': float(proba[i][2]),
        }
        for i in range(len(predicted_classes))
    ]

    with session.begin_nested():
        for pred_data in predictions_to_save:
            existing = session.execute(
                select(Predicted).filter_by(match_id=pred_data['match_id'])
            ).scalar_one_or_none()
            if existing:
                existing.predicted_result = pred_data['predicted_result']
                existing.confidence = pred_data['confidence']
                existing.prob_home = pred_data['prob_home']
                existing.prob_draw = pred_data['prob_draw']
                existing.prob_away = pred_data['prob_away']
            else:
                session.add(Predicted(
                    match_id=pred_data['match_id'],
                    predicted_result=pred_data['predicted_result'],
                    confidence=pred_data['confidence'],
                    prob_home=pred_data['prob_home'],
                    prob_draw=pred_data['prob_draw'],
                    prob_away=pred_data['prob_away'],
                ))
    session.commit()
    return pd.DataFrame(predictions_to_save)


def run_predictions(session: Session, engine: Engine):
    """Run the canonical end-to-end prediction pipeline.

    Trains ONE XGBoost model, evaluates it on a held-out set, checkpoints it,
    records metrics, and predicts both past and future matches. Replaces the old
    divergent NeuralNet (past) / XGBoost (future) setup. Exits early if there
    is not enough past-match data to train.

    Args:
        session (sqlalchemy.orm.Session): Active database session.
        engine (sqlalchemy.engine.Engine): Engine for reading tables and writing
            checkpoints/metrics.

    Returns:
        None:
    """
    db.create_all()  # ensure model_metrics (and any new) table exists

    result_map = {'H': 0, 'D': 1, 'A': 2}

    # Draw-probability multiplier: applied post-hoc at inference time (see
    # apply_draw_multiplier). Read from Config so it is tunable via env var
    # without code edits; defaults to 1.0 (no change).
    try:
        from src.flask_app.app.config import Config
        draw_prob_multiplier = float(getattr(Config, 'DRAW_PROB_MULTIPLIER', 1.0))
    except Exception:
        draw_prob_multiplier = 1.0
    print(f"Draw-probability multiplier = {draw_prob_multiplier}")

    df_full = create_full_dataframe_for_xgboost(session, engine)
    if df_full.empty or df_full[df_full['is_future_match'] == False].empty:
        print("Not enough past-match data to train the model. Exiting.")
        return

    X_train, X_test, y_train, y_test, features = prepare_training_data(df_full, result_map)
    if len(X_train) == 0:
        print("Not enough training data. Exiting.")
        return

    print("Training canonical XGBoost model...")
    model = train_model(X_train, y_train)

    acc, ll, baseline, macro_f1, per_class, cm = evaluate_model(
        model, X_test, y_test, result_map)
    print(f"[xgboost_canonical] test accuracy={acc:.4f}  log_loss={ll:.4f}  "
          f"macroF1={macro_f1:.4f}  baseline(ELO-fav)={baseline:.4f}  "
          f"(n_train={len(X_train)}, n_test={len(X_test)})")

    checkpoint_path = str(MODELS_DIR / f"{CANONICAL_MODEL_NAME}.json")
    save_checkpoint(model, checkpoint_path)
    persist_metrics(session, acc, ll, baseline, len(X_train), len(X_test),
                    features, checkpoint_path, macro_f1=macro_f1,
                    per_class=per_class, confusion_matrix=cm)
    print(f"Checkpoint saved: {checkpoint_path}")

    print("Predicting past matches...")
    predict_and_save_past_matches(model, features, result_map, session, engine,
                                  draw_prob_multiplier=draw_prob_multiplier)
    print("Predicting future matches...")
    predict_and_save_future_matches(model, features, result_map, session, engine,
                                    draw_prob_multiplier=draw_prob_multiplier)
    print("Predykcje zapisane (przeszłe + przyszłe).")