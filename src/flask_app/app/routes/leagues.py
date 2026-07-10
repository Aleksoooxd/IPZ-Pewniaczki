import datetime

from sqlalchemy import or_
from flask import Blueprint, render_template, request, abort

from ..db import db
from ..models import FootballMatch, Team, League, TeamLeague, Season, TeamElo

leagues_bp = Blueprint("leagues", __name__)

LEAGUE_URL_MAP = {
    "Premierleague":        "premier league",
    "Bundesliga":           "bundesliga",
    "Eredivisie":           "eredivisie",
    "EthnikiKatigoria":     "ethniki katigoria",
    "FutbolLig1":           "futbol ligi 1",
    "JupiterLeague":        "jupiler league",
    "LaLiga":               "la liga",
    "Ligue1":               "ligue 1",
    "LigaI":                "liga i",
    "SerieA":               "serie a",
    "ScotishPremierLeague": "spremier league",
}

LEAGUE_NAME_TO_URL = {v: k for k, v in LEAGUE_URL_MAP.items()}


def _get_team_current_elo(team_id, season_id=None):
    from sqlalchemy import desc
    q = db.session.query(TeamElo).filter(TeamElo.team_id == team_id)
    if season_id:
        q = q.filter(TeamElo.season_id == season_id)
    obj = q.order_by(desc(TeamElo.last_updated)).first()
    return int(obj.rating) if obj else None


def calculate_standings(league_id, season_id=None, matchday_filter=None):
    standings = {}
    q = db.session.query(FootballMatch).filter(FootballMatch.league_id == league_id)
    if season_id:
        q = q.filter(FootballMatch.season_id == season_id)
    if matchday_filter:
        q = q.filter(or_(
            FootballMatch.home_matchday <= matchday_filter,
            FootballMatch.away_matchday <= matchday_filter,
        ))

    for m in q.order_by(FootballMatch.date, FootballMatch.home_matchday).all():
        for tid in (m.home_team_id, m.away_team_id):
            if tid not in standings:
                name = db.session.get(Team, tid).name
                standings[tid] = dict(points=0, played=0, wins=0, draws=0, losses=0,
                                      goals_for=0, goals_against=0, goal_diff=0,
                                      team_name=name, team_id=tid)
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
        try:
            td["elo_rating"] = _get_team_current_elo(td["team_id"], season_id=season_id)
        except Exception:
            td["elo_rating"] = None
    return sorted_s


@leagues_bp.route("/league/<league_code>")
def league_view(league_code):
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
            max_md = db.session.query(db.func.max(FootballMatch.home_matchday)).filter(
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
        standings_display = f"2004-{datetime.datetime.now().year % 100}"

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