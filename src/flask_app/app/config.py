# src/flask_app/app/config.py
import os
import json
import urllib

class Config:

    SECRETS_FILE = os.path.join(os.path.dirname(__file__), 'secrets.json')

    try:
        with open(SECRETS_FILE, 'r') as f:
            secrets = json.load(f)
    except FileNotFoundError:
        print(f"Error: {SECRETS_FILE} not found. Please create it with your database credentials")
        secrets = {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {SECRETS_FILE}. Please check its format.")
        secrets = {}

    SERVER = secrets.get('SERVER', 'default_server')
    DATABASE = secrets.get('DATABASE', 'default_database')
    USERNAME = secrets.get('USERNAME', 'default_username')
    PASSWORD = secrets.get('PASSWORD', 'default_password')
    SECRET_KEY = secrets.get('SECRET_KEY', os.urandom(24).hex())

    ENCRYPT = 'yes'
    TRUST_SERVER_CERTIFICATE = 'no'
    TIMEOUT = 60

    params = urllib.parse.quote_plus(
        f"DRIVER=ODBC Driver 17 for SQL Server;"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={USERNAME};"
        f"PWD={PASSWORD};"
        f"Encrypt={ENCRYPT};"
        f"TrustServerCertificate={TRUST_SERVER_CERTIFICATE};"
        f"Connection Timeout={TIMEOUT}"
    )

    SQLALCHEMY_DATABASE_URI = f"mssql+pyodbc:///?odbc_connect={params}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LANGUAGES = ['en', 'de', 'es', 'pt', 'cs', 'da', 'pl', 'ja', 'sv', 'it', 'tr', 'hr','he']