"""Regression tests for `resolve_teams` (footballScrap.py).

`resolve_teams` replaced a get-or-create + INSERT pattern that raced under the
concurrent scrape (scrape_top_11 runs up to 6 threads against one SQLite file).
Teams are shared across leagues/seasons, so two workers could both try to INSERT
the same team name and trip UNIQUE(team.name). The upsert with
ON CONFLICT DO NOTHING must keep the table duplicate-free and return the
canonical committed rows.
"""

from src.flask_app.app.db import db
from src.flask_app.app.models import Team
from src.scraping.footballScrap import resolve_teams


def test_resolve_teams_creates_and_returns_rows(app):
    """Verify new teams are created and returned keyed by name.

    Resolving a list of new team names creates one Team per name, returns a dict
    keyed by name whose values have assigned ``team_id``s, and leaves exactly
    three teams in the DB.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    result = resolve_teams(db.session, ["Arsenal", "Chelsea", "Spurs"])
    assert set(result.keys()) == {"Arsenal", "Chelsea", "Spurs"}
    for team in result.values():
        assert team.team_id is not None
    assert db.session.query(Team).count() == 3


def test_resolve_teams_is_idempotent(app):
    """Verify re-resolution reuses existing ids and adds no duplicates.

    Resolving ["Arsenal", "Chelsea"] then ["Arsenal", "Chelsea", "Spurs"] keeps
    the original ids for Arsenal/Chelsea and ends with exactly three teams, no
    duplicates.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    first = resolve_teams(db.session, ["Arsenal", "Chelsea"])
    second = resolve_teams(db.session, ["Arsenal", "Chelsea", "Spurs"])
    # Existing teams keep their ids; no duplicates are created.
    assert first["Arsenal"].team_id == second["Arsenal"].team_id
    assert first["Chelsea"].team_id == second["Chelsea"].team_id
    assert db.session.query(Team).count() == 3


def test_resolve_teams_reuses_already_committed_row(app):
    """Verify an already-committed team is reused without a duplicate.

    Simulates a competing worker that committed "Stoke City" first; resolving
    ["Stoke City", "Burnley"] reuses the existing row (same id, one "Stoke City"
    row) and adds exactly one new team.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    # Simulate a "competing worker" that already committed a team before this
    # call runs with an overlapping name plus a brand-new one.
    other = Team(name="Stoke City")
    db.session.add(other)
    db.session.commit()
    existing_id = other.team_id

    result = resolve_teams(db.session, ["Stoke City", "Burnley"])

    # The existing row is reused (no IntegrityError, same id) and exactly one
    # "Stoke City" row exists despite the concurrent-looking insert.
    assert result["Stoke City"].team_id == existing_id
    assert result["Burnley"].team_id is not None
    assert db.session.query(Team).filter_by(name="Stoke City").count() == 1
    assert db.session.query(Team).count() == 2


def test_resolve_teams_skips_empty_and_none(app):
    """Verify None and empty-string names are skipped.

    Resolving [None, "", "Arsenal"] ignores the empty/None entries and returns a
    dict containing only "Arsenal", with exactly one team persisted.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    result = resolve_teams(db.session, [None, "", "Arsenal"])
    assert list(result.keys()) == ["Arsenal"]
    assert db.session.query(Team).count() == 1


def test_resolve_teams_empty_input_returns_empty(app):
    """Verify an empty input list returns an empty dict.

    Resolving an empty list should return an empty dict (no teams created) rather
    than erroring.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    assert resolve_teams(db.session, []) == {}
