from sqlalchemy import or_, desc
from sqlalchemy.orm import aliased
from flask import Blueprint, render_template, abort

from ..db import db
from ..models import FootballMatch, FutureMatch, Team, League, MatchForm, MatchStats, TeamElo, PredictedFuture

matches_bp = Blueprint("matches", __name__)


@matches_bp.route("/match/<string:match_type>/<int:match_id>")
def match_detail(match_type, match_id):
    from datetime import date

    if match_type == "past":
        match = FootballMatch.query.filter_by(match_id=match_id).first()
    elif match_type == "future":
        match = FutureMatch.query.filter_by(match_id=match_id).first()
    else:
        abort(404)

    if not match:
        abort(404)

    if hasattr(match, "result") and match.result:
        status = "finished"
    elif match.date > date.today():
        status = "upcoming"
    else:
        status = "live"

    home_form = away_form = None
    home_stats = away_stats = None
    home_elo = away_elo = None
    predictions = []
    home_h2h_data = away_h2h_data = None
    home_last_3_matches = away_last_3_matches = []

    home_team_id = match.home_team_id
    away_team_id = match.away_team_id
    match_date = match.date
    season_id = match.season.season_id if match.season else None

    HomeTeamAlias = aliased(Team)
    AwayTeamAlias = aliased(Team)

    if isinstance(match, FutureMatch):
        home_elo_obj = TeamElo.query.filter_by(team_id=home_team_id).order_by(desc(TeamElo.last_updated)).first()
        away_elo_obj = TeamElo.query.filter_by(team_id=away_team_id).order_by(desc(TeamElo.last_updated)).first()
        home_elo = home_elo_obj.rating if home_elo_obj else None
        away_elo = away_elo_obj.rating if away_elo_obj else None

        predictions = PredictedFuture.query.filter_by(match_id=match_id).all()

        for team_id, attr in [(home_team_id, "home"), (away_team_id, "away")]:
            last = db.session.query(FootballMatch).filter(
                or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id),
                FootballMatch.date < match_date,
                FootballMatch.result.isnot(None),
            ).order_by(desc(FootballMatch.date), desc(FootballMatch.match_id)).first()

            if last:
                side = "home" if last.home_team_id == team_id else "away"
                form = MatchForm.query.filter_by(match_id=last.match_id, team_side=side).first()
                if attr == "home":
                    home_form = form
                else:
                    away_form = form

        past_h2h = db.session.query(FootballMatch).filter(
            or_(
                (FootballMatch.home_team_id == home_team_id) & (FootballMatch.away_team_id == away_team_id),
                (FootballMatch.home_team_id == away_team_id) & (FootballMatch.away_team_id == home_team_id),
            ),
            FootballMatch.date < match_date,
            FootballMatch.result.isnot(None),
        ).order_by(desc(FootballMatch.date)).all()

        n = len(past_h2h)
        hw = dr = aw = hgf = hga = h5pts = 0
        for m in past_h2h:
            is_home = m.home_team_id == home_team_id
            res = m.result
            if is_home:
                if res == "H":   hw += 1; h5pts += 3
                elif res == "D": dr += 1; h5pts += 1
                else:            aw += 1
                hgf += m.fthg or 0; hga += m.ftag or 0
            else:
                if res == "A":   hw += 1; h5pts += 3
                elif res == "D": dr += 1; h5pts += 1
                else:            aw += 1
                hgf += m.ftag or 0; hga += m.fthg or 0

        home_h2h_data = dict(h2h_matches=n, h2h_wins=hw, h2h_draws=dr,
                             h2h_losses=n-hw-dr, h2h_goals_for=hgf,
                             h2h_goals_against=hga, h2h_last_5_points=h5pts)
        away_h2h_data = dict(h2h_matches=n, h2h_wins=aw, h2h_draws=dr,
                             h2h_losses=hw, h2h_goals_for=hga,
                             h2h_goals_against=hgf, h2h_last_5_points=h5pts)

        def last_3(team_id):
            return db.session.query(
                FootballMatch,
                HomeTeamAlias.name.label("home_team_name"),
                AwayTeamAlias.name.label("away_team_name"),
            ).outerjoin(HomeTeamAlias, FootballMatch.home_team_id == HomeTeamAlias.team_id
            ).outerjoin(AwayTeamAlias, FootballMatch.away_team_id == AwayTeamAlias.team_id
            ).filter(
                or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id),
                FootballMatch.date < match_date,
                FootballMatch.result.isnot(None),
            ).order_by(desc(FootballMatch.date)).limit(3).all()

        home_last_3_matches = last_3(home_team_id)
        away_last_3_matches = last_3(away_team_id)

    else:  # past FootballMatch
        home_elo = match.home_elo
        away_elo = match.away_elo

        home_form  = MatchForm.query.filter_by(match_id=match.match_id, team_side="home").first()
        away_form  = MatchForm.query.filter_by(match_id=match.match_id, team_side="away").first()
        home_stats = MatchStats.query.filter_by(match_id=match.match_id, team_side="home").first()
        away_stats = MatchStats.query.filter_by(match_id=match.match_id, team_side="away").first()
        predictions = match.predictions

        home_h2h_data = home_form if home_form and home_form.h2h_matches else None
        away_h2h_data = away_form if away_form and away_form.h2h_matches else None

        def last_3(team_id):
            return db.session.query(
                FootballMatch,
                HomeTeamAlias.name.label("home_team_name"),
                AwayTeamAlias.name.label("away_team_name"),
            ).outerjoin(HomeTeamAlias, FootballMatch.home_team_id == HomeTeamAlias.team_id
            ).outerjoin(AwayTeamAlias, FootballMatch.away_team_id == AwayTeamAlias.team_id
            ).filter(
                or_(FootballMatch.home_team_id == team_id, FootballMatch.away_team_id == team_id),
                FootballMatch.date < match_date,
            ).order_by(desc(FootballMatch.date)).limit(3).all()

        home_last_3_matches = last_3(home_team_id)
        away_last_3_matches = last_3(away_team_id)

    return render_template(
        "match_detail.html",
        match=match, status=status,
        home_form=home_form, away_form=away_form,
        home_stats=home_stats, away_stats=away_stats,
        home_elo=home_elo, away_elo=away_elo,
        predictions=predictions,
        home_h2h_data=home_h2h_data, away_h2h_data=away_h2h_data,
        home_last_3_matches=home_last_3_matches,
        away_last_3_matches=away_last_3_matches,
    )