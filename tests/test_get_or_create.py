"""Regression tests for get_or_create_league / get_or_create_season.

Both used a SELECT-then-INSERT pattern that raced under the concurrent scrape
(scrape_top_11 runs up to 6 threads). League codes are shared across seasons and
season names across leagues, so two workers could both try to INSERT the same
value and trip UNIQUE(league.code) / UNIQUE(season.name). The upsert with
ON CONFLICT DO NOTHING must keep each table duplicate-free and return the
canonical committed row.
"""

from src.flask_app.app.db import db
from src.flask_app.app.models import League, Season
from src.scraping.footballScrap import get_or_create_league, get_or_create_season


def test_get_or_create_league_creates_and_returns(app):
    """Verify a new league is created and its row is returned.

    Calling with a brand-new league code persists a League and returns a model
    instance whose ``league_id`` is set and whose ``code`` matches the input.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    lg = get_or_create_league(db.session, "premier league")
    assert lg.league_id is not None
    assert lg.code == "premier league"


def test_get_or_create_league_is_idempotent(app):
    """Verify repeated calls return the same league row (no duplicates).

    Calling ``get_or_create_league`` twice with the same code returns rows with
    identical ``league_id`` and leaves exactly one League with that code.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    first = get_or_create_league(db.session, "premier league")
    second = get_or_create_league(db.session, "premier league")
    assert first.league_id == second.league_id
    assert db.session.query(League).filter_by(code="premier league").count() == 1


def test_get_or_create_league_reuses_committed_row(app):
    """Verify an already-committed league row is reused, not re-inserted.

    Seeds a committed League, then calls ``get_or_create_league`` with the same
    code; the returned row keeps the original ``league_id`` and only one League
    exists.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    existing = League(code="premier league")
    db.session.add(existing)
    db.session.commit()
    existing_id = existing.league_id

    got = get_or_create_league(db.session, "premier league")
    assert got.league_id == existing_id
    assert db.session.query(League).filter_by(code="premier league").count() == 1


def test_get_or_create_season_creates_and_returns(app):
    """Verify a new season is created and its row is returned.

    Calling with a brand-new season name persists a Season and returns a model
    instance whose ``season_id`` is set and whose ``name`` matches the input.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    s = get_or_create_season(db.session, "2023/24")
    assert s.season_id is not None
    assert s.name == "2023/24"


def test_get_or_create_season_is_idempotent(app):
    """Verify repeated calls return the same season row (no duplicates).

    Calling ``get_or_create_season`` twice with the same name returns rows with
    identical ``season_id`` and leaves exactly one Season with that name.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    first = get_or_create_season(db.session, "2023/24")
    second = get_or_create_season(db.session, "2023/24")
    assert first.season_id == second.season_id
    assert db.session.query(Season).filter_by(name="2023/24").count() == 1


def test_get_or_create_season_reuses_committed_row(app):
    """Verify an already-committed season row is reused, not re-inserted.

    Seeds a committed Season, then calls ``get_or_create_season`` with the same
    name; the returned row keeps the original ``season_id`` and only one Season
    exists.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    existing = Season(name="2023/24")
    db.session.add(existing)
    db.session.commit()
    existing_id = existing.season_id

    got = get_or_create_season(db.session, "2023/24")
    assert got.season_id == existing_id
    assert db.session.query(Season).filter_by(name="2023/24").count() == 1
