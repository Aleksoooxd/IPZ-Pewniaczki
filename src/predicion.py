import pandas as pd
from flask_app.app.db import db, app
from sqlalchemy import select
from sqlalchemy.orm import aliased
from flask_app.app.db import (
    FootballMatch, League, Season, Team, TeamValue,
    MatchStats, MatchForm
)


def create_match_dataframe_sql():
    """
    Efficiently creates a DataFrame of football matches, stats, values, and form by
    using SQLAlchemy Core for correct column names and pd.read_sql_query.
    """
    with app.app_context():
        engine = db.engine

        # Aliases for two team and value tables
        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)
        HomeValue = aliased(TeamValue)
        AwayValue = aliased(TeamValue)

        # Main match query
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
                FootballMatch.consensus
            )
            .outerjoin(League, FootballMatch.league)
            .outerjoin(Season, FootballMatch.season)
            .outerjoin(HomeTeam, FootballMatch.home_team)
            .outerjoin(AwayTeam, FootballMatch.away_team)
            .outerjoin(HomeValue, FootballMatch.home_value_ref)
            .outerjoin(AwayValue, FootballMatch.away_value_ref)
        )
        df_main = pd.read_sql_query(stmt_main, engine)

        # Query match statistics
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
            # Flatten multiindex columns
            df_stats_pivot.columns = [f"{side}_{stat}" for stat, side in df_stats_pivot.columns]
            df_stats_pivot = df_stats_pivot.reset_index()
            df_main = df_main.merge(df_stats_pivot, on='match_id', how='left')

        # Query form data
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
            MatchForm.team_strength
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

        return df_main


def main():
    df = create_match_dataframe_sql()
    csv_path = 'matches_data.csv'
    df.to_csv(csv_path, index=False)
    print(f"DataFrame saved to {csv_path}")
    print(df.head())


if __name__ == '__main__':
    main()
