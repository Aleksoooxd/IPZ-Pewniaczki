import datetime
import json

from sqlalchemy import or_, desc, case
from flask import Blueprint, render_template

from ..db import db
from ..models import FootballMatch, Team, League, TeamLeague, Season, TeamElo, MatchForm

teams_bp = Blueprint("teams", __name__)

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


def _current_season_name():
    now = datetime.datetime.now()
    y = now.year
    if now.month < 8:
        return f"{y-1}/{str(y)[-2:]}"
    return f"{y}/{str(y+1)[-2:]}"


def _get_team_current_elo(team_id, season_id=None):
    q = db.session.query(TeamElo).filter(TeamElo.team_id == team_id)
    if season_id:
        q = q.filter(TeamElo.season_id == season_id)
    obj = q.order_by(desc(TeamElo.last_updated)).first()
    return int(obj.rating) if obj else None


@teams_bp.route("/league/<league_code>/team/<team_name>/<string:season_name>")
def team_view(league_code, team_name, season_name):
    team = db.session.query(Team).filter_by(name=team_name).first_or_404()
    team_id = team.team_id
    db_code = LEAGUE_URL_MAP.get(league_code)
    display_league = (db_code or league_code).replace(
        "premier league", "Premier League").replace("spremier league", "Scottish Premiership").title()

    if "all" in season_name.lower():
        return _team_all_seasons(league_code, team_name, team_id, db_code, display_league, season_name)
    return _team_single_season(league_code, team_name, team_id, db_code, display_league, season_name)


# ── helpers ──────────────────────────────────────────────────────────

def _team_all_seasons(league_code, team_name, team_id, db_code, display_league, season_name):
    display_season = f"2004-{_current_season_name()[-2:]}"

    team_matchday = case((FootballMatch.home_team_id == team_id, FootballMatch.home_matchday),
                         else_=FootballMatch.away_matchday)
    team_elo_col  = case((FootballMatch.home_team_id == team_id, FootballMatch.home_elo),
                         else_=FootballMatch.away_elo)
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
        for season in db.session.query(Season).join(TeamLeague).filter(
            TeamLeague.team_id == team_id,
            TeamLeague.league_id == league.league_id,
        ).order_by(Season.name).all():
            last_m = db.session.query(FootballMatch).filter(
                FootballMatch.league_id == league.league_id,
                FootballMatch.season_id == season.season_id,
                or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id),
            ).order_by(FootballMatch.date.desc(), FootballMatch.match_id.desc()).first()
            if last_m:
                side = "home" if last_m.home_team_id == team_id else "away"
                ff = db.session.query(MatchForm).filter_by(match_id=last_m.match_id, team_side=side).first()
                if ff and ff.team_placement:
                    position_history.append({"season": season.name, "position": ff.team_placement})

    current_elo_obj = db.session.query(TeamElo).filter(
        TeamElo.team_id == team_id).order_by(TeamElo.last_updated.desc()).first()
    current_elo = current_elo_obj.rating if current_elo_obj else None

    all_matches = db.session.query(FootballMatch).filter(
        or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id)).all()
    total = len(all_matches)
    pts = 0
    for m in all_matches:
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
        league_name=display_league, season_name=season_name,
        display_season_name=display_season,
        elo_history=json.dumps(elo_history),
        position_history=json.dumps(position_history),
        summary_stats_all_seasons=dict(avg_points_per_match=avg_pts, avg_position=avg_pos, current_elo=current_elo),
    )


def _team_single_season(league_code, team_name, team_id, db_code, display_league, season_name):
    display_season = season_name.replace(" ", "/")
    season_obj = db.session.query(Season).filter(Season.name == season_name.replace(" ", "/")).first_or_404()
    league_obj = db.session.query(League).filter_by(code=db_code).first_or_404()

    teams_in = db.session.query(Team).join(TeamLeague).filter(
        TeamLeague.league_id == league_obj.league_id,
        TeamLeague.season_id == season_obj.season_id,
    ).all()

    lw_stats = []
    for t in teams_in:
        ms = db.session.query(FootballMatch).filter(
            FootballMatch.season_id == season_obj.season_id,
            FootballMatch.league_id == league_obj.league_id,
            or_(FootballMatch.home_team_id == t.team_id, FootballMatch.away_team_id == t.team_id),
        ).all()
        if not ms:
            continue
        gf = sum((m.fthg if m.home_team_id == t.team_id else m.ftag) or 0 for m in ms)
        ga = sum((m.ftag if m.home_team_id == t.team_id else m.fthg) or 0 for m in ms)
        lw_stats.append(dict(team_id=t.team_id, avg_goals_for=gf/len(ms), avg_goals_conceded=ga/len(ms)))

    def rank(key, tid, rev=False):
        s = sorted(lw_stats, key=lambda x: x[key], reverse=rev)
        return next((i+1 for i, it in enumerate(s) if it["team_id"] == tid), None)

    matches = db.session.query(FootballMatch).filter(
        FootballMatch.season_id == season_obj.season_id,
        FootballMatch.league_id == league_obj.league_id,
        or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id),
    ).order_by(FootballMatch.date).all()

    elo_data = []; points_data = []; gf_data = []; ga_data = []; pos_data = []
    cum_pts = cum_gf = cum_ga = 0

    for m in matches:
        side = "home" if m.home_team_id == team_id else "away"
        md   = m.home_matchday if side == "home" else m.away_matchday
        if side == "home":
            elo = m.home_elo
            cum_gf += m.fthg or 0; cum_ga += m.ftag or 0
            cum_pts += 3 if m.result == "H" else 1 if m.result == "D" else 0
        else:
            elo = m.away_elo
            cum_gf += m.ftag or 0; cum_ga += m.fthg or 0
            cum_pts += 3 if m.result == "A" else 1 if m.result == "D" else 0
        elo_data.append({"matchday": md, "value": elo})
        points_data.append({"matchday": md, "value": cum_pts})
        gf_data.append({"matchday": md, "value": cum_gf})
        ga_data.append({"matchday": md, "value": cum_ga})
        ff = db.session.query(MatchForm).filter_by(match_id=m.match_id, team_side=side).first()
        if ff:
            pos_data.append({"matchday": md, "value": ff.team_placement})

    for lst in (elo_data, points_data, gf_data, ga_data, pos_data):
        lst.sort(key=lambda x: x["matchday"])

    cum_w = cum_d = cum_l = 0
    w_d_l = []
    for m in matches:
        side = "home" if m.home_team_id == team_id else "away"
        md   = m.home_matchday if side == "home" else m.away_matchday
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
        league_name=display_league, season_name=season_name,
        display_season_name=display_season,
        elo_data=json.dumps(elo_data),
        points_data=json.dumps(points_data),
        goals_for_data=json.dumps(gf_data),
        goals_conceded_data=json.dumps(ga_data),
        position_data=json.dumps(pos_data),
        w_d_l_data=json.dumps(w_d_l),
        summary_stats=summary,
    )