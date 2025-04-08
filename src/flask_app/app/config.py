import urllib

class Config:
    SERVER = 'ipz-pewniaczki.database.windows.net'
    DATABASE = 'ipz-pewniaczki-db'
    USERNAME = 'admin_'
    PASSWORD = 'IPZ_pewniaczki'

    ENCRYPT = 'yes'
    TRUST_SERVER_CERTIFICATE = 'no'
    TIMEOUT = 30

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


