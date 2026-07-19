import json

from sqlalchemy import select
from flask import Blueprint, render_template

from ..db import db
from ..models import (
    SystemStats, TeamElo, FootballMatch, Team, Season, League, TeamLeague,
    ModelMetrics,
)
from ..leagues_config import DB_TO_URL
from src.scraping.footballScrap import compute_stats_dict

stats_bp = Blueprint("stats", __name__)

# db_code -> url_code, single source of truth in leagues_config.py
DB_CODE_TO_URL_CODE = DB_TO_URL


def _find_league_for_team_season(team_id, season_id):
    """Find the league a team played in during a given season.

    Args:
        team_id (int): ``Team.team_id`` to look up.
        season_id (int): ``Season.season_id`` to look up.

    Returns:
        League or None: The :class:`League` the team belonged to in that
        season, or ``None`` if no membership is found.
    """
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
    """Build the URL parameters needed to link to a team's page.

    Resolves the team's league for the given season, maps the league's DB code
    to its URL code, and formats the season name (slashes -> spaces) so the
    values can be passed to ``url_for('teams.team_view', ...)``.

    Args:
        team (Team): The team to build a link for.
        season (Season): The season context for the link.

    Returns:
        dict or None: ``{'league_code', 'team_name', 'season_name'}`` suitable
        for ``url_for``, or ``None`` when the league can't be resolved.
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
    """Render the system-wide statistics dashboard.

    Loads the most recent :class:`SystemStats` snapshot. If none exists (e.g.
    right after a scrape), the stats are computed live from the current DB
    state instead of showing an empty page. The highest/lowest ELO, highest-goal
    match, and biggest-upset records are resolved into rows plus template links.

    Args:
        None

    Returns:
        flask.Response: The rendered ``system_stats.html`` template.
    """
    latest_stats = db.session.execute(
        select(SystemStats)
        .order_by(SystemStats.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Most recent model evaluation, to show how the predictor compares to the
    # naive ELO-favourite baseline. Absent on a fresh DB (no training run yet).
    latest_model_metrics = db.session.execute(
        select(ModelMetrics)
        .order_by(ModelMetrics.trained_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Parse the JSON-encoded per-class breakdown and confusion matrix so the
    # template can render them directly. Legacy rows (before these columns
    # existed) simply yield None and the template shows a "run run-predict"
    # hint instead of erroring.
    per_class = None
    confusion_matrix = None
    if latest_model_metrics is not None:
        if latest_model_metrics.per_class:
            try:
                per_class = json.loads(latest_model_metrics.per_class)
            except (ValueError, TypeError):
                per_class = None
        if latest_model_metrics.confusion_matrix:
            try:
                confusion_matrix = json.loads(latest_model_metrics.confusion_matrix)
            except (ValueError, TypeError):
                confusion_matrix = None

    # Po samym scrapingu (choice 1) lub bez pełnego przebiegu pipeline'u
    # tabela system_stats może być pusta. Wtedy liczymy statystyki na żywo
    # z bieżącego stanu bazy, zamiast pokazywać pusty ekran.
    stats_live = False
    if latest_stats is None:
        stats_live = True
        latest_stats = SystemStats(**compute_stats_dict(db.session))

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
        stats_live=stats_live,
        model_metrics=latest_model_metrics,
        per_class=per_class,
        confusion_matrix=confusion_matrix,
        highest_elo_row=highest_elo_row,
        lowest_elo_row=lowest_elo_row,
        highest_elo_link=highest_elo_link,
        lowest_elo_link=lowest_elo_link,
        highest_goal_match=highest_goal_match,
        biggest_upset_match=biggest_upset_match,
    )