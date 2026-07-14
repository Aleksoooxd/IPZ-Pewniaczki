from sqlalchemy import select
from flask import Blueprint, render_template

from ..db import db
from ..models import (
    SystemStats, TeamElo, FootballMatch, Team, Season, League, TeamLeague
)

stats_bp = Blueprint("stats", __name__)

# Mapowanie League.code (wartość w bazie) -> segment używany w URL /league/<league_code>/...
# Odwrotność LEAGUE_URL_MAP z routes/teams.py
DB_CODE_TO_URL_CODE = {
    "premier league": "Premierleague",
    "bundesliga": "Bundesliga",
    "eredivisie": "Eredivisie",
    "ethniki katigoria": "EthnikiKatigoria",
    "futbol ligi 1": "FutbolLig1",
    "jupiler league": "JupiterLeague",
    "la liga": "LaLiga",
    "ligue 1": "Ligue1",
    "liga i": "LigaI",
    "serie a": "SerieA",
    "spremier league": "ScotishPremierLeague",
}


def _find_league_for_team_season(team_id, season_id):
    """Znajduje ligę, w której drużyna grała w danym sezonie."""
    team_league = db.session.execute(
        select(TeamLeague, League)
        .join(League, League.league_id == TeamLeague.league_id)
        .where(
            TeamLeague.team_id == team_id,
            TeamLeague.season_id == season_id,
        )
        .limit(1)
    ).first()
    return team_league[1] if team_league else None


def _build_team_link(team, season):
    """
    Buduje dane potrzebne do url_for('teams.team_view', ...)
    Zwraca dict albo None jeśli nie da się ustalić ligi.
    """
    league = _find_league_for_team_season(team.team_id, season.season_id)
    if not league:
        return None

    league_url_code = DB_CODE_TO_URL_CODE.get(league.code, league.code)
    season_url = season.name.replace("/", " ")

    return {
        "league_code": league_url_code,
        "team_name": team.name,
        "season_name": season_url,
    }


@stats_bp.route("/stats")
def system_stats():
    latest_stats = db.session.execute(
        select(SystemStats)
        .order_by(SystemStats.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_stats is None:
        return render_template("system_stats.html", stats=None)

    highest_elo_link = None
    lowest_elo_link = None
    highest_elo_row = None
    lowest_elo_row = None
    highest_goal_match = None
    biggest_upset_match = None

    if latest_stats.highest_elo_id:
        row = db.session.execute(
            select(TeamElo, Team, Season)
            .join(Team, Team.team_id == TeamElo.team_id)
            .join(Season, Season.season_id == TeamElo.season_id)
            .where(TeamElo.elo_id == latest_stats.highest_elo_id)
        ).first()
        if row:
            highest_elo_row = row
            highest_elo_link = _build_team_link(row[1], row[2])

    if latest_stats.lowest_elo_id:
        row = db.session.execute(
            select(TeamElo, Team, Season)
            .join(Team, Team.team_id == TeamElo.team_id)
            .join(Season, Season.season_id == TeamElo.season_id)
            .where(TeamElo.elo_id == latest_stats.lowest_elo_id)
        ).first()
        if row:
            lowest_elo_row = row
            lowest_elo_link = _build_team_link(row[1], row[2])

    if latest_stats.highest_goal_match_id:
        highest_goal_match = db.session.execute(
            select(FootballMatch)
            .where(FootballMatch.match_id == latest_stats.highest_goal_match_id)
        ).scalar_one_or_none()

    if latest_stats.biggest_upset_match_id:
        biggest_upset_match = db.session.execute(
            select(FootballMatch)
            .where(FootballMatch.match_id == latest_stats.biggest_upset_match_id)
        ).scalar_one_or_none()

    return render_template(
        "system_stats.html",
        stats=latest_stats,
        highest_elo_row=highest_elo_row,
        lowest_elo_row=lowest_elo_row,
        highest_elo_link=highest_elo_link,
        lowest_elo_link=lowest_elo_link,
        highest_goal_match=highest_goal_match,
        biggest_upset_match=biggest_upset_match,
    )