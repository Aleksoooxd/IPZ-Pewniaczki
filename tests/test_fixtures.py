"""Regression tests for `process_fixtures` (footballScrap.py).

`process_fixtures` is the testable, network-free core of the fixtures pipeline:
it downloads nothing, just takes a fixtures-shaped DataFrame and stores
upcoming matches for tracked leagues into FutureMatch. These tests pin the
tracked-only filter, the season derivation, and idempotent re-runs.
"""

import datetime

import pandas as pd

from src.flask_app.app.db import db
from src.flask_app.app.models import Team, League, Season, FutureMatch
from src.scraping.footballScrap import process_fixtures


# Fixed reference "today" so the example May-2026 fixtures count as future.
AS_OF = datetime.date(2026, 1, 1)


def _fixtures_df():
    """Build a fixtures-shaped DataFrame for the process_fixtures tests.

    Returns a three-row DataFrame with two tracked divisions (E0 -> "premier
    league", B1 -> "jupiler league") and one untracked division (SP2) whose teams
    must be skipped. Used as the input to ``process_fixtures`` in every test.

    Returns:
        pandas.DataFrame: A fixtures-shaped DataFrame with tracked and untracked rows.
    """
    return pd.DataFrame([
        {'Div': 'E0', 'Date': '31/05/2026', 'Time': '17:30',
         'HomeTeam': 'Arsenal', 'AwayTeam': 'Chelsea'},
        {'Div': 'B1', 'Date': '30/05/2026', 'Time': '15:15',
         'HomeTeam': 'Gent', 'AwayTeam': 'Genk'},
        # Untracked division -> must be skipped, and its teams must not be created.
        {'Div': 'SP2', 'Date': '30/05/2026', 'Time': '15:15',
         'HomeTeam': 'Ceuta', 'AwayTeam': 'Albacete'},
    ])


def test_process_fixtures_stores_tracked_only(app):
    """Verify only tracked leagues/teams are stored and season is derived.

    Runs the pipeline once and asserts exactly two tracked fixtures are inserted,
    one untracked row is skipped, only the two tracked leagues are created, the
    season is derived as 2025/26 from the May 2026 dates, exactly four tracked
    teams exist, and the E0 fixture fields are stored correctly.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    inserted, skipped, errors = process_fixtures(db.session, _fixtures_df(), as_of=AS_OF)
    assert inserted == 2
    assert skipped == 1
    assert errors == 0

    # Only the two tracked fixtures are stored.
    assert db.session.query(FutureMatch).count() == 2

    # Leagues: only the two tracked codes; the SP2 league is NOT created.
    codes = {lg.code for lg in db.session.query(League).all()}
    assert codes == {'premier league', 'jupiler league'}

    # Season derived from the May 2026 date (season starts in August).
    seasons = {s.name for s in db.session.query(Season).all()}
    assert seasons == {'2025/26'}

    # Exactly the four tracked teams exist; Ceuta/Albacete are not added.
    assert db.session.query(Team).count() == 4

    # Spot-check the E0 fixture fields.
    fm = db.session.query(FutureMatch).join(League).filter(
        League.code == 'premier league'
    ).one()
    assert fm.date == datetime.date(2026, 5, 31)
    assert fm.time == '17:30'
    assert fm.season_id == db.session.query(Season).filter_by(
        name='2025/26'
    ).one().season_id


def test_process_fixtures_is_idempotent(app):
    """Verify re-running the pipeline inserts nothing new (idempotent).

    Running ``process_fixtures`` twice on the same data should return 0 inserted
    on the second run while still holding exactly two FutureMatch rows.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    process_fixtures(db.session, _fixtures_df(), as_of=AS_OF)
    inserted, skipped, errors = process_fixtures(db.session, _fixtures_df(), as_of=AS_OF)
    assert inserted == 0
    assert db.session.query(FutureMatch).count() == 2


def test_process_fixtures_returns_zero_for_empty(app):
    """Verify None and empty DataFrames are handled as zero work.

    Passing None or an empty DataFrame should return the (0, 0, 0) tuple of
    (inserted, skipped, errors) without erroring.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    assert process_fixtures(db.session, None, as_of=AS_OF) == (0, 0, 0)
    assert process_fixtures(db.session, pd.DataFrame(), as_of=AS_OF) == (0, 0, 0)


def test_process_fixtures_skips_unparsed_dates(app):
    """Verify rows with unparseable dates are skipped, not stored.

    A tracked-division row whose Date cannot be parsed should be skipped (count
    1) with no FutureMatch inserted.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    df = pd.DataFrame([
        {'Div': 'E0', 'Date': 'not-a-date', 'Time': '17:30',
         'HomeTeam': 'Arsenal', 'AwayTeam': 'Chelsea'},
    ])
    inserted, skipped, errors = process_fixtures(db.session, df, as_of=AS_OF)
    assert inserted == 0
    assert skipped == 1
    assert db.session.query(FutureMatch).count() == 0


def test_process_fixtures_skips_past_rows(app):
    """Verify past fixtures are skipped while future ones are inserted.

    With as_of set after the first fixture's date, the past row is skipped and
    the future row is inserted; the stored FutureMatch date reflects the future
    fixture.

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    as_of = datetime.date(2026, 6, 1)
    df = pd.DataFrame([
        {'Div': 'E0', 'Date': '31/05/2026', 'Time': '17:30',
         'HomeTeam': 'Arsenal', 'AwayTeam': 'Chelsea'},  # past -> skipped
        {'Div': 'E0', 'Date': '15/06/2026', 'Time': '20:00',
         'HomeTeam': 'Liverpool', 'AwayTeam': 'Tottenham'},  # future -> inserted
    ])
    inserted, skipped, errors = process_fixtures(db.session, df, as_of=as_of)
    assert inserted == 1
    assert skipped == 1
    assert db.session.query(FutureMatch).count() == 1
    assert db.session.query(FutureMatch).one().date == datetime.date(2026, 6, 15)


def test_process_fixtures_deletes_existing_past_future_match(app):
    """Verify a stale past FutureMatch is cleaned up by the pipeline.

    Seeds a FutureMatch already in the past relative to as_of, runs the pipeline
    with no new data, and asserts the stale fixture is deleted (count returns to
    0).

    Args:
        app (fixture): Isolated Flask app + in-memory DB providing db.session.

    Returns:
        None.
    """
    # Seed a FutureMatch that is now in the past relative to as_of.
    lg = League(code='premier league')
    season = Season(name='2025/26')
    t1 = Team(name='Arsenal')
    t2 = Team(name='Chelsea')
    db.session.add_all([lg, season, t1, t2])
    db.session.commit()
    db.session.add(FutureMatch(
        league_id=lg.league_id, season_id=season.season_id,
        date=datetime.date(2026, 5, 1),
        home_team_id=t1.team_id, away_team_id=t2.team_id,
    ))
    db.session.commit()
    assert db.session.query(FutureMatch).count() == 1

    # Running the pipeline (even with no new data) cleans up the stale fixture.
    process_fixtures(db.session, pd.DataFrame(), as_of=datetime.date(2026, 6, 1))
    assert db.session.query(FutureMatch).count() == 0
