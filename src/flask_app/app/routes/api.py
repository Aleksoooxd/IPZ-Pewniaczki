import datetime

from sqlalchemy.orm import aliased
from flask import Blueprint, jsonify, request

from ..db import db
from ..models import FootballMatch, FutureMatch, Team, League

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/matches")
def get_matches():
    """Return all past and future matches on a given date as JSON.

    Requires a ``?date=YYYY-MM-DD`` query parameter. Past matches include
    their final scores; future matches report ``home_goals``/``away_goals``
    as ``null``. Both sets are unioned into a single list, each entry tagged
    with ``match_type`` of ``"past"`` or ``"future"``.

    Args:
        None (reads the ``date`` request query parameter)

    Returns:
        flask.Response: A JSON list of match dicts, or a 400 error object
        when the date parameter is missing or malformed.
    """
    date_param = request.args.get("date")
    if not date_param:
        return jsonify({"error": "Missing 'date' parameter"}), 400

    try:
        match_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    def _base(model, is_future):
        """Build a base match query for one match model.

        Projects the match id/date, both team names and ids (via aliased
        ``Team`` joins), the league code, and the home/away goals. For future
        matches the goal columns are emitted as ``NULL`` literals.

        Args:
            model: The match ORM model (``FootballMatch`` or ``FutureMatch``).
            is_future (bool): True when ``model`` is the future model, in which
                case goals are rendered as ``NULL``.

        Returns:
            sqlalchemy.orm.Query: A partially-built query filtered to
            ``model.date == match_date``, ready to be union-ed / executed.
        """
        home_goals = db.literal(None) if is_future else model.fthg
        away_goals = db.literal(None) if is_future else model.ftag
        return db.session.query(
            model.match_id, model.date,
            HomeTeam.name.label("home_team"),
            HomeTeam.team_id.label("home_team_id"),
            AwayTeam.name.label("away_team"),
            AwayTeam.team_id.label("away_team_id"),
            League.code.label("league"),
            home_goals.label("home_goals"),
            away_goals.label("away_goals"),
        ).join(HomeTeam, model.home_team_id == HomeTeam.team_id
        ).join(AwayTeam, model.away_team_id == AwayTeam.team_id
        ).join(League, model.league_id == League.league_id
        ).filter(model.date == match_date)

    matches = _base(FootballMatch, False).union_all(_base(FutureMatch, True)).all()

    return jsonify([
        dict(
            match_id=m.match_id,
            match_type="past" if m.home_goals is not None else "future",
            date=m.date.strftime("%Y-%m-%d"),
            home_team=m.home_team, home_team_id=m.home_team_id,
            away_team=m.away_team, away_team_id=m.away_team_id,
            league=m.league,
            home_goals=m.home_goals, away_goals=m.away_goals,
        ) for m in matches
    ])