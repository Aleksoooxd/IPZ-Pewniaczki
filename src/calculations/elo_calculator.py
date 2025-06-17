import datetime
import copy
from sqlalchemy import select
from flask_app.app.db import db, app, Team, FootballMatch, TeamElo, MatchForm


def calculate_elo_change(home_elo, away_elo, result, goal_diff=None):
    K = 40
    HOME_ADVANTAGE = 100

    if result == 'H':
        home_score, away_score = 1.0, 0.0
    elif result == 'D':
        home_score, away_score = 0.5, 0.5
    else:
        home_score, away_score = 0.0, 1.0

    adjusted_home_elo = home_elo + HOME_ADVANTAGE

    exp_home = round((1.0 / (1.0 + 10.0 ** ((away_elo - adjusted_home_elo) / 400.0))),4)
    exp_away = 1.0 - exp_home

    if goal_diff is not None and result != 'D':
        margin_factor = min(1.75, 1 + 0.75 * (goal_diff - 1) / 3.0)
        K *= margin_factor

    home_change = round((K * (home_score - exp_home)),2)
    away_change = round((K * (away_score - exp_away)),2)

    return home_change, away_change


def process_all_matches_for_elo():
    with app.app_context():
        print("Starting ELO and H2H calculation process (optimized and reset-friendly)...")


        teams = db.session.execute(select(Team)).scalars().all()
        teams_elo = {team.team_id: 1500.0 for team in teams}

        all_match_forms = {}
        for mf in db.session.execute(select(MatchForm)).scalars().all():
            all_match_forms[(mf.match_id, mf.team_side)] = mf


        h2h_current_stats = {}


        matches = db.session.execute(
            select(FootballMatch)
            .order_by(FootballMatch.date, FootballMatch.match_id)
        ).scalars().all()

        print(f"Processing {len(matches)} matches for ELO and H2H calculation")


        team_elo_to_add = []
        match_form_updates = []
        football_match_updates = []

        for i, match in enumerate(matches):
            if not match.result:
                continue

            home_team_id = match.home_team_id
            away_team_id = match.away_team_id



            current_home_elo = teams_elo.get(home_team_id, 1500.0)
            current_away_elo = teams_elo.get(away_team_id, 1500.0)


            match.home_elo = current_home_elo
            match.away_elo = current_away_elo

            goal_diff = abs(match.fthg - match.ftag) if match.fthg is not None and match.ftag is not None else 0
            home_change, away_change = calculate_elo_change(current_home_elo, current_away_elo, match.result, goal_diff)


            match.home_elo_change = home_change
            match.away_elo_change = away_change


            teams_elo[home_team_id] += home_change
            teams_elo[away_team_id] += away_change


            team_elo_to_add.append(TeamElo(
                team_id=home_team_id,
                rating=teams_elo[home_team_id],
                last_updated=match.date
            ))
            team_elo_to_add.append(TeamElo(
                team_id=away_team_id,
                rating=teams_elo[away_team_id],
                last_updated=match.date
            ))


            football_match_updates.append({
                'match_id': match.match_id,
                'home_elo': match.home_elo,
                'away_elo': match.away_elo,
                'home_elo_change': match.home_elo_change,
                'away_elo_change': match.away_elo_change
            })


            team_pair_key = frozenset({home_team_id, away_team_id})


            if team_pair_key not in h2h_current_stats:
                h2h_current_stats[team_pair_key] = {
                    home_team_id: {'h2h_matches': 0, 'h2h_wins': 0, 'h2h_draws': 0, 'h2h_losses': 0, 'h2h_goals_for': 0,
                                   'h2h_goals_against': 0, 'last_5_points': []},
                    away_team_id: {'h2h_matches': 0, 'h2h_wins': 0, 'h2h_draws': 0, 'h2h_losses': 0, 'h2h_goals_for': 0,
                                   'h2h_goals_against': 0, 'last_5_points': []}
                }

            h2h_home_pre_match = copy.deepcopy(h2h_current_stats[team_pair_key][home_team_id])
            h2h_away_pre_match = copy.deepcopy(h2h_current_stats[team_pair_key][away_team_id])

            h2h_home_pre_match['h2h_last_5_points'] = sum(h2h_home_pre_match['last_5_points'])
            h2h_away_pre_match['h2h_last_5_points'] = sum(h2h_away_pre_match['last_5_points'])

            home_match_form = all_match_forms.get((match.match_id, 'home'))
            away_match_form = all_match_forms.get((match.match_id, 'away'))

            if home_match_form:
                match_form_updates.append({
                    'form_id': home_match_form.form_id,
                    'h2h_matches': h2h_home_pre_match['h2h_matches'],
                    'h2h_wins': h2h_home_pre_match['h2h_wins'],
                    'h2h_draws': h2h_home_pre_match['h2h_draws'],
                    'h2h_losses': h2h_home_pre_match['h2h_losses'],
                    'h2h_goals_for': h2h_home_pre_match['h2h_goals_for'],
                    'h2h_goals_against': h2h_home_pre_match['h2h_goals_against'],
                    'h2h_last_5_points': h2h_home_pre_match['h2h_last_5_points']
                })
            if away_match_form:
                match_form_updates.append({
                    'form_id': away_match_form.form_id,
                    'h2h_matches': h2h_away_pre_match['h2h_matches'],
                    'h2h_wins': h2h_away_pre_match['h2h_wins'],
                    'h2h_draws': h2h_away_pre_match['h2h_draws'],
                    'h2h_losses': h2h_away_pre_match['h2h_losses'],
                    'h2h_goals_for': h2h_away_pre_match['h2h_goals_for'],
                    'h2h_goals_against': h2h_away_pre_match['h2h_goals_against'],
                    'h2h_last_5_points': h2h_away_pre_match['h2h_last_5_points']
                })
            current_home_h2h_in_memory = h2h_current_stats[team_pair_key][home_team_id]
            current_away_h2h_in_memory = h2h_current_stats[team_pair_key][away_team_id]

            current_home_h2h_in_memory['h2h_matches'] += 1
            current_away_h2h_in_memory['h2h_matches'] += 1

            home_points_earned = 0
            away_points_earned = 0

            if match.result == 'H':
                current_home_h2h_in_memory['h2h_wins'] += 1
                current_away_h2h_in_memory['h2h_losses'] += 1
                home_points_earned = 3
                away_points_earned = 0
            elif match.result == 'D':
                current_home_h2h_in_memory['h2h_draws'] += 1
                current_away_h2h_in_memory['h2h_draws'] += 1
                home_points_earned = 1
                away_points_earned = 1
            elif match.result == 'A':
                current_home_h2h_in_memory['h2h_losses'] += 1
                current_away_h2h_in_memory['h2h_wins'] += 1
                home_points_earned = 0
                away_points_earned = 3

            current_home_h2h_in_memory['h2h_goals_for'] += match.fthg if match.fthg is not None else 0
            current_home_h2h_in_memory['h2h_goals_against'] += match.ftag if match.ftag is not None else 0
            current_away_h2h_in_memory['h2h_goals_for'] += match.ftag if match.ftag is not None else 0
            current_away_h2h_in_memory['h2h_goals_against'] += match.fthg if match.fthg is not None else 0

            current_home_h2h_in_memory['last_5_points'].insert(0, home_points_earned)
            if len(current_home_h2h_in_memory['last_5_points']) > 5:
                current_home_h2h_in_memory['last_5_points'].pop()

            current_away_h2h_in_memory['last_5_points'].insert(0, away_points_earned)
            if len(current_away_h2h_in_memory['last_5_points']) > 5:
                current_away_h2h_in_memory['last_5_points'].pop()


            if (i + 1) % 1000 == 0:
                print(f"Processed {i + 1}/{len(matches)} matches, performing batch update.")
                if team_elo_to_add:
                    db.session.bulk_save_objects(team_elo_to_add)
                    team_elo_to_add = []
                if match_form_updates:
                    db.session.bulk_update_mappings(MatchForm, match_form_updates)
                    match_form_updates = []
                if football_match_updates:
                    db.session.bulk_update_mappings(FootballMatch, football_match_updates)
                    football_match_updates = []
                db.session.commit()

        print("Finalizing batch updates...")
        if team_elo_to_add:
            db.session.bulk_save_objects(team_elo_to_add)
        if match_form_updates:
            db.session.bulk_update_mappings(MatchForm, match_form_updates)
        if football_match_updates:
            db.session.bulk_update_mappings(FootballMatch, football_match_updates)
        db.session.commit()
        print("ELO and H2H calculation complete")