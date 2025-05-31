import datetime
import copy # Keep copy for deepcopy in calculate_head2head_stats
from sqlalchemy import select
from flask_app.app.db import db, app, Team, FootballMatch, TeamElo, MatchForm # Import MatchForm

def calculate_elo_change(home_elo, away_elo, result, goal_diff=None):
    K = 40
    HOME_ADVANTAGE = 100

    if result == 'H':
        home_score, away_score = 1.0, 0.0
    elif result == 'D':
        home_score, away_score = 0.5, 0.5
    else:  # 'A'
        home_score, away_score = 0.0, 1.0

    adjusted_home_elo = home_elo + HOME_ADVANTAGE

    exp_home = 1.0 / (1.0 + 10.0 ** ((away_elo - adjusted_home_elo) / 400.0))
    exp_away = 1.0 - exp_home

    if goal_diff is not None and result != 'D':
        margin_factor = min(1.75, 1 + 0.75 * (goal_diff - 1) / 3.0)
        K *= margin_factor

    home_change = K * (home_score - exp_home)
    away_change = K * (away_score - exp_away)

    return home_change, away_change

# New function: calculate_head2head_stats (moved from footballScrap.py)
def calculate_head2head_stats(session, home_team_id, away_team_id, match_date):
    """Calculate head-to-head statistics between two teams up to a specific date."""
    # Get all previous matches between these teams
    previous_matches = session.execute(
        select(FootballMatch)
        .where(
            ((FootballMatch.home_team_id == home_team_id) & (FootballMatch.away_team_id == away_team_id) |
             (FootballMatch.home_team_id == away_team_id) & (FootballMatch.away_team_id == home_team_id)),
            FootballMatch.date < match_date
        )
        .order_by(FootballMatch.date.desc())
    ).scalars().all()

    # Initialize stats
    home_stats = {
        'h2h_matches': len(previous_matches),
        'h2h_wins': 0,
        'h2h_draws': 0,
        'h2h_losses': 0,
        'h2h_goals_for': 0,
        'h2h_goals_against': 0,
        'h2h_last_5_points': 0
    }

    away_stats = copy.deepcopy(home_stats)

    # Calculate stats
    last_5_count = 0
    for match in previous_matches:
        if last_5_count >= 5:
            break

        # Determine if the home_team_id in the *current* H2H match is the 'home' or 'away' team in the *previous* match
        is_home_team_in_prev_match_home = (match.home_team_id == home_team_id)
        is_away_team_in_prev_match_away = (match.away_team_id == away_team_id)

        if is_home_team_in_prev_match_home and is_away_team_in_prev_match_away: # Previous match was home_team vs away_team
            if match.result == 'H':
                home_stats['h2h_wins'] += 1
                away_stats['h2h_losses'] += 1
                if last_5_count < 5:
                    home_stats['h2h_last_5_points'] += 3
            elif match.result == 'A':
                home_stats['h2h_losses'] += 1
                away_stats['h2h_wins'] += 1
                if last_5_count < 5:
                    away_stats['h2h_last_5_points'] += 3
            else:  # Draw
                home_stats['h2h_draws'] += 1
                away_stats['h2h_draws'] += 1
                if last_5_count < 5:
                    home_stats['h2h_last_5_points'] += 1
                    away_stats['h2h_last_5_points'] += 1

            home_stats['h2h_goals_for'] += match.fthg
            home_stats['h2h_goals_against'] += match.ftag
            away_stats['h2h_goals_for'] += match.ftag
            away_stats['h2h_goals_against'] += match.fthg
        else: # Previous match was away_team vs home_team (reversed)
            if match.result == 'H': # Previous match home team won (which is our away team)
                away_stats['h2h_wins'] += 1
                home_stats['h2h_losses'] += 1
                if last_5_count < 5:
                    away_stats['h2h_last_5_points'] += 3
            elif match.result == 'A': # Previous match away team won (which is our home team)
                away_stats['h2h_losses'] += 1
                home_stats['h2h_wins'] += 1
                if last_5_count < 5:
                    home_stats['h2h_last_5_points'] += 3
            else:  # Draw
                away_stats['h2h_draws'] += 1
                home_stats['h2h_draws'] += 1
                if last_5_count < 5:
                    away_stats['h2h_last_5_points'] += 1
                    home_stats['h2h_last_5_points'] += 1

            away_stats['h2h_goals_for'] += match.fthg
            away_stats['h2h_goals_against'] += match.ftag
            home_stats['h2h_goals_for'] += match.ftag
            home_stats['h2h_goals_against'] += match.fthg

        last_5_count += 1

    return {'home': home_stats, 'away': away_stats}


def process_all_matches_for_elo():
    with app.app_context():
        print("Starting ELO and H2H calculation process...")

        teams = db.session.execute(select(Team)).scalars().all()
        teams_elo = {team.team_id: 1500.0 for team in teams}

        # Process matches chronologically
        matches = db.session.execute(
            select(FootballMatch)
            .order_by(FootballMatch.date, FootballMatch.match_id)
        ).scalars().all()

        print(f"Processing {len(matches)} matches for ELO and H2H calculation")

        for i, match in enumerate(matches):
            if not match.result:
                continue

            home_team_id = match.home_team_id
            away_team_id = match.away_team_id

            # ELO Calculation
            home_elo = teams_elo.get(home_team_id, 1500.0)
            away_elo = teams_elo.get(away_team_id, 1500.0)

            # Update match with ELO before current match (historical ELO)
            match.home_elo = home_elo
            match.away_elo = away_elo

            goal_diff = abs(match.fthg - match.ftag) if match.fthg is not None and match.ftag is not None else 0
            home_change, away_change = calculate_elo_change(home_elo, away_elo, match.result, goal_diff)

            match.home_elo_change = home_change
            match.away_elo_change = away_change

            # Update in-memory ELO ratings for future matches
            teams_elo[home_team_id] = home_elo + home_change
            teams_elo[away_team_id] = away_elo + away_change

            # Store ELO history
            db.session.add(TeamElo(
                team_id=home_team_id,
                rating=teams_elo[home_team_id],
                last_updated=match.date
            ))
            db.session.add(TeamElo(
                team_id=away_team_id,
                rating=teams_elo[away_team_id],
                last_updated=match.date
            ))

            # H2H Calculation and Update MatchForm
            h2h_stats = calculate_head2head_stats(db.session, home_team_id, away_team_id, match.date)

            for side, stats in h2h_stats.items():
                match_form = db.session.execute(
                    select(MatchForm)
                    .where(MatchForm.match_id == match.match_id, MatchForm.team_side == side)
                ).scalar_one_or_none()

                if match_form:
                    match_form.h2h_matches = stats['h2h_matches']
                    match_form.h2h_wins = stats['h2h_wins']
                    match_form.h2h_draws = stats['h2h_draws']
                    match_form.h2h_losses = stats['h2h_losses']
                    match_form.h2h_goals_for = stats['h2h_goals_for']
                    match_form.h2h_goals_against = stats['h2h_goals_against']
                    match_form.h2h_last_5_points = stats['h2h_last_5_points']
                else:
                    # This case should ideally not happen if MatchForm is created in footballScrap
                    # before this function is called, but adding for robustness.
                    print(f"Warning: MatchForm for match_id {match.match_id}, side {side} not found. Creating a new one.")
                    new_form_entry = MatchForm(
                        match_id=match.match_id,
                        team_side=side,
                        form_last_3=0,  # Default or derive if possible
                        form_last_5=0,
                        form_season=0,
                        goals_last_3=0,
                        goals_last_5=0,
                        goals_season=0,
                        team_placement=0,
                        h2h_matches=stats['h2h_matches'],
                        h2h_wins=stats['h2h_wins'],
                        h2h_draws=stats['h2h_draws'],
                        h2h_losses=stats['h2h_losses'],
                        h2h_goals_for=stats['h2h_goals_for'],
                        h2h_goals_against=stats['h2h_goals_against'],
                        h2h_last_5_points=stats['h2h_last_5_points']
                    )
                    db.session.add(new_form_entry)
            db.session.add(match) # Add the match object to session with updated ELO
            if i % 1000 == 0:
                print(f"Processed {i}/{len(matches)} matches")
                db.session.commit() # Commit periodically

        db.session.commit() # Final commit
        print("ELO and H2H calculation complete")


if __name__ == "__main__":
    process_all_matches_for_elo()