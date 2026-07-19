"""Shared Flask extensions: the SQLAlchemy and Babel instances.

Importing this module creates the single ``db`` (Flask-SQLAlchemy) and
``babel`` (Flask-Babel) objects used across the application and its models.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel

db = SQLAlchemy()
babel = Babel()