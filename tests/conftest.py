"""Shared pytest fixtures.

The standings code (`src/flask_app/app/routes/leagues.py`) reaches into the
Flask-SQLAlchemy `db.session` directly, so it needs a real (but isolated) app
context + database. We point Config at a fresh in-memory SQLite DB per test so
the project's real `local.db` is never touched and tables don't leak between
tests.
"""

from sqlalchemy.pool import StaticPool

import pytest

from src.flask_app.app.config import Config


@pytest.fixture
def app():
    """Provide an isolated Flask app + in-memory SQLite DB for a test.

    Pushes an application context with a fresh in-memory SQLite database so the
    project's real ``local.db`` is never touched and tables do not leak between
    tests. Monkeypatches the module-level schema guards to no-ops so the real
    ``db.create_all()`` / ``db.drop_all()`` lifecycle runs cleanly. Yields the
    created ``application`` and tears down the session and schema afterwards.

    Yields:
        Flask: The created Flask application with an active app context.
    """
    # Redirect the app at an isolated in-memory SQLite DB. StaticPool keeps a
    # single shared connection so the in-memory DB survives across the session.
    Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    Config.SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }

    from src.flask_app.app import create_app
    import src.flask_app.app as app_module
    from src.flask_app.app.db import db

    app_module._ensure_round_column = lambda: None
    app_module._ensure_team_elo_collapsed = lambda: None

    application = create_app()
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
