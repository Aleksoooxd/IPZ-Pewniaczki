from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

    return app