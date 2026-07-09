
import json
import os

class Config:

    BASE_DIR = os.path.dirname(__file__)
    SECRETS_FILE = os.path.join(BASE_DIR, 'secrets.json')
    LOCAL_DATABASE_FILE = os.path.join(BASE_DIR, 'local.db')

    try:
        with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
            secrets = json.load(f)
    except FileNotFoundError:
        secrets = {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {SECRETS_FILE}. Please check its format.")
        secrets = {}

    SECRET_KEY = secrets.get('SECRET_KEY', os.urandom(24).hex())
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{LOCAL_DATABASE_FILE.replace(os.sep, '/')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LANGUAGES = ['en']