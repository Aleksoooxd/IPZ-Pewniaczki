import copy
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.flask_app.app.models import Team, FootballMatch, TeamElo, MatchForm, SystemStats


def calculate_elo_change(home_elo, away_elo, result, goal_diff=None):
    """Compute the ELO rating change for the home and away teams after a match.

    Uses the standard ELO expected-score formula with a fixed home advantage of
    100 points. The K-factor (40) is scaled by the victory margin when the
    result is not a draw, capped at 1.75.

    Args:
        home_elo (float): Pre-match ELO rating of the home team.
        away_elo (float): Pre-match ELO rating of the away team.
        result (str): Match outcome, one of 'H' (home win), 'D' (draw),
            or 'A' (away win).
        goal_diff (int, optional): Absolute goal difference of the match.
            Used to apply the margin-of-victory scaling. Defaults to None,
            in which case no scaling is applied.

    Returns:
        tuple[float, float]: A pair ``(home_change, away_change)`` of rounded
        ELO deltas (2 decimal places) to apply to the home and away teams.
    """
    K = 40
    HOME_ADVANTAGE = 100

    if result == 'H':
        home_score, away_score = 1.0, 0.0
    elif result == 'D':
        home_score, away_score = 0.5, 0.5
    else:
        home_score, away_score = 0.0, 1.0

    adjusted_home_elo = home_elo + HOME_ADVANTAGE

    exp_home = round((1.0 / (1.0 + 10.0 ** ((away_elo - adjusted_home_elo) / 400.0))), 4)
    exp_away = 1.0 - exp_home

    if goal_diff is not None and result != 'D':
        margin_factor = min(1.75, 1 + 0.75 * (goal_diff - 1) / 3.0)
        K *= margin_factor

    home_change = round((K * (home_score - exp_home)), 2)
    away_change = round((K * (away_score - exp_away)), 2)

    return home_change, away_change


def process_all_matches_for_elo(session: Session):
    """Recompute ELO ratings, head-to-head form, and season-end ELO snapshots.

    Iterates over all ``FootballMatch`` rows in date order, computing the ELO
    change for each played match (via :func:`calculate_elo_change`) and writing
    the resulting ``home_elo`` / ``away_elo`` / ``home_elo_change`` /
    ``away_elo_change`` columns back to ``FootballMatch``. It also snapshots the
    per-team head-to-head record (wins / draws / losses / goals / last-5 points)
    into the corresponding ``MatchForm`` rows *before* each match is played.

    The ``TeamElo`` table is collapsed to a single season-end snapshot per
    ``(team_id, season_id)`` (the last rating seen for that team in that season),
    replacing all prior rows. Finally, the ``SystemStats`` highest/lowest ELO
    pointers are refreshed against the collapsed table.

    Updates are flushed in batches of 1000 matches and committed at the end.

    Args:
        session (sqlalchemy.orm.Session): Active database session. The function
            commits its own transactions; the caller does not need to.

    Returns:
        None:
    """
    print("Starting ELO and H2H calculation process...")

    teams = session.execute(select(Team)).scalars().all()
    teams_elo = {team.team_id: 1500.0 for team in teams}

    all_match_forms = {}
    for mf in session.execute(select(MatchForm)).scalars().all():
        all_match_forms[(mf.match_id, mf.team_side)] = mf

    h2h_current_stats = {}

    # Season-end ELO snapshot per (team_id, season_id): rating + last match date.
    # Collapses the table from 2 rows/match to ~teams x seasons rows.
    season_end_ratings = {}

    matches = session.execute(
        select(FootballMatch)
        .order_by(FootballMatch.date, FootballMatch.match_id)
    ).scalars().all()

    print(f"Processing {len(matches)} matches for ELO and H2H calculation")

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

        # Record season-end snapshot (matches are processed in date order, so the
        # last write per (team, season) is that season's final rating).
        season_end_ratings[(home_team_id, match.season_id)] = (teams_elo[home_team_id], match.date)
        season_end_ratings[(away_team_id, match.season_id)] = (teams_elo[away_team_id], match.date)

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
                home_team_id: {'h2h_matches': 0, 'h2h_wins': 0, 'h2h_draws': 0, 'h2h_losses': 0,
                               'h2h_goals_for': 0, 'h2h_goals_against': 0, 'last_5_points': []},
                away_team_id: {'h2h_matches': 0, 'h2h_wins': 0, 'h2h_draws': 0, 'h2h_losses': 0,
                               'h2h_goals_for': 0, 'h2h_goals_against': 0, 'last_5_points': []}
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

        current_home_h2h = h2h_current_stats[team_pair_key][home_team_id]
        current_away_h2h = h2h_current_stats[team_pair_key][away_team_id]

        current_home_h2h['h2h_matches'] += 1
        current_away_h2h['h2h_matches'] += 1

        home_points_earned = 0
        away_points_earned = 0

        if match.result == 'H':
            current_home_h2h['h2h_wins'] += 1
            current_away_h2h['h2h_losses'] += 1
            home_points_earned = 3
        elif match.result == 'D':
            current_home_h2h['h2h_draws'] += 1
            current_away_h2h['h2h_draws'] += 1
            home_points_earned = 1
            away_points_earned = 1
        elif match.result == 'A':
            current_home_h2h['h2h_losses'] += 1
            current_away_h2h['h2h_wins'] += 1
            away_points_earned = 3

        current_home_h2h['h2h_goals_for'] += match.fthg if match.fthg is not None else 0
        current_home_h2h['h2h_goals_against'] += match.ftag if match.ftag is not None else 0
        current_away_h2h['h2h_goals_for'] += match.ftag if match.ftag is not None else 0
        current_away_h2h['h2h_goals_against'] += match.fthg if match.fthg is not None else 0

        current_home_h2h['last_5_points'].insert(0, home_points_earned)
        if len(current_home_h2h['last_5_points']) > 5:
            current_home_h2h['last_5_points'].pop()

        current_away_h2h['last_5_points'].insert(0, away_points_earned)
        if len(current_away_h2h['last_5_points']) > 5:
            current_away_h2h['last_5_points'].pop()

        if (i + 1) % 1000 == 0:
            print(f"Processed {i + 1}/{len(matches)} matches, performing batch update.")
            if match_form_updates:
                session.bulk_update_mappings(MatchForm, match_form_updates)
                match_form_updates = []
            if football_match_updates:
                session.bulk_update_mappings(FootballMatch, football_match_updates)
                football_match_updates = []
            session.commit()

    print("Finalizing batch updates...")
    if match_form_updates:
        session.bulk_update_mappings(MatchForm, match_form_updates)
    if football_match_updates:
        session.bulk_update_mappings(FootballMatch, football_match_updates)
    session.commit()

    # Collapse TeamElo to one season-end snapshot per (team, season). Recomputing
    # from scratch, so replace all rows with the collapsed set.
    print(f"Collapsing TeamElo to {len(season_end_ratings)} season-end snapshots...")
    session.execute(text("DELETE FROM team_elo"))
    session.commit()
    session.bulk_save_objects([
        TeamElo(
            team_id=team_id,
            season_id=season_id,
            rating=rating,
            last_updated=last_updated,
        )
        for (team_id, season_id), (rating, last_updated) in season_end_ratings.items()
    ])
    session.commit()

    # Keep SystemStats highest/lowest ELO pointers valid after the collapse.
    highest = session.execute(
        select(TeamElo).order_by(TeamElo.rating.desc()).limit(1)
    ).scalar_one_or_none()
    lowest = session.execute(
        select(TeamElo).order_by(TeamElo.rating.asc()).limit(1)
    ).scalar_one_or_none()
    latest_stats = session.execute(
        select(SystemStats).order_by(SystemStats.recorded_at.desc())
    ).scalars().first()
    if latest_stats is None:
        latest_stats = SystemStats()
        session.add(latest_stats)
    latest_stats.highest_elo_id = highest.elo_id if highest else None
    latest_stats.lowest_elo_id = lowest.elo_id if lowest else None
    session.commit()
    print("ELO and H2H calculation complete")