import datetime
from sqlalchemy import select
from flask_app.app.db import db, app, Team, FootballMatch, TeamElo


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


def process_all_matches_for_elo():

    with app.app_context():
        print("Starting ELO calculation process...")


        teams = db.session.execute(select(Team)).scalars().all()
        teams_elo = {team.team_id: 1500.0 for team in teams}

        # Process matches chronologically
        matches = db.session.execute(
            select(FootballMatch)
            .order_by(FootballMatch.date, FootballMatch.match_id)
        ).scalars().all()

        print(f"Processing {len(matches)} matches for ELO calculation")

        for i, match in enumerate(matches):
            if not match.result:
                continue

            home_team_id = match.home_team_id
            away_team_id = match.away_team_id


            home_elo = teams_elo.get(home_team_id, 1500.0)
            away_elo = teams_elo.get(away_team_id, 1500.0)


            match.home_elo = home_elo
            match.away_elo = away_elo


            goal_diff = abs(match.fthg - match.ftag) if match.fthg is not None and match.ftag is not None else 0
            home_change, away_change = calculate_elo_change(home_elo, away_elo, match.result, goal_diff)


            match.home_elo_change = home_change
            match.away_elo_change = away_change


            teams_elo[home_team_id] = home_elo + home_change
            teams_elo[away_team_id] = away_elo + away_change


            db.session.add(TeamElo(
                team_id=home_team_id,
                rating=home_elo + home_change,
                last_updated=match.date
            ))

            db.session.add(TeamElo(
                team_id=away_team_id,
                rating=away_elo + away_change,
                last_updated=match.date
            ))
            if i % 1000 == 0:
                print(f"Processed {i}/{len(matches)} matches")
                db.session.commit()

        db.session.commit()
        print("ELO calculation complete")


if __name__ == "__main__":
    process_all_matches_for_elo()