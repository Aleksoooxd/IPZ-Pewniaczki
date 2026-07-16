"""Application configuration for the Flask app.

Provides the ``Config`` class consumed by ``app.factory_create_app``.
Paths, the SQLAlchemy URI, and i18n (Flask-Babel) settings live here.
"""

import json
import os
import secrets

class Config:
    """Base configuration loaded by the Flask application factory.

    Builds the SQLite database URI from the module directory, generates a
    secret key (from the environment or a fresh token), and configures
    Flask-Babel for Polish/English with Polish as the default locale.
    """

    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    BASE_DIR = os.path.dirname(__file__)
    LOCAL_DATABASE_FILE = os.path.join(BASE_DIR, 'local.db')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{LOCAL_DATABASE_FILE.replace(os.sep, '/')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "pool_pre_ping": True,
    }

    LANGUAGES = ['pl','en']

    BABEL_DEFAULT_LOCALE = 'pl'
    BABEL_DEFAULT_TIMEZONE = 'Europe/Warsaw'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'