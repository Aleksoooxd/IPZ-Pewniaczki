from flask import Blueprint, render_template, request, redirect, url_for, jsonify,abort
from sqlalchemy.orm import aliased

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

@main.route('/matches')
def get_matches():
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    past_matches = db.session.query(
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
    )

    future_matches = db.session.query(
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
    )

    matches = past_matches.union_all(future_matches).all()

    result = [
        {
            "date": m.date.strftime('%Y-%m-%d'),
            "home_team": m.home_team,
            "away_team": m.away_team,
            "league": m.league,
            "home_goals": m.home_goals if m.home_goals is not None else '-',
            "away_goals": m.away_goals if m.away_goals is not None else '-'
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


