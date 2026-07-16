"""Team routes: per-team season and all-seasons statistics views."""

import datetime
import json

from sqlalchemy import or_, desc, case
from flask import Blueprint, render_template

from ..db import db
from ..models import FootballMatch, Team, League, TeamLeague, Season, TeamElo, MatchForm

teams_bp = Blueprint("teams", __name__)

LEAGUE_URL_MAP = {
    "Premierleague": "premier league",
    "Bundesliga": "bundesliga",
    "Eredivisie": "eredivisie",
    "EthnikiKatigoria": "ethniki katigoria",
    "FutbolLig1": "futbol ligi 1",
    "JupiterLeague": "jupiler league",
    "LaLiga": "la liga",
    "Ligue1": "ligue 1",
    "LigaI": "liga i",
    "SerieA": "serie a",
    "ScottishPremierLeague": "spremier league",
}

DB_CODE_TO_URL_CODE = {v: k for k, v in LEAGUE_URL_MAP.items()}

DB_CODE_TO_DISPLAY = {
    "premier league": "Premier League",
    "bundesliga": "Bundesliga",
    "eredivisie": "Eredivisie",
    "ethniki katigoria": "Ethniki Katigoria",
    "futbol ligi 1": "Futbol Ligi 1",
    "jupiler league": "Jupiler League",
    "la liga": "La Liga",
    "ligue 1": "Ligue 1",
    "liga i": "Liga I",
    "serie a": "Serie A",
    "spremier league": "Scottish Premiership",
}


def _current_season_name():
    """Return the current football season label (e.g. ``"2024/25"``).

    Seasons are assumed to turn over after July: before August the season is
    ``(year-1)/year``, from August onward it is ``year/(year+1)``.

    Args:
        None

    Returns:
        str: Season name in ``YYYY/YY`` format.
    """
    now = datetime.datetime.now()
    y = now.year
    if now.month < 8:
        return f"{y-1}/{str(y)[-2:]}"
    return f"{y}/{str(y+1)[-2:]}"


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
    q = db.session.query(TeamElo).filter(TeamElo.team_id == team_id)
    if season_id:
        q = q.filter(TeamElo.season_id == season_id)
    obj = q.order_by(desc(TeamElo.last_updated)).first()
    return int(obj.rating) if obj else None


def _get_team_trophies(team_id):
    """Return a team's championship (1st-place) history.

    Queries :class:`TeamLeague` rows flagged ``is_champion`` for the team and,
    for each, builds the league/season labels used for display and linking.

    Args:
        team_id (int): ``Team.team_id`` to fetch trophies for.

    Returns:
        list[dict]: One entry per title with ``league_name``, ``league_code``,
        ``league_url_code``, ``season_name`` and ``season_url``.
    """
    rows = db.session.query(TeamLeague, League, Season).join(
        League, League.league_id == TeamLeague.league_id
    ).join(
        Season, Season.season_id == TeamLeague.season_id
    ).filter(
        TeamLeague.team_id == team_id,
        TeamLeague.is_champion == 1,
    ).order_by(Season.name.desc()).all()

    trophies = []
    for tl, league, season in rows:
        trophies.append({
            "league_name": DB_CODE_TO_DISPLAY.get(league.code, league.code.title()),
            "league_code": league.code,
            "league_url_code": DB_CODE_TO_URL_CODE.get(league.code, league.code),
            "season_name": season.name,
            "season_url": season.name.replace("/", " "),
        })
    return trophies


@teams_bp.route("/league/<league_code>/team/<team_name>/<season_name>")
def team_view(league_code, team_name, season_name):
    """Render a team's statistics page for one season or all seasons.

    Resolves the team (404 if unknown), derives the display league name, and
    fetches the team's trophies. A ``season_name`` containing "all" dispatches
    to :func:`_team_all_seasons`; otherwise to :func:`_team_single_season`.

    Args:
        league_code (str): URL segment identifying the league.
        team_name (str): ``Team.name`` to display.
        season_name (str): Season label, or a name containing "all" for the
            aggregated all-seasons view.

    Returns:
        flask.Response: The rendered ``team.html`` (via a helper), or a 404
        abort for an unknown team.
    """
    team = db.session.query(Team).filter_by(name=team_name).first_or_404()
    team_id = team.team_id

    db_code = LEAGUE_URL_MAP.get(league_code)
    display_league = (db_code or league_code).replace(
        "premier league", "Premier League").replace("spremier league", "Scottish Premiership").title()

    trophies = _get_team_trophies(team_id)

    if "all" in season_name.lower():
        return _team_all_seasons(league_code, team_name, team_id, db_code, display_league, season_name, trophies)
    return _team_single_season(league_code, team_name, team_id, db_code, display_league, season_name, trophies)


# ── helpers ──────────────────────────────────────────────────────────

def _team_all_seasons(league_code, team_name, team_id, db_code, display_league, season_name, trophies):
    """Build the all-seasons team view data and render ``team.html``.

    Computes the ELO history (per season/matchday), the team's final league
    position per season (from a simulated table via
    :func:`_compute_position_snapshots`), total points / average points per match
    / average position across all seasons, and the current ELO. Renders the
    template.

    Args:
        league_code (str): URL league segment.
        team_name (str): ``Team.name``.
        team_id (int): ``Team.team_id``.
        db_code (str or None): DB league code (from the URL map) or None.
        display_league (str): Human-readable league name for display.
        season_name (str): The requested season label (contains "all").
        trophies (list[dict]): Pre-fetched championship history.

    Returns:
        flask.Response: The rendered ``team.html``.
    """
    display_season = f"2004-{_current_season_name()[-2:]}"

    team_matchday = FootballMatch.round
    team_elo_col = case((FootballMatch.home_team_id == team_id, FootballMatch.home_elo), else_=FootballMatch.away_elo)

    elo_rows = db.session.query(
        Season.name.label("season_name"),
        team_matchday.label("matchday"),
        team_elo_col.label("elo"),
    ).join(Season, FootballMatch.season_id == Season.season_id).filter(
        or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id),
        FootballMatch.home_elo.isnot(None),
    ).order_by(Season.name, team_matchday).all()

    elo_history = [{"label": f"{r.season_name} K{r.matchday}", "rating": r.elo} for r in elo_rows]

    position_history = []
    league = db.session.query(League).filter_by(code=db_code).first()

    if league:
        seasons = db.session.query(Season).join(TeamLeague).filter(
            TeamLeague.team_id == team_id,
            TeamLeague.league_id == league.league_id,
        ).order_by(Season.name).all()

        for season in seasons:
            # ── ZMIANA: pozycja liczona z rzeczywistej symulacji tabeli sezonu,
            # nie z MatchForm.team_placement ──
            season_matches = db.session.query(FootballMatch).filter(
                FootballMatch.league_id == league.league_id,
                FootballMatch.season_id == season.season_id,
            ).all()

            if not season_matches:
                continue

            snapshots = _compute_position_snapshots(season_matches)
            last_match = max(season_matches, key=lambda m: (m.date, m.match_id))
            final_rank_map = snapshots.get(last_match.match_id, {})
            team_final_position = final_rank_map.get(team_id)

            if team_final_position:
                position_history.append({"season": season.name, "position": team_final_position})

    current_elo_obj = db.session.query(TeamElo).filter(
        TeamElo.team_id == team_id).order_by(TeamElo.last_updated.desc()).first()
    current_elo = current_elo_obj.rating if current_elo_obj else None

    all_matches_total = db.session.query(FootballMatch).filter(
        or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id)).all()

    total = len(all_matches_total)
    pts = 0
    for m in all_matches_total:
        if m.result:
            if m.home_team_id == team_id:
                pts += 3 if m.result == "H" else 1 if m.result == "D" else 0
            else:
                pts += 3 if m.result == "A" else 1 if m.result == "D" else 0

    avg_pts = pts / total if total else 0
    avg_pos = sum(p["position"] for p in position_history) / len(position_history) if position_history else None

    return render_template(
        "team.html",
        league_code=league_code, team_name=team_name, team_id=team_id,
        league_name=display_league, season_name=season_name, display_season_name=display_season,
        elo_history=json.dumps(elo_history), position_history=json.dumps(position_history),
        summary_stats_all_seasons=dict(avg_points_per_match=avg_pts, avg_position=avg_pos, current_elo=current_elo),
        trophies=trophies,
    )


def _team_single_season(league_code, team_name, team_id, db_code, display_league, season_name, trophies):
    """Build a single-season team view and render ``team.html``.

    Loads the season/league, computes per-team goal averages across the league,
    simulates the league table to get position snapshots, and accumulates the
    team's ELO / cumulative points / cumulative goals / position / win-draw-loss
    curves match by match. Renders the template.

    Args:
        league_code (str): URL league segment.
        team_name (str): ``Team.name``.
        team_id (int): ``Team.team_id``.
        db_code (str or None): DB league code.
        display_league (str): Human-readable league name.
        season_name (str): Season label (spaces denote the ``/`` in ``YYYY/YY``).
        trophies (list[dict]): Pre-fetched championship history.

    Returns:
        flask.Response: The rendered ``team.html``.
    """
    display_season = season_name.replace(" ", "/")
    season_obj = db.session.query(Season).filter(Season.name == season_name.replace(" ", "/")).first_or_404()
    league_obj = db.session.query(League).filter_by(code=db_code).first_or_404()

    teams_in = db.session.query(Team).join(TeamLeague).filter(
        TeamLeague.league_id == league_obj.league_id,
        TeamLeague.season_id == season_obj.season_id,
    ).all()

    all_season_matches = db.session.query(FootballMatch).filter(
        FootballMatch.season_id == season_obj.season_id,
        FootballMatch.league_id == league_obj.league_id,
    ).all()

    team_goal_stats = {t.team_id: {"gf": 0, "ga": 0, "played": 0} for t in teams_in}
    for m in all_season_matches:
        if m.home_team_id in team_goal_stats:
            team_goal_stats[m.home_team_id]["gf"] += m.fthg or 0
            team_goal_stats[m.home_team_id]["ga"] += m.ftag or 0
            team_goal_stats[m.home_team_id]["played"] += 1
        if m.away_team_id in team_goal_stats:
            team_goal_stats[m.away_team_id]["gf"] += m.ftag or 0
            team_goal_stats[m.away_team_id]["ga"] += m.fthg or 0
            team_goal_stats[m.away_team_id]["played"] += 1

    lw_stats = [
        dict(team_id=tid, avg_goals_for=v["gf"] / v["played"], avg_goals_conceded=v["ga"] / v["played"])
        for tid, v in team_goal_stats.items() if v["played"] > 0
    ]

    def rank(key, tid, rev=False):
        """Return the 1-based rank of a team by a league-wide stat.

        Args:
            key (str): Stat key in ``lw_stats`` to rank by.
            tid (int): ``Team.team_id`` to locate in the ranking.
            rev (bool, optional): Rank descending when True. Defaults to False.

        Returns:
            int or None: 1-based rank, or ``None`` if the team isn't present.
        """
        s = sorted(lw_stats, key=lambda x: x[key], reverse=rev)
        return next((i + 1 for i, it in enumerate(s) if it["team_id"] == tid), None)

    position_snapshots = _compute_position_snapshots(all_season_matches)

    matches = db.session.query(FootballMatch).filter(
        FootballMatch.season_id == season_obj.season_id,
        FootballMatch.league_id == league_obj.league_id,
        or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id),
    ).order_by(FootballMatch.date).all()

    elo_data, points_data, gf_data, ga_data, pos_data = [], [], [], [], []
    cum_pts = cum_gf = cum_ga = 0

    for m in matches:
        side = "home" if m.home_team_id == team_id else "away"
        md = m.round

        if side == "home":
            elo = m.home_elo
            cum_gf += m.fthg or 0
            cum_ga += m.ftag or 0
            cum_pts += 3 if m.result == "H" else 1 if m.result == "D" else 0
        else:
            elo = m.away_elo
            cum_gf += m.ftag or 0
            cum_ga += m.fthg or 0
            cum_pts += 3 if m.result == "A" else 1 if m.result == "D" else 0

        elo_data.append({"matchday": md, "value": elo})
        points_data.append({"matchday": md, "value": cum_pts})
        gf_data.append({"matchday": md, "value": cum_gf})
        ga_data.append({"matchday": md, "value": cum_ga})

        # ── ZMIANA: pozycja z symulacji tabeli, nie z MatchForm.team_placement ──
        rank_map = position_snapshots.get(m.match_id, {})
        team_position = rank_map.get(team_id)
        if team_position:
            pos_data.append({"matchday": md, "value": team_position})

    for lst in (elo_data, points_data, gf_data, ga_data, pos_data):
        lst.sort(key=lambda x: x["matchday"])

    cum_w = cum_d = cum_l = 0
    w_d_l = []
    for m in matches:
        side = "home" if m.home_team_id == team_id else "away"
        md = m.round
        if m.result:
            if (side == "home" and m.result == "H") or (side == "away" and m.result == "A"):
                cum_w += 1
            elif m.result == "D":
                cum_d += 1
            else:
                cum_l += 1
        w_d_l.append({"matchday": md, "wins": cum_w, "draws": cum_d, "losses": cum_l})
    w_d_l.sort(key=lambda x: x["matchday"])

    n = len(matches)
    my_stats = next((s for s in lw_stats if s["team_id"] == team_id), {})

    summary = dict(
        avg_goals_for=round(my_stats.get("avg_goals_for", 0), 2),
        avg_goals_conceded=round(my_stats.get("avg_goals_conceded", 0), 2),
        final_position=pos_data[-1]["value"] if pos_data else None,
        avg_goals_for_rank=rank("avg_goals_for", team_id, rev=True),
        avg_goals_conceded_rank=rank("avg_goals_conceded", team_id),
        avg_points_per_match=round(cum_pts / n, 2) if n else 0,
    )

    return render_template(
        "team.html",
        league_code=league_code, team_name=team_name, team_id=team_id,
        league_name=display_league, season_name=season_name, display_season_name=display_season,
        elo_data=json.dumps(elo_data), points_data=json.dumps(points_data),
        goals_for_data=json.dumps(gf_data), goals_conceded_data=json.dumps(ga_data),
        position_data=json.dumps(pos_data), w_d_l_data=json.dumps(w_d_l),
        summary_stats=summary, trophies=trophies,
    )
def _compute_position_snapshots(matches):
    """Simulate a league table after each match to snapshot team positions.

    Replays the matches in date order, accumulating points and goal difference
    per team, and after each match ranks all teams (by points, then GD, then
    goals-for) to record every team's 1-based position keyed by ``match_id``.

    Args:
        matches (list[FootballMatch]): Matches of one league/season, in any
            order (they are sorted internally by date then id).

    Returns:
        dict: Mapping ``match_id -> {team_id: position}`` for every match.
    """
    sorted_matches = sorted(matches, key=lambda m: (m.date, m.match_id))
    standings = {}
    snapshots = {}

    for m in sorted_matches:
        for tid in (m.home_team_id, m.away_team_id):
            standings.setdefault(tid, {"points": 0, "gf": 0, "ga": 0, "gd": 0})

        h, a = standings[m.home_team_id], standings[m.away_team_id]
        hg, ag = m.fthg or 0, m.ftag or 0
        h["gf"] += hg; h["ga"] += ag; h["gd"] = h["gf"] - h["ga"]
        a["gf"] += ag; a["ga"] += hg; a["gd"] = a["gf"] - a["ga"]

        if m.result == "H":
            h["points"] += 3
        elif m.result == "D":
            h["points"] += 1; a["points"] += 1
        elif m.result == "A":
            a["points"] += 3

        ranked = sorted(
            standings.items(),
            key=lambda kv: (-kv[1]["points"], -kv[1]["gd"], -kv[1]["gf"])
        )
        snapshots[m.match_id] = {tid: i + 1 for i, (tid, _) in enumerate(ranked)}

    return snapshots