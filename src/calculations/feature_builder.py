from bisect import bisect_left
from collections import defaultdict

import pandas as pd
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.engine import Engine

from src.flask_app.app.models import (
    FootballMatch, FutureMatch, MatchForm, MatchStats, TeamElo,
    League, Season, Team,
)


# Columns produced by MatchForm, prefixed home_/away_ after the pivot.
FORM_COLS = [
    'form_last_3', 'form_last_5', 'form_season', 'goals_last_3', 'goals_last_5',
    'goals_season', 'team_placement', 'h2h_wins', 'h2h_draws', 'h2h_losses',
    'h2h_matches', 'h2h_goals_for', 'h2h_goals_against', 'h2h_last_5_points'
]
STATS_COLS = ['mean', 'std', 'shannon', 'cv', 'gini', 'hhi']


def _backfill_elo(session: Session, df_full: pd.DataFrame) -> pd.DataFrame:
    """Back-fill null ELO ratings for future matches from the latest snapshot.

    For any match whose ``home_elo`` / ``away_elo`` is missing, the most recent
    ``TeamElo`` rating for that team is looked up and written in, then the
    ``elo_difference`` column (home minus away) is recomputed for the whole frame.

    Args:
        session (sqlalchemy.orm.Session): Active database session used to read
            the latest ``TeamElo`` ratings.
        df_full (pandas.DataFrame): Match dataframe containing ``home_elo``,
            ``away_elo``, ``home_team_id`` and ``away_team_id`` columns.

    Returns:
        pandas.DataFrame: The same dataframe, with ELO gaps filled and
        ``elo_difference`` recalculated.
    """
    latest_elos = session.execute(
        select(TeamElo.team_id, TeamElo.rating)
        .order_by(TeamElo.last_updated.desc())
    ).fetchall()
    latest_elos_df = pd.DataFrame(
        latest_elos, columns=['team_id', 'rating']
    ).drop_duplicates(subset=['team_id'], keep='first')

    elo_map = latest_elos_df.set_index('team_id')['rating']
    null_home = df_full['home_elo'].isnull()
    null_away = df_full['away_elo'].isnull()
    df_full.loc[null_home, 'home_elo'] = \
        df_full.loc[null_home, 'home_team_id'].map(elo_map)
    df_full.loc[null_away, 'away_elo'] = \
        df_full.loc[null_away, 'away_team_id'].map(elo_map)
    df_full['elo_difference'] = df_full['home_elo'] - df_full['away_elo']
    return df_full


def _add_win_probabilities(df: pd.DataFrame) -> pd.DataFrame:
    """Add ELO-derived Home/Draw/Away win probabilities to the dataframe.

    Uses the same expected-score logic (with a +100 home advantage) as
    :func:`elo_calculator.calculate_elo_change`, so the probabilities are
    consistent with the ELO model. No-op if the ELO columns are absent.

    Args:
        df (pandas.DataFrame): Match dataframe containing ``home_elo`` and
            ``away_elo`` columns.

    Returns:
        pandas.DataFrame: The dataframe with ``home_win_probability``,
        ``draw_probability`` and ``away_win_probability`` columns added.
    """
    if 'home_elo' in df.columns and 'away_elo' in df.columns:
        df['home_win_probability'] = 1.0 / (
            1.0 + 10 ** ((df['away_elo'] - (df['home_elo'] + 100)) / 400))
        df['draw_probability'] = 1 - df['home_win_probability'] - (
            1.0 / (1.0 + 10 ** ((df['home_elo'] + 100 - df['away_elo']) / 400)))
        df['away_win_probability'] = 1.0 / (
            1.0 + 10 ** ((df['home_elo'] + 100 - df['away_elo']) / 400))
    return df


def _merge_side_features(df_full: pd.DataFrame, df_side: pd.DataFrame,
                         cols) -> pd.DataFrame:
    """Pivot a long (match_id, team_side, field) table to home_/away_ columns.

    The side table is pivoted so each ``field`` becomes ``home_<field>`` /
    ``away_<field>`` columns, then left-joined onto the match dataframe on
    ``match_id``. When the side table is empty, the expected
    ``home_<col>`` / ``away_<col>`` columns are created as NaN so downstream
    code can always rely on their presence.

    Args:
        df_full (pandas.DataFrame): Match dataframe to merge features onto;
            must contain a ``match_id`` column.
        df_side (pandas.DataFrame): Long-format table with ``match_id``,
            ``team_side`` ('home'/'away'), and the ``cols`` fields.
        cols (list[str]): Field names present in ``df_side`` to spread across
            the two sides.

    Returns:
        pandas.DataFrame: ``df_full`` with the merged home_/away_ columns.
    """
    if df_side.empty:
        for col in cols:
            df_full[f'home_{col}'] = np.nan
            df_full[f'away_{col}'] = np.nan
        return df_full
    pivot = df_side.pivot(index='match_id', columns='team_side')
    pivot.columns = [f"{side}_{field}" for field, side in pivot.columns]
    return pd.merge(df_full, pivot.reset_index(), on='match_id', how='left')


def _backfill_future_features(df_full: pd.DataFrame, df_football: pd.DataFrame,
                              df_form: pd.DataFrame, df_stats: pd.DataFrame,
                              form_cols, stats_cols) -> pd.DataFrame:
    """Back-fill form, stats and head-to-head features for future matches.

    Future matches that have no precomputed ``MatchForm`` row (detected via a
    null ``home_form_season``) get their features reconstructed from past data:
    for each side the nearest past match before the fixture date is found via a
    binary search and its form/stats copied across; the head-to-head record
    against the opponent is recomputed from all past meetings before that date.

    Every required dataset is loaded once and kept in memory: per-team and
    per-H2H-pair lists are sorted once, and each future match resolves its
    lookups with an O(log n) binary search instead of round-tripping to the
    database.

    Args:
        df_full (pandas.DataFrame): The full match dataframe (past + future)
            that will be mutated in place for the targeted future rows.
        df_football (pandas.DataFrame): Past ``FootballMatch`` rows with
            ``match_id``, ``date``, team ids, ``result``, ``fthg``, ``ftag``.
        df_form (pandas.DataFrame): Long ``MatchForm`` rows keyed by
            ``(match_id, team_side)``.
        df_stats (pandas.DataFrame): Long ``MatchStats`` rows keyed by
            ``(match_id, team_side)``.
        form_cols (list[str]): Form field names to copy from ``df_form``.
        stats_cols (list[str]): Stats field names to copy from ``df_stats``.

    Returns:
        pandas.DataFrame: ``df_full`` with the future rows' features filled in.
    """
    if df_full.empty or df_football.empty:
        return df_full

    future_mask = df_full['is_future_match'] & df_full['home_form_season'].isnull()
    future_to_update = df_full[future_mask]
    if future_to_update.empty:
        return df_full

    # Past matches only (matches still lacking a result have no form to copy).
    past = df_football[df_football['result'].notnull()].copy()
    past['date'] = pd.to_datetime(past['date'])
    if past.empty:
        return df_full

    # Per team: past matches sorted by (date, match_id), with a parallel date array.
    team_dates = defaultdict(list)
    team_entries = defaultdict(list)  # (match_id, side) aligned with team_dates
    for mid, dt, ht, at in zip(
        past['match_id'], past['date'], past['home_team_id'], past['away_team_id']
    ):
        team_dates[ht].append(dt)
        team_entries[ht].append((mid, 'home'))
        team_dates[at].append(dt)
        team_entries[at].append((mid, 'away'))
    for tid in team_dates:
        order = sorted(range(len(team_dates[tid])),
                       key=lambda i: (team_dates[tid][i], team_entries[tid][i][0]))
        team_dates[tid] = [team_dates[tid][i] for i in order]
        team_entries[tid] = [team_entries[tid][i] for i in order]

    # Per unordered team pair: H2H matches sorted by (date, match_id).
    h2h_dates = defaultdict(list)
    h2h_rows = defaultdict(list)  # (home_id, away_id, result, fthg, ftag) aligned
    for mid, dt, ht, at, res, fthg, ftag in zip(
        past['match_id'], past['date'], past['home_team_id'], past['away_team_id'],
        past['result'], past['fthg'], past['ftag']
    ):
        pair = (ht, at) if ht < at else (at, ht)
        h2h_dates[pair].append(dt)
        h2h_rows[pair].append((ht, at, res, fthg, ftag))
    for pair in h2h_dates:
        order = sorted(range(len(h2h_dates[pair])),
                       key=lambda i: h2h_dates[pair][i])
        h2h_dates[pair] = [h2h_dates[pair][i] for i in order]
        h2h_rows[pair] = [h2h_rows[pair][i] for i in order]

    # Form / stats lookup keyed by (match_id, team_side).
    form_lookup = {(int(r['match_id']), r['team_side']): r
                   for _, r in df_form.iterrows()} if not df_form.empty else {}
    stats_lookup = {(int(r['match_id']), r['team_side']): r
                    for _, r in df_stats.iterrows()} if not df_stats.empty else {}

    for index, row in future_to_update.iterrows():
        home_team_id = row['home_team_id']
        away_team_id = row['away_team_id']
        match_date = pd.to_datetime(row['date'])

        for side_team_id, prefix in [(home_team_id, 'home'), (away_team_id, 'away')]:
            dates = team_dates.get(side_team_id)
            if not dates:
                continue
            pos = bisect_left(dates, match_date) - 1
            if pos < 0:
                continue
            latest_match_id, side_in_last = team_entries[side_team_id][pos]
            key = (int(latest_match_id), side_in_last)
            form_row = form_lookup.get(key)
            if form_row is not None:
                for col in form_cols:
                    df_full.loc[index, f'{prefix}_{col}'] = form_row[col]
            stats_row = stats_lookup.get(key)
            if stats_row is not None:
                for col in stats_cols:
                    df_full.loc[index, f'{prefix}_{col}'] = stats_row[col]

        pair = (home_team_id, away_team_id) if home_team_id < away_team_id \
            else (away_team_id, home_team_id)
        dates = h2h_dates.get(pair, [])
        cut = bisect_left(dates, match_date)
        past_h2h = h2h_rows.get(pair, [])[:cut]

        h2h_home_wins = h2h_draws = h2h_goals_for_home = h2h_goals_against_home = 0
        h2h_last_5_points_home_sum = 0
        for ht, at, res, fthg, ftag in past_h2h:
            if ht == home_team_id:
                home_points = 3 if res == 'H' else (1 if res == 'D' else 0)
                h2h_goals_for_home += fthg or 0
                h2h_goals_against_home += ftag or 0
            else:
                home_points = 3 if res == 'A' else (1 if res == 'D' else 0)
                h2h_goals_for_home += ftag or 0
                h2h_goals_against_home += fthg or 0
            if res in ('H', 'A') and home_points == 3:
                h2h_home_wins += 1
            elif res == 'D':
                h2h_draws += 1
            h2h_last_5_points_home_sum += home_points

        n = len(past_h2h)
        h2h_losses = n - h2h_home_wins - h2h_draws
        df_full.loc[index, 'home_h2h_matches'] = n
        df_full.loc[index, 'home_h2h_wins'] = h2h_home_wins
        df_full.loc[index, 'home_h2h_draws'] = h2h_draws
        df_full.loc[index, 'home_h2h_losses'] = h2h_losses
        df_full.loc[index, 'home_h2h_goals_for'] = h2h_goals_for_home
        df_full.loc[index, 'home_h2h_goals_against'] = h2h_goals_against_home
        df_full.loc[index, 'home_h2h_last_5_points'] = h2h_last_5_points_home_sum
        df_full.loc[index, 'away_h2h_matches'] = n
        df_full.loc[index, 'away_h2h_wins'] = h2h_losses
        df_full.loc[index, 'away_h2h_draws'] = h2h_draws
        df_full.loc[index, 'away_h2h_losses'] = h2h_home_wins
        df_full.loc[index, 'away_h2h_goals_for'] = h2h_goals_against_home
        df_full.loc[index, 'away_h2h_goals_against'] = h2h_goals_for_home
        df_full.loc[index, 'away_h2h_last_5_points'] = h2h_last_5_points_home_sum

    return df_full


def build_match_features(session: Session, engine: Engine,
                         include_future: bool = True) -> pd.DataFrame:
    """Build the match-feature dataframe used for both training and inference.

    Past ``FootballMatch`` rows are always loaded (with the standard
    team/league/season joins). When ``include_future`` is set, upcoming
    ``FutureMatch`` rows are concatenated, their ELO is back-filled from the
    latest snapshot, and form/stats/H2H are back-filled for rows lacking a
    precomputed ``MatchForm``. Form and stats are pivoted to home_/away_ columns
    and merged on, then ELO-derived win probabilities are added.

    Args:
        session (sqlalchemy.orm.Session): Active session, used to back-fill
            future ELO from ``TeamElo``.
        engine (sqlalchemy.engine.Engine): Engine used to read tables into
            dataframes via ``pandas.read_sql_query``.
        include_future (bool, optional): When True, append ``FutureMatch`` rows
            and back-fill their features. Defaults to True.

    Returns:
        pandas.DataFrame: One row per match with all home_/away_ feature
        columns, ELO-derived win probabilities, and an ``is_future_match`` flag.
    """
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

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
            FootballMatch.consensus,
            FootballMatch.is_surprise,
            FootballMatch.fthg,
            FootballMatch.ftag
        )
        .outerjoin(League, FootballMatch.league)
        .outerjoin(Season, FootballMatch.season)
        .outerjoin(HomeTeam, FootballMatch.home_team)
        .outerjoin(AwayTeam, FootballMatch.away_team)
    )
    df_football = pd.read_sql_query(stmt_football_match, engine)
    df_football['is_future_match'] = False

    if include_future:
        stmt_future_match = (
            select(
                FutureMatch.match_id,
                FutureMatch.date,
                None,
                League.code.label('league'),
                Season.name.label('season'),
                HomeTeam.team_id.label('home_team_id'),
                HomeTeam.name.label('home_team_name'),
                AwayTeam.team_id.label('away_team_id'),
                AwayTeam.name.label('away_team_name'),
            )
            .outerjoin(League, FutureMatch.league)
            .outerjoin(Season, FutureMatch.season)
            .outerjoin(HomeTeam, FutureMatch.home_team)
            .outerjoin(AwayTeam, FutureMatch.away_team)
        )
        df_future = pd.read_sql_query(stmt_future_match, engine)
        for col in ['result', 'home_elo', 'away_elo', 'elo_difference',
                    'consensus', 'is_surprise', 'fthg', 'ftag']:
            if col not in df_future.columns:
                df_future[col] = None
        df_future['is_future_match'] = True
        # Skip the concat when there are no future matches: pd.concat with an
        # empty frame raises a FutureWarning about dtype inference and is also
        # just wasteful.
        df_full = (
            pd.concat([df_football, df_future], ignore_index=True)
            if not df_future.empty
            else df_football.copy()
        )
    else:
        df_full = df_football

    df_full = _backfill_elo(session, df_full)
    df_full = _add_win_probabilities(df_full)

    stmt_form = select(
        MatchForm.match_id, MatchForm.team_side,
        MatchForm.form_last_3, MatchForm.form_last_5, MatchForm.form_season,
        MatchForm.goals_last_3, MatchForm.goals_last_5, MatchForm.goals_season,
        MatchForm.team_placement,
        MatchForm.h2h_wins, MatchForm.h2h_draws, MatchForm.h2h_losses,
        MatchForm.h2h_matches, MatchForm.h2h_goals_for, MatchForm.h2h_goals_against,
        MatchForm.h2h_last_5_points
    )
    df_form = pd.read_sql_query(stmt_form, engine)

    stmt_stats = select(
        MatchStats.match_id, MatchStats.team_side,
        MatchStats.mean, MatchStats.std, MatchStats.shannon,
        MatchStats.cv, MatchStats.gini, MatchStats.hhi
    )
    df_stats = pd.read_sql_query(stmt_stats, engine)

    df_full = _merge_side_features(df_full, df_form, FORM_COLS)
    df_full = _merge_side_features(df_full, df_stats, STATS_COLS)

    if include_future:
        df_full = _backfill_future_features(
            df_full, df_football, df_form, df_stats, FORM_COLS, STATS_COLS)

    return df_full


def encode_consensus(df: pd.DataFrame, features, append_new: bool = False):
    """One-hot encode the ``consensus`` categorical column for the model.

    One-hot encodes the ``consensus`` column into ``consensus_*`` dummy columns
    and keeps the feature list aligned with the model. The raw ``consensus``
    column is always dropped.

    Training path (``append_new=True``): any newly created ``consensus_*``
    column is appended to ``features`` so the model learns it.

    Inference path (``append_new=False``): ``features`` is treated as the frozen
    model feature set — ``consensus_*`` columns it expects but this batch lacks
    are back-filled with 0, and any unseen ``consensus_*`` category is dropped.

    Args:
        df (pandas.DataFrame): Match dataframe possibly containing a
            ``consensus`` column.
        features (list[str]): Current model feature list.
        append_new (bool, optional): True on the training path to grow the
            feature list with new categories; False on inference to conform to a
            frozen feature set. Defaults to False.

    Returns:
        tuple[pandas.DataFrame, list[str]]: ``(df, features)`` with the encoded
        dataframe and the (possibly updated) feature list.
    """
    if 'consensus' not in df.columns:
        return df, list(features)

    df = pd.get_dummies(df, columns=['consensus'], prefix='consensus', dummy_na=False)
    consensus_cols = [c for c in df.columns if c.startswith('consensus_')]
    result_features = list(features)

    if append_new:
        for col in consensus_cols:
            if col not in result_features:
                result_features.append(col)
    else:
        for col in (c for c in result_features if c.startswith('consensus_')):
            if col not in df.columns:
                df[col] = 0
        extra = [c for c in consensus_cols if c not in result_features]
        if extra:
            df = df.drop(columns=extra)

    return df, result_features
