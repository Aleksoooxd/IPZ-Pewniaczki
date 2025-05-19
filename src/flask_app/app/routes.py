from flask import Blueprint, render_template, request, redirect, url_for, jsonify,abort
from sqlalchemy.orm import aliased
from datetime import datetime
from flask import render_template, abort


from .db import db, FootballMatch, Team, League, FutureMatch

main = Blueprint('main', __name__)
@main.route('/')
def home():
    return render_template('index.html')

@main.route('/main')
def mainpage():
    league_names = {
        "Premierleague": "premier league",
        "Bundesliga": "Bundesliga",
        "Eredivisie": "Eredivisie",
        "EthnikiKatigoria": "Grecja: Ethniki Katigoria",
        "FutbolLig1": "Turcja: 1. Lig",
        "JupiterLeague": "Belgia: Jupiler League",
        "LaLiga": "Hiszpania: La Liga",
        "Ligue1": "Francja: Ligue 1",
        "LigaI": "Rumunia: Liga I",
        "ScotishPremierLeague": "Szkocja: Premiership",
        "SerieA": "Włochy: Serie A"
    }
    return render_template('MainPage.html', league_names=league_names)


@main.route('/api/matches')
def get_matches():
    date_param = request.args.get('date')

    if not date_param:
        return jsonify({"error": "Missing 'date' parameter"}), 400

    try:
        match_date = datetime.strptime(date_param, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    # POBIERANIE MECZÓW Z DANEGO DNIA
    past_matches = db.session.query(
        FootballMatch.match_id,  # <-- dodaj to
        FootballMatch.date,
        HomeTeam.name.label('home_team'),
        AwayTeam.name.label('away_team'),
        League.code.label('league'),
        FootballMatch.fthg.label('home_goals'),
        FootballMatch.ftag.label('away_goals')
    ).join(
        HomeTeam, FootballMatch.home_team_id == HomeTeam.team_id
    ).join(
        AwayTeam, FootballMatch.away_team_id == AwayTeam.team_id
    ).join(
        League, FootballMatch.league_id == League.league_id
    ).filter(FootballMatch.date == match_date)

    future_matches = db.session.query(
        FutureMatch.match_id,
        FutureMatch.date,
        HomeTeam.name.label('home_team'),
        AwayTeam.name.label('away_team'),
        League.code.label('league'),
        db.literal(None).label('home_goals'),
        db.literal(None).label('away_goals')
    ).join(
        HomeTeam, FutureMatch.home_team_id == HomeTeam.team_id
    ).join(
        AwayTeam, FutureMatch.away_team_id == AwayTeam.team_id
    ).join(
        League, FutureMatch.league_id == League.league_id
    ).filter(FutureMatch.date == match_date)

    matches = past_matches.union_all(future_matches).all()

    result = [
        {
            "match_id": m.match_id,
            "date": m.date.strftime('%Y-%m-%d'),
            "home_team": m.home_team,
            "away_team": m.away_team,
            "league": m.league,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals
        } for m in matches
    ]

    return jsonify(result)



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
    "PremierLeague": "premier league",
    "SerieA": "serie a",
    "ScotishPremierLeague": "spremier league"
}



@main.route('/match/<int:match_id>')
def match_detail(match_id):
    match = FootballMatch.query.filter_by(match_id=match_id).first()
    if not match:
        abort(404)

    home_form = {f.team_side: f for f in match.form_data}.get('home')
    away_form = {f.team_side: f for f in match.form_data}.get('away')

    home_stats = {s.team_side: s for s in match.match_stats}.get('home')
    away_stats = {s.team_side: s for s in match.match_stats}.get('away')

    home_value = match.home_value_ref.value if match.home_value_ref else None
    away_value = match.away_value_ref.value if match.away_value_ref else None

    predictions = match.predictions

    from datetime import date
    if match.result:
        status = "finished"
    elif match.date > date.today():
        status = "upcoming"
    else:
        status = "live"  # lub inna logika

    return render_template('match_detail.html', match=match,
                           home_form=home_form, away_form=away_form,
                           home_stats=home_stats, away_stats=away_stats,
                           home_value=home_value, away_value=away_value,
                           predictions=predictions, status=status)


@main.route('/league/<league_code>')
def league_view(league_code):
    db_code = LEAGUE_URL_MAP.get(league_code)
    if not db_code:
        abort(404, description=f"Nieznana liga: {league_code}")

    league = League.query.filter_by(code=db_code).first_or_404()

    teams = db.session.query(Team).join(
        FootballMatch,
        ((FootballMatch.league_id == league.league_id) &
         ((FootballMatch.home_team_id == Team.team_id) |
          (FootballMatch.away_team_id == Team.team_id)))
    ).distinct().order_by(Team.name).all()

    return render_template('league_view.html', league=league, teams=teams)

@main.route('/test_db')
def test_db():
    from . import db
    from sqlalchemy import text
    status = ""
    try:
        result = db.session.execute(text("SELECT 1")).scalar()
        if result == 1:
            status = "✅ Połączenie z bazą danych działa poprawnie."
        else:
            status = "⚠️ Połączenie wykonane, ale wynik zapytania testowego jest nieoczekiwany."
    except Exception as e:
        status = f"❌ Błąd połączenia z bazą danych: {str(e)}"

    return render_template('test_db.html', status=status)


