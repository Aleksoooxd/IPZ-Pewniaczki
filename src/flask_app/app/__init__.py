import click
from flask import Flask, request, session, g, current_app
from flask.cli import with_appcontext
from sqlalchemy import inspect, text
from .config import Config
from .db import db, babel
from .routes import matches_bp, leagues_bp, teams_bp, api_bp, main_bp, stats_bp


def _ensure_round_column():
    """Ensure the canonical ``round`` column exists and is back-filled.

    Fresh databases created via ``db.create_all()`` already include the column,
    so for them this is a no-op. For legacy databases the column is added with
    an ``ALTER TABLE`` (if missing) on both ``football_match`` and
    ``future_match``, then any null rounds are back-filled as
    ``MAX(home_matchday, away_matchday)``.

    Called at app startup and from the ``db-*`` CLI commands so existing
    deployments self-heal without a manual migration step.

    Returns:
        None:
    """
    inspector = inspect(db.engine)
    for table in ("football_match", "future_match"):
        if table not in inspector.get_table_names():
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "round" in cols:
            continue
        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN round INTEGER"))
        db.session.commit()
    # Backfill canonical round for already-scraped rows: round = max(home, away).
    db.session.execute(text(
        "UPDATE football_match "
        "SET round = MAX(home_matchday, away_matchday) "
        "WHERE round IS NULL AND home_matchday IS NOT NULL AND away_matchday IS NOT NULL"
    ))
    db.session.commit()


def _ensure_team_elo_collapsed():
    """Collapse legacy per-match TeamElo rows to one season-end snapshot per team.

    The ELO calculator now writes a single TeamElo row per (team, season).
    Older deployments accumulated 2 rows per match; this dedupes them to one
    per (team, season) (keeping the latest by ``elo_id``) and creates the
    unique index (idempotent). Self-heals at startup so existing DBs don't
    need a manual step.

    Returns:
        None:
    """
    inspector = inspect(db.engine)
    if "team_elo" not in inspector.get_table_names():
        return
    indexes = {ix["name"] for ix in inspector.get_indexes("team_elo")}
    if "uq_team_elo_team_season" in indexes:
        return  # already collapsed + indexed
    # Keep one row per (team, season) — the latest (highest elo_id == latest date).
    db.session.execute(text(
        "DELETE FROM team_elo WHERE elo_id NOT IN ("
        "SELECT MAX(elo_id) FROM team_elo GROUP BY team_id, season_id)"
    ))
    db.session.commit()
    db.session.execute(text(
        "CREATE UNIQUE INDEX uq_team_elo_team_season ON team_elo(team_id, season_id)"
    ))
    db.session.commit()


def create_app():
    """Application factory: build and configure the Flask app.

    Loads :class:`Config`, enables the Jinja ``do`` extension, initialises
    SQLAlchemy and Flask-Babel (with a request/locale selector), registers all
    blueprints, runs the schema self-heal helpers at startup, and wires up the
    database / pipeline CLI commands.

    Args:
        None

    Returns:
        flask.Flask: The fully configured application instance.
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    app.jinja_env.add_extension('jinja2.ext.do')

    db.init_app(app)

    def get_locale():
        """Resolve the active UI locale for Flask-Babel.

        Honours an explicit ``?lang=`` request argument (persisting it in the
        session if valid), then a stored session language, and finally falls back
        to the best match from the ``Accept-Language`` header (default Polish).

        Args:
            None

        Returns:
            str: One of the configured ``LANGUAGES`` codes (``'pl'`` or
            ``'en'``).
        """
        if 'lang' in request.args:
            lang = request.args['lang']
            if lang in current_app.config['LANGUAGES']:
                session['lang'] = lang
        lang = session.get('lang')
        if lang and lang in current_app.config['LANGUAGES']:
            return lang
        return request.accept_languages.best_match(
            current_app.config['LANGUAGES'], default='pl'
        )

    babel.init_app(app, locale_selector=get_locale)

    @app.before_request
    def before_request():
        """Set ``g.lang`` for every request before handlers run.

        Re-reads an explicit ``?lang=`` argument into the session, then resolves
        the active language (session -> ``Accept-Language`` header) and stores it
        on ``g.lang``, defaulting to Polish when none is valid.

        Args:
            None

        Returns:
            None:
        """
        if 'lang' in request.args:
            requested_lang = request.args['lang']
            if requested_lang in current_app.config['LANGUAGES']:
                session['lang'] = requested_lang
        g.lang = session.get(
            'lang',
            request.accept_languages.best_match(current_app.config['LANGUAGES'])
        )
        if not g.lang or g.lang not in current_app.config['LANGUAGES']:
            g.lang = 'pl'

    @app.context_processor
    def inject_helpers():
        """Inject helper callables/functions into every template context.

        Exposes ``gettext`` as ``_`` (for translations) and a
        ``lang_code_to_display_name`` lambda mapping a language code to its
        human-readable name.

        Args:
            None

        Returns:
            dict: Template-context variables (``_`` and the name mapper).
        """
        from flask_babel import gettext
        lang_map = {'pl': 'Polski', 'en': 'English'}
        return dict(
            _=gettext,
            lang_code_to_display_name=lambda code: lang_map.get(code, code),
        )

    app.register_blueprint(main_bp)
    app.register_blueprint(matches_bp)
    app.register_blueprint(leagues_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(stats_bp)

    with app.app_context():
        _ensure_round_column()
        _ensure_team_elo_collapsed()

    @app.cli.command("db-create")
    @with_appcontext
    def db_create():
        """Create all database tables and run the self-heal helpers."""
        db.create_all()
        _ensure_round_column()
        _ensure_team_elo_collapsed()
        click.echo("Tabele utworzone.")

    @app.cli.command("db-drop")
    @click.confirmation_option(prompt="Usunąć WSZYSTKIE tabele?")
    @with_appcontext
    def db_drop():
        """Drop every database table (with a confirmation prompt)."""
        db.drop_all()
        click.echo("Tabele usunięte.")

    @app.cli.command("db-reset")
    @click.confirmation_option(prompt="Zresetować bazę (drop + create)?")
    @with_appcontext
    def db_reset():
        """Drop and recreate all tables, then run the self-heal helpers."""
        db.drop_all()
        db.create_all()
        _ensure_round_column()
        _ensure_team_elo_collapsed()
        click.echo("Baza zresetowana.")

    @app.cli.command("db-add-round")
    @with_appcontext
    def db_add_round():
        """Add/back-fill the canonical ``round`` column on legacy tables."""
        _ensure_round_column()
        click.echo("Kolumna 'round' dodana/uzupełniona.")

    @app.cli.command("db-collapse-elo")
    @with_appcontext
    def db_collapse_elo():
        """Collapse per-match TeamElo rows to season-end snapshots."""
        _ensure_team_elo_collapsed()
        click.echo("TeamElo zredukowane do migawek na koniec sezonu.")

    @app.cli.command("db-status")
    @with_appcontext
    def db_status():
        """Print every table name and its column list to the console."""
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            click.echo(f"Tabele w bazie ({len(tables)}):")
            for t in tables:
                cols = [c['name'] for c in inspector.get_columns(t)]
                click.echo(f"  • {t}  [{', '.join(cols)}]")
        else:
            click.echo("Baza jest pusta — brak tabel.")

    @app.cli.command("run-elo")
    @with_appcontext
    def run_elo():
        """Recompute all ELO ratings and head-to-head form."""
        from src.calculations.elo_calculator import process_all_matches_for_elo
        process_all_matches_for_elo(db.session)
        click.echo("ELO obliczone.")

    @app.cli.command("run-predict")
    @with_appcontext
    def run_predict():
        """Run the full canonical prediction pipeline (past + future)."""
        from src.calculations.predict_all_future import run_predictions
        run_predictions(db.session, db.engine)
        click.echo("Predykcje gotowe (model kanoniczny XGBoost).")

    @app.cli.command("run-predict-future")
    @with_appcontext
    def run_predict_future():
        """Run the canonical prediction pipeline (alias for ``run-predict``)."""
        from src.calculations.predict_all_future import run_predictions
        run_predictions(db.session, db.engine)
        click.echo("Predykcje przyszłych meczów gotowe (model kanoniczny XGBoost).")

    @app.cli.command("rename-teams")
    @with_appcontext
    def rename_teams():
        """Normalise team names against ``mapping.json``."""
        from src.scraping.rename_team import rename
        rename(db.session)
        click.echo("Nazwy drużyn znormalizowane według mapping.json.")

    return app