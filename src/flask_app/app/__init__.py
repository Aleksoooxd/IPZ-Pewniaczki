import os
import json
import click
from flask import Flask, request, session, g, current_app
from flask.cli import with_appcontext
from .config import Config
from .db import db, babel
from .routes import matches_bp, leagues_bp, teams_bp, api_bp, main_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.jinja_env.add_extension('jinja2.ext.do')

    db.init_app(app)

    def get_locale():
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

    @app.cli.command("db-create")
    @with_appcontext
    def db_create():
        db.create_all()
        click.echo("Tabele utworzone.")

    @app.cli.command("db-drop")
    @click.confirmation_option(prompt="Usunąć WSZYSTKIE tabele?")
    @with_appcontext
    def db_drop():
        db.drop_all()
        click.echo("Tabele usunięte.")

    @app.cli.command("db-reset")
    @click.confirmation_option(prompt="Zresetować bazę (drop + create)?")
    @with_appcontext
    def db_reset():
        db.drop_all()
        db.create_all()
        click.echo("Baza zresetowana.")

    @app.cli.command("db-status")
    @with_appcontext
    def db_status():
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

    return app