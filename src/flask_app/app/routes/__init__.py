"""Blueprint registration for the Flask application.

Imports and re-exports every route blueprint so the app factory can register
them in one place.
"""

from .matches import matches_bp
from .leagues import leagues_bp
from .teams import teams_bp
from .api import api_bp
from .main import main_bp
from .stats import stats_bp

__all__ = ["matches_bp", "leagues_bp", "teams_bp", "api_bp", "main_bp", "stats_bp"]