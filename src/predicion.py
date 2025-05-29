import pandas as pd
from flask_app.app.db import db, app
from sqlalchemy import select
from sqlalchemy.orm import aliased
import seaborn as sns
import matplotlib.pyplot as plt
from flask_app.app.db import (
    FootballMatch, League, Season, Team, TeamValue,
    MatchStats, MatchForm
)


def create_match_dataframe_sql():
    """
    Efficiently creates a DataFrame of football matches, stats, values, and form by
    using SQLAlchemy Core for correct column names and pd.read_sql_query.
    Now includes ELO ratings and changes.
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
                FootballMatch.consensus,
                # Add ELO columns
                FootballMatch.home_elo,
                FootballMatch.away_elo,
                FootballMatch.home_elo_change,
                FootballMatch.away_elo_change,
                # Calculate ELO difference
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

        # Add derived ELO features
        if 'home_elo' in df_main and 'away_elo' in df_main:
            # Calculate win probability based on ELO
            df_main['home_win_probability'] = 1.0 / (1.0 + 10 ** ((df_main['away_elo'] - (df_main['home_elo'] + 100)) / 400))
            df_main['draw_probability'] = 1 - df_main['home_win_probability'] - (1.0 / (1.0 + 10 ** ((df_main['home_elo'] - df_main['away_elo']) / 400)))
            df_main['away_win_probability'] = 1.0 / (1.0 + 10 ** ((df_main['home_elo'] + 100 - df_main['away_elo']) / 400))

        return df_main


def drop_non_predictive_columns(df):
    """
    Drop columns that are typically not statistically significant for prediction models.
    """
    # Columns to drop - identifiers and metadata
    non_predictive_cols = [
        'match_id',  # Unique identifier
        'date',  # Date information
        'home_team',  # Team name strings
        'away_team',  # Team name strings
        'home_matchday',  # Sequential information
        'away_matchday',  # Sequential information
        'league',  # League identifier
        'season',  # Season identifier
        'away_team_strength',
        'home_team_strength',
        'home_elo_change',
        'away_elo_change',
        'is_surprise',  # Boolean flags
    ]

    # Only drop columns that exist in the dataframe
    cols_to_drop = [col for col in non_predictive_cols if col in df.columns]

    print(f"Dropping non-predictive columns: {cols_to_drop}")
    return df.drop(columns=cols_to_drop)

def main():
    df = create_match_dataframe_sql()
    df = drop_non_predictive_columns(df)
    important_columns = ['result', 'home_goals', 'away_goals', 'home_elo', 'away_elo','elo_difference',
                         'home_win_probability', 'draw_probability', 'away_win_probability','home_value', 'away_value','home_form_last_3', 'away_form_last_3','home_form_last_5', 'away_form_last_5','home_form_season', 'away_form_season','home_team_placement', 'away_team_placement','home_goals_last_3', 'away_goals_last_3','home_goals_last_5', 'away_goals_last_5','home_goals_season', 'away_goals_season','home_mean', 'away_mean','home_std', 'away_std','home_shannon', 'away_shannon','home_cv', 'away_cv','home_gini', 'away_gini','home_hhi', 'away_hhi']
    csv_path = 'matches_data.csv'
    df.to_csv(csv_path, index=False)
    print(f"DataFrame saved to {csv_path}")
    plt.rcParams.update({'font.size': 12})
    g = sns.pairplot(
        df[important_columns],
        hue='result',
        diag_kind='kde',
        height=3.5,  # Increase size of each subplot
        aspect=1.2,  # Slightly wider than tall
        plot_kws={'alpha': 0.6, 's': 80},  # Larger and semi-transparent markers
        diag_kws={'linewidth': 2, 'alpha': 0.8}
    )

    # Improve legend and labels
    g._legend.set_title("Match Result", fontsize=14)
    plt.subplots_adjust(top=0.95)

    # Save the plot with higher resolution
    plot_path = 'matches_pairplot.png'
    g.savefig(plot_path, bbox_inches='tight', dpi=400)
    print(f"Pairplot saved to {plot_path}")

    plt.show()




if __name__ == '__main__':
    main()
