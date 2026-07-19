"""Unit tests for `calculate_standings` (routes/leagues.py:37).

`calculate_standings` reads from the Flask-SQLAlchemy `db.session`, so each test
runs inside the isolated in-memory app context provided by the `app` fixture.
"""

import datetime

from src.flask_app.app.db import db
from src.flask_app.app.models import Team, League, Season, FootballMatch, TeamElo
from src.flask_app.app.routes.leagues import calculate_standings


def _match(home_id, away_id, league_id, season_id, rnd, fthg, ftag, result, date):
    """Construct a FootballMatch row with the given attributes.

    Convenience factory that builds a ``FootballMatch`` from its component
    fields (team ids, league/season ids, round, scores, result and date) for use
    in the standings seed helpers.

    Args:
        home_id (int): Home team id.
        away_id (int): Away team id.
        league_id (int): League id.
        season_id (int): Season id.
        rnd (int): Match round number.
        fthg (int): Full-time home goals.
        ftag (int): Full-time away goals.
        result (str): Result code ("H", "D", or "A").
        date (datetime.date): Match date.

    Returns:
        FootballMatch: The constructed match instance (not yet committed).
    """
    return FootballMatch(
        league_id=league_id,
        season_id=season_id,
        round=rnd,
        date=date,
        home_team_id=home_id,
        away_team_id=away_id,
        fthg=fthg,
        ftag=ftag,
        result=result,
    )


def _seed_minimal_league(app):
    """Seed a minimal league with three teams into the in-memory DB.

    Creates a "premier league" league, a 2023 season, and three teams (Arsenal,
    Chelsea, Spurs), commits them, and returns the created objects for further
    use in tests.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        tuple: (League, Season, Team, Team, Team) for the seeded league, season
            and three teams.
    """
    league = League(league_id=1, code="premier league")
    season = Season(season_id=1, name="2023")
    t1 = Team(team_id=1, name="Arsenal")
    t2 = Team(team_id=2, name="Chelsea")
    t3 = Team(team_id=3, name="Spurs")
    db.session.add_all([league, season, t1, t2, t3])
    db.session.commit()
    return league, season, t1, t2, t3


# Full 6-match round-robin-ish season used by the ordering tests.
_SEASON_MATCHES = [
    (1, 2, 1, 2, 0, "H", datetime.date(2023, 8, 11)),
    (3, 1, 1, 1, 1, "D", datetime.date(2023, 8, 12)),
    (2, 3, 2, 3, 1, "H", datetime.date(2023, 8, 18)),
    (1, 3, 2, 1, 0, "H", datetime.date(2023, 8, 19)),
    (2, 1, 3, 2, 1, "H", datetime.date(2023, 8, 25)),
    (3, 2, 3, 4, 0, "H", datetime.date(2023, 8, 26)),
]


def _seed_full_season(app):
    """Seed a full 6-match season plus ELO snapshots for ordering tests.

    Builds on ``_seed_minimal_league``, adds the six matches from
    ``_SEASON_MATCHES`` (with explicit match ids), and adds one TeamElo snapshot
    per team for season 1, then commits. Used by the standings/ordering tests.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    _seed_minimal_league(app)
    for i, (h, a, rnd, hg, ag, res, d) in enumerate(_SEASON_MATCHES, start=1):
        m = _match(h, a, 1, 1, rnd, hg, ag, res, d)
        m.match_id = i
        db.session.add(m)
    db.session.add_all([
        TeamElo(team_id=1, season_id=1, rating=1650.0, last_updated=datetime.date(2023, 8, 26)),
        TeamElo(team_id=2, season_id=1, rating=1580.0, last_updated=datetime.date(2023, 8, 26)),
        TeamElo(team_id=3, season_id=1, rating=1505.0, last_updated=datetime.date(2023, 8, 26)),
    ])
    db.session.commit()


def test_full_season_standings_and_ordering(app):
    """Verify a full season's standings and per-team stats/ordering.

    Seeds the full season and asserts teams are ordered Arsenal, Chelsea, Spurs
    by points, that Arsenal's full stat line (position, points, played, wins,
    draws, losses, goals for/against, goal difference, and ELO rating) matches
    the expected values, and that Chelsea/Spurs have the expected points and
    goal difference.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    _seed_full_season(app)

    standings = calculate_standings(league_id=1, season_id=1)
    by_name = {row["team_name"]: row for row in standings}

    # Points: Arsenal 7, Chelsea 6, Spurs 4.
    assert [r["team_name"] for r in standings] == ["Arsenal", "Chelsea", "Spurs"]

    arsenal = by_name["Arsenal"]
    assert arsenal["position"] == 1
    assert arsenal["points"] == 7
    assert arsenal["played"] == 4
    assert arsenal["wins"] == 2
    assert arsenal["draws"] == 1
    assert arsenal["losses"] == 1
    assert arsenal["goals_for"] == 5
    assert arsenal["goals_against"] == 3
    assert arsenal["goal_diff"] == 2
    assert arsenal["elo_rating"] == 1650

    chelsea = by_name["Chelsea"]
    assert chelsea["position"] == 2
    assert chelsea["points"] == 6
    assert chelsea["goal_diff"] == -3

    spurs = by_name["Spurs"]
    assert spurs["position"] == 3
    assert spurs["points"] == 4


def test_matchday_filter_counts_only_up_to_round(app):
    """Verify matchday_filter restricts standings to rounds <= filter.

    With matchday_filter=1 only the first two matches count, so Arsenal leads on
    4 points, Spurs has 1, and Chelsea has 0, in that order.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    _seed_full_season(app)

    # round <= 1 keeps only the first two matches (Arsenal 2-0 Chelsea, Spurs 1-1 Arsenal).
    standings = calculate_standings(league_id=1, season_id=1, matchday_filter=1)
    by_name = {row["team_name"]: row for row in standings}

    assert [r["team_name"] for r in standings] == ["Arsenal", "Spurs", "Chelsea"]
    assert by_name["Arsenal"]["points"] == 4
    assert by_name["Arsenal"]["played"] == 2
    assert by_name["Spurs"]["points"] == 1
    assert by_name["Chelsea"]["points"] == 0


def test_season_filter_excludes_other_seasons(app):
    """Verify season_id filter excludes matches from other seasons.

    Seeds one match in season 1 and one in season 2 between the same teams, then
    asserts a season-1 filtered standings only counts the season-1 match (each
    team played once, 3 points for the winner).

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    _seed_minimal_league(app)

    # One match in season 1, one in season 2 between the same teams.
    m_s1 = _match(1, 2, 1, 1, 1, 1, 0, "H", datetime.date(2023, 8, 11))
    m_s1.match_id = 1
    m_s2 = _match(1, 2, 1, 2, 1, 5, 0, "H", datetime.date(2024, 8, 1))
    m_s2.match_id = 2
    db.session.add_all([m_s1, m_s2])
    db.session.commit()

    standings = calculate_standings(league_id=1, season_id=1)
    by_name = {row["team_name"]: row for row in standings}

    # Only the season-1 match counts.
    assert by_name["Arsenal"]["played"] == 1
    assert by_name["Arsenal"]["points"] == 3
    assert by_name["Chelsea"]["played"] == 1


def test_tiebreak_by_goal_difference(app):
    """Verify tied points are broken by goal difference.

    Two teams each win 3-0-equivalent matches against fillers (1-0 and 2-0);
    both have 3 points but Chelsea (2-0) ranks above Arsenal (1-0) on goal
    difference.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    # Alpha beats a filler 1-0; Bravo beats a filler 2-0. Both 3 pts -> Bravo
    # ranks higher on goal difference.
    league = League(league_id=1, code="premier league")
    season = Season(season_id=1, name="2023/24")
    alpha = Team(team_id=1, name="Arsenal")
    bravo = Team(team_id=2, name="Chelsea")
    filler_a = Team(team_id=3, name="Liverpool")
    filler_b = Team(team_id=4, name="Manchester United")
    db.session.add_all([league, season, alpha, bravo, filler_a, filler_b])
    db.session.commit()

    db.session.add_all([
        _match(1, 3, 1, 1, 1, 1, 0, "H", datetime.date(2023, 8, 11)),
        _match(2, 4, 1, 1, 1, 2, 0, "H", datetime.date(2023, 8, 12)),
    ])
    db.session.commit()

    standings = calculate_standings(league_id=1, season_id=1)
    by_name = {row["team_name"]: row for row in standings}

    assert by_name["Chelsea"]["position"] < by_name["Arsenal"]["position"]
    assert by_name["Chelsea"]["goal_diff"] == 2
    assert by_name["Arsenal"]["goal_diff"] == 1


def test_elo_rating_taken_from_latest_season_snapshot(app):
    """Verify ELO rating comes from the right season/latest snapshot.

    Seeds two ELO snapshots for Arsenal (season 1 older, season 2 newer) and one
    for Chelsea. A season-1 filtered standings uses the season-1 snapshot, while
    a no-filter standings uses the most recent snapshot by last_updated.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    _seed_minimal_league(app)
    # Need at least one match so both teams appear in the standings table.
    opener = _match(1, 2, 1, 1, 1, 2, 0, "H", datetime.date(2023, 8, 11))
    opener.match_id = 1
    db.session.add(opener)
    db.session.commit()
    # Arsenal has one snapshot per season (unique on (team_id, season_id)).
    # Season 2's rating is newer, so it should win when no season is filtered.
    db.session.add_all([
        TeamElo(team_id=1, season_id=1, rating=1642.0, last_updated=datetime.date(2023, 8, 20)),
        TeamElo(team_id=1, season_id=2, rating=1700.0, last_updated=datetime.date(2024, 8, 20)),
        TeamElo(team_id=2, season_id=1, rating=1550.0, last_updated=datetime.date(2023, 8, 20)),
    ])
    db.session.commit()

    # Season-filtered: only the season-1 snapshot is in scope.
    season_standings = calculate_standings(league_id=1, season_id=1)
    by_season = {row["team_name"]: row for row in season_standings}
    assert by_season["Arsenal"]["elo_rating"] == 1642
    assert by_season["Chelsea"]["elo_rating"] == 1550

    # No season filter: the most recent snapshot (by last_updated) wins.
    all_standings = calculate_standings(league_id=1)
    by_all = {row["team_name"]: row for row in all_standings}
    assert by_all["Arsenal"]["elo_rating"] == 1700
