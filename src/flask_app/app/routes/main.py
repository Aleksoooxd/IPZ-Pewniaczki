"""Top-level routes: the landing page and the main match-day view."""

import datetime
from flask import Blueprint, render_template, request, redirect, url_for

main_bp = Blueprint("main", __name__)

from ..leagues_config import URL_TO_DISPLAY

LEAGUE_NAMES = URL_TO_DISPLAY  # url_code -> display name


@main_bp.route("/")
def home():
    """Render the application landing page."""
    return render_template("index.html")


@main_bp.route("/main")
def mainpage():
    """Render the main match-day view, defaulting to today's date.

    Reads an optional ``?date=`` parameter. When absent, redirects to the same
    route with today's date so the page always has a concrete day to display.
    Passes the league display-name map to the template.

    Args:
        None (reads the optional ``date`` request arg)

    Returns:
        flask.Response: The rendered ``MainPage.html`` or a redirect to it.
    """
    date_param = request.args.get("date")
    if not date_param:
        today = datetime.date.today().strftime("%Y-%m-%d")
        return redirect(url_for("main.mainpage", date=today))
    return render_template("MainPage.html", league_names=LEAGUE_NAMES)