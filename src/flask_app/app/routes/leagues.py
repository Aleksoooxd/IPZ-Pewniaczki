"""League routes: league overview with season/matchday standings."""

import datetime

from flask import Blueprint, render_template, request, abort

from ..db import db
from ..models import FootballMatch, Team, League, TeamLeague, Season, TeamElo
from ..leagues_config import URL_TO_DB, DB_TO_URL

leagues_bp = Blueprint("leagues", __name__)

# Single source of truth: src/flask_app/app/leagues_config.py
LEAGUE_URL_MAP = URL_TO_DB          # url_code -> db_code
LEAGUE_NAME_TO_URL = DB_TO_URL      # db_code -> url_code


def _get_team_current_elo(team_id, season_id=None):
    """Return a team's most recent ELO rating.

    Args:
        team_id (int): ``Team.team_id`` to look up.
        season_id (int, optional): When given, restrict to that season's
            ``TeamElo`` rows. Defaults to None (most recent across seasons).

    Returns:
        int or None: The latest ``rating`` (cast to int), or ``None`` if no
        ELO snapshot exists.
    """
    from sqlalchemy import desc
    q = db.session.query(TeamElo).filter(TeamElo.team_id == team_id)
    if season_id:
        q = q.filter(TeamElo.season_id == season_id)
    obj = q.order_by(desc(TeamElo.last_updated)).first()
    return int(obj.rating) if obj else None


def calculate_standings(league_id, season_id=None, matchday_filter=None):
    """Compute league standings from played matches.

    Aggregates points, played, wins/draws/losses and goals for every team in
    the league (optionally scoped to a season and/or up to a given round), then
    sorts by points, goal difference, goals-for and name, assigning positions
    and attaching the latest ELO rating per team.

    Args:
        league_id (int): ``League.league_id`` to compute standings for.
        season_id (int, optional): Restrict to a single season. Defaults to None
            (all seasons).
        matchday_filter (int, optional): Only count matches with
            ``round <= matchday_filter``. Defaults to None (all rounds).

    Returns:
        list[dict]: Standings rows, each with ``position``, ``team_name``,
        ``team_id``, ``points``, ``played``, ``wins``, ``draws``, ``losses``,
        ``goals_for``, ``goals_against``, ``goal_diff`` and ``elo_rating``.
    """
    standings = {}
    q = db.session.query(FootballMatch).filter(FootballMatch.league_id == league_id)
    if season_id:
        q = q.filter(FootballMatch.season_id == season_id)
    if matchday_filter:
        q = q.filter(FootballMatch.round <= matchday_filter)

    matches = q.order_by(FootballMatch.date, FootballMatch.round).all()

    team_ids = {m.home_team_id for m in matches} | {m.away_team_id for m in matches}
    teams_map = {t.team_id: t.name for t in db.session.query(Team).filter(Team.team_id.in_(team_ids)).all()}

    elo_map = {}
    if team_ids:
        elo_q = db.session.query(TeamElo).filter(TeamElo.team_id.in_(team_ids))
        if season_id:
            elo_q = elo_q.filter(TeamElo.season_id == season_id)
        for elo in elo_q.order_by(TeamElo.last_updated.desc()).all():
            elo_map.setdefault(elo.team_id, int(elo.rating))

    for tid in team_ids:
        standings[tid] = dict(points=0, played=0, wins=0, draws=0, losses=0,
                               goals_for=0, goals_against=0, goal_diff=0,
                               team_name=teams_map.get(tid, "?"), team_id=tid)

    for m in matches:
        h, a = standings[m.home_team_id], standings[m.away_team_id]
        h["played"] += 1; a["played"] += 1
        hg, ag = m.fthg or 0, m.ftag or 0
        h["goals_for"] += hg; h["goals_against"] += ag
        a["goals_for"] += ag; a["goals_against"] += hg
        h["goal_diff"] = h["goals_for"] - h["goals_against"]
        a["goal_diff"] = a["goals_for"] - a["goals_against"]
        if m.result == "H":
            h["points"] += 3; h["wins"] += 1; a["losses"] += 1
        elif m.result == "D":
            h["points"] += 1; a["points"] += 1; h["draws"] += 1; a["draws"] += 1
        elif m.result == "A":
            a["points"] += 3; a["wins"] += 1; h["losses"] += 1

    sorted_s = sorted(standings.values(),
                       key=lambda x: (-x["points"], -x["goal_diff"], -x["goals_for"], x["team_name"]))
    for i, td in enumerate(sorted_s):
        td["position"] = i + 1
        td["elo_rating"] = elo_map.get(td["team_id"])
    return sorted_s


@leagues_bp.route("/league/<league_code>")
def league_view(league_code):
    """Render a league's season selector, teams and standings.

    Maps the URL league code to its DB code, resolves the league, lists its
    available seasons, and (when a season/matchday is selected) computes the
    standings via :func:`calculate_standings`. Renders ``league_view.html``.

    Args:
        league_code (str): URL segment identifying the league (e.g. ``"LaLiga"``).

    Returns:
        flask.Response: The rendered ``league_view.html``, or a 404 abort for
        an unknown league code.
    """
    db_code = LEAGUE_URL_MAP.get(league_code)
    if not db_code:
        abort(404, description=f"Nieznana liga: {league_code}")

    league = League.query.filter_by(code=db_code).first_or_404()
    available_seasons = [s[0] for s in db.session.query(Season.name).order_by(Season.name.desc()).all()]

    selected_season_name = request.args.get("season")
    selected_matchday   = request.args.get("matchday", type=int)

    teams_query = db.session.query(Team).join(TeamLeague).filter(TeamLeague.league_id == league.league_id)
    current_standings = []
    standings_display = "Wybierz sezon"
    available_matchdays = []

    if selected_season_name and selected_season_name != "all_seasons":
        season_obj = Season.query.filter_by(name=selected_season_name).first()
        if season_obj:
            teams_query = teams_query.filter(TeamLeague.season_id == season_obj.season_id)
            max_md = db.session.query(db.func.max(FootballMatch.round)).filter(
                FootballMatch.league_id == league.league_id,
                FootballMatch.season_id == season_obj.season_id,
            ).scalar()
            if max_md:
                available_matchdays = list(range(1, max_md + 1))
            current_standings = calculate_standings(league.league_id, season_obj.season_id, selected_matchday)
            standings_display = selected_season_name
        else:
            selected_season_name = "all_seasons"

    if selected_season_name == "all_seasons" or not selected_season_name:
        selected_season_name = "all_seasons"
        current_standings = calculate_standings(league.league_id)
        # Derive the real span from the data instead of hardcoding a start year.
        start_year = min(available_seasons)[:4] if available_seasons else None
        standings_display = (
            f"{start_year}-{datetime.datetime.now().year % 100}"
            if start_year else "Wszystkie sezony"
        )

    teams = teams_query.distinct().order_by(Team.name).all()

    return render_template(
        "league_view.html",
        league=league,
        teams=teams,
        league_name_to_url=LEAGUE_NAME_TO_URL,
        available_seasons=available_seasons,
        selected_season=selected_season_name,
        standings=current_standings,
        standings_season_display_name=standings_display,
        available_matchdays=available_matchdays,
        selected_matchday=selected_matchday,
    )