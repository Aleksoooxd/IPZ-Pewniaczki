from flask import Flask
from .config import Config
from .db import db
from .routes import main

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    app.register_blueprint(main)

    return app
