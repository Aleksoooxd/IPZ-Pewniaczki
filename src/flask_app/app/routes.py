from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from sqlalchemy.orm import aliased

from .db import db, FootballMatch, Team, League

main = Blueprint('main', __name__)
@main.route('/')
def home():
    return render_template('index.html')

@main.route('/main')
def mainpage():
    return render_template('MainPage.html')

@main.route('/premierleague')
def premierleague():
    return render_template('premierleague.html')

@main.route('/bundesliga')
def bundesliga():
    return render_template('bundesliga.html')

@main.route('/laliga')
def laliga():
    return render_template('laliga.html')

@main.route('/ligue1')
def ligue1():
    return render_template('ligue1.html')

@main.route('/seriea')
def seriea():
    return render_template('seriea.html')

@main.route('/eredivisie')
def eredivisie():
    return render_template('eredivisie.html')

@main.route('/scotishpremierleague')
def scotishpremierleague():
    return render_template('scotishpremierleague.html')

@main.route('/greecesuperleague')
def greecesuperleague():
    return render_template('greecesuperleague.html')
@main.route('/jupilerleague')
def jupilerleague():
    return render_template('jupilerleague.html')

@main.route('/superleauge')
def superleauge():
    return render_template('superleauge.html')

@main.route('/leaugeportugal')
def leaugeportugal():
    return render_template('leaugeportugal.html')

@main.route('/matches')
def get_matches():
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    matches = db.session.query(
        FootballMatch.date,
        HomeTeam.name.label('home_team'),
        AwayTeam.name.label('away_team'),
        League.code.label('league')
    ).join(
        HomeTeam, FootballMatch.home_team_id == HomeTeam.team_id
    ).join(
        AwayTeam, FootballMatch.away_team_id == AwayTeam.team_id
    ).join(
        League, FootballMatch.league_id == League.league_id
    ).all()

    result = [
        {
            "date": m.date.strftime('%Y-%m-%d'),
            "home_team": m.home_team,
            "away_team": m.away_team,
            "league": m.league
        } for m in matches
    ]

    return jsonify(result)


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


