
import json
import os
import secrets

class Config:

    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    BASE_DIR = os.path.dirname(__file__)
    LOCAL_DATABASE_FILE = os.path.join(BASE_DIR, 'local.db')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{LOCAL_DATABASE_FILE.replace(os.sep, '/')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LANGUAGES = ['pl','en']

    BABEL_DEFAULT_LOCALE = 'pl'
    BABEL_DEFAULT_TIMEZONE = 'Europe/Warsaw'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'