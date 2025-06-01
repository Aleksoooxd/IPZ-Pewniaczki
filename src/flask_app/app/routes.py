# src/flask_app/app/routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify,abort
from sqlalchemy.orm import aliased
from datetime import datetime
from flask import render_template, abort

from sqlalchemy import or_, desc


from .db import db, FootballMatch, Team, League, FutureMatch , TeamValue, Predicted,MatchStats,MatchForm,TeamElo, TeamLeague, Season


main = Blueprint('main', __name__)
@main.route('/')
def home():
    return render_template('index.html')


@main.route('/main')
def mainpage():
    league_names = {
        "Premierleague": "Premier league",
        "Bundesliga": "Bundesliga",
        "Eredivisie": "Eredivisie",
        "EthnikiKatigoria": "Ethniki Katigoria",
        "FutbolLig1": "1. Lig",
        "JupiterLeague": "Jupiler League",
        "LaLiga": "La Liga",
        "Ligue1": "Ligue 1",
        "LigaI": "Liga I",
        "ScotishPremierLeague": "Premiership",
        "SerieA": "Serie A"
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
        return jsonify({"error": "Invalid date format. UseYYYY-MM-DD."}), 400

    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    # PAST MATCHES
    past_matches = db.session.query(
        FootballMatch.match_id,
        FootballMatch.date,
        HomeTeam.name.label('home_team'),
        HomeTeam.team_id.label('home_team_id'),
        AwayTeam.name.label('away_team'),
        AwayTeam.team_id.label('away_team_id'),
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

    # FUTURE MATCHES
    future_matches = db.session.query(
        FutureMatch.match_id,
        FutureMatch.date,
        HomeTeam.name.label('home_team'),
        HomeTeam.team_id.label('home_team_id'),
        AwayTeam.name.label('away_team'),
        AwayTeam.team_id.label('away_team_id'),
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

    # COMBINE
    matches = past_matches.union_all(future_matches).all()

    result = [
        {
            "match_id": m.match_id,
            "match_type": "past" if m.home_goals is not None else "future",
            "date": m.date.strftime('%Y-%m-%d'),
            "home_team": m.home_team,
            "home_team_id": m.home_team_id,
            "away_team": m.away_team,
            "away_team_id": m.away_team_id,
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
    "SerieA": "serie a",
    "ScotishPremierLeague": "spremier league"
}

LEAGUE_NAME_TO_URL= {
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
  "spremier league": "ScotishPremierLeague"
}


def get_current_season_name():
    current_year = datetime.now().year
    if datetime.now().month < 8:
        season = f"{current_year - 1}/{str(current_year)[-2:]}"
    else:
        season = f"{current_year}/{str(current_year + 1)[-2:]}"
    return season


@main.route('/match/<string:match_type>/<int:match_id>')
def match_detail(match_type, match_id):
    from datetime import date
    from sqlalchemy import or_, desc
    from sqlalchemy.orm.exc import NoResultFound

    if match_type == "past":
        match = FootballMatch.query.filter_by(match_id=match_id).first()
    elif match_type == "future":
        match = FutureMatch.query.filter_by(match_id=match_id).first()
    else:
        abort(404)

    if not match:
        abort(404)

    if hasattr(match, 'result') and match.result:
        status = "finished"
    elif match.date > date.today():
        status = "upcoming"
    else:
        status = "live"

    # Init variables
    home_form = None
    away_form = None
    home_stats = None
    away_stats = None
    home_value = None
    away_value = None
    home_elo = None
    away_elo = None
    predictions = []
    h2h_data = None
    home_h2h_data = None
    away_h2h_data = None
    home_last_3_matches = []
    away_last_3_matches = []


    if isinstance(match, FutureMatch):
        season_id = match.season.season_id
        home_team_id = match.home_team.team_id
        away_team_id = match.away_team.team_id
        match_date_for_h3h = match.date

        # Elo
        home_elo_obj = TeamElo.query.filter_by(team_id=home_team_id).order_by(desc(TeamElo.last_updated)).first()
        away_elo_obj = TeamElo.query.filter_by(team_id=away_team_id).order_by(desc(TeamElo.last_updated)).first()
        home_elo = home_elo_obj.rating if home_elo_obj else None
        away_elo = away_elo_obj.rating if away_elo_obj else None

        # Value
        home_value_obj = TeamValue.query.filter_by(team_id=home_team_id, season_id=season_id).first()
        away_value_obj = TeamValue.query.filter_by(team_id=away_team_id, season_id=season_id).first()
        home_value = home_value_obj.value if home_value_obj else None
        away_value = away_value_obj.value if away_value_obj else None

        # Form
        home_form = MatchForm.query.filter_by(match_id=match.match_id, team_side='home').first()
        away_form = MatchForm.query.filter_by(match_id=match.match_id, team_side='away').first()

        # Stats
        home_stats = MatchStats.query.filter_by(match_id=match.match_id, team_side='home').first()
        away_stats = MatchStats.query.filter_by(match_id=match.match_id, team_side='away').first()

        # Predictions
        predictions = Predicted.query.filter_by(match_id=match_id).all()

        # H2H per team side
        home_h2h_data = home_form if home_form and home_form.h2h_matches else None
        away_h2h_data = away_form if away_form and away_form.h2h_matches else None

        # Fetch last 3 matches for future matches (assuming they are past matches relative to the future match date)
        HomeTeamAlias = aliased(Team)
        AwayTeamAlias = aliased(Team)

        home_last_3_matches = db.session.query(
            FootballMatch, HomeTeamAlias.name.label('home_team_name'), AwayTeamAlias.name.label('away_team_name')
        ).outerjoin(
            HomeTeamAlias, FootballMatch.home_team_id == HomeTeamAlias.team_id
        ).outerjoin(
            AwayTeamAlias, FootballMatch.away_team_id == AwayTeamAlias.team_id
        ).filter(
            or_(FootballMatch.home_team_id == home_team_id, FootballMatch.away_team_id == home_team_id),
            FootballMatch.date < match_date_for_h3h
        ).order_by(
            desc(FootballMatch.date)
        ).limit(3).all()

        away_last_3_matches = db.session.query(
            FootballMatch, HomeTeamAlias.name.label('home_team_name'), AwayTeamAlias.name.label('away_team_name')
        ).outerjoin(
            HomeTeamAlias, FootballMatch.home_team_id == HomeTeam.team_id
        ).outerjoin(
            AwayTeamAlias, FootballMatch.away_team_id == AwayTeam.team_id
        ).filter(
            or_(FootballMatch.home_team_id == away_team_id, FootballMatch.away_team_id == away_team_id),
            FootballMatch.date < match_date_for_h3h
        ).order_by(
            desc(FootballMatch.date)
        ).limit(3).all()


    else:
        # Past match
        home_elo = match.home_elo
        away_elo = match.away_elo
        match_date_for_h3h = match.date

        home_form = MatchForm.query.filter_by(match_id=match.match_id, team_side='home').first()
        away_form = MatchForm.query.filter_by(match_id=match.match_id, team_side='away').first()

        home_stats = MatchStats.query.filter_by(match_id=match.match_id, team_side='home').first()
        away_stats = MatchStats.query.filter_by(match_id=match.match_id, team_side='away').first()

        home_value = match.home_value_ref.value if match.home_value_ref else None
        away_value = match.away_value_ref.value if match.away_value_ref else None

        predictions = match.predictions

        # H2H per team side
        home_h2h_data = home_form if home_form and home_form.h2h_matches else None
        away_h2h_data = away_form if away_form and away_form.h2h_matches else None

        # Optional summary H2H (shared)
        h2h_data = home_h2h_data or away_h2h_data

        # Fetch last 3 matches for past matches
        HomeTeamAlias = aliased(Team)
        AwayTeamAlias = aliased(Team)

        home_last_3_matches = db.session.query(
            FootballMatch, HomeTeamAlias.name.label('home_team_name'), AwayTeamAlias.name.label('away_team_name')
        ).outerjoin(
            HomeTeamAlias, FootballMatch.home_team_id == HomeTeamAlias.team_id
        ).outerjoin(
            AwayTeamAlias, FootballMatch.away_team_id == AwayTeamAlias.team_id
        ).filter(
            or_(FootballMatch.home_team_id == match.home_team_id, FootballMatch.away_team_id == match.home_team_id),
            FootballMatch.date < match_date_for_h3h
        ).order_by(
            desc(FootballMatch.date)
        ).limit(3).all()

        away_last_3_matches = db.session.query(
            FootballMatch, HomeTeamAlias.name.label('home_team_name'), AwayTeamAlias.name.label('away_team_name')
        ).outerjoin(
            HomeTeamAlias, FootballMatch.home_team_id == HomeTeamAlias.team_id
        ).outerjoin(
            AwayTeamAlias, FootballMatch.away_team_id == AwayTeamAlias.team_id
        ).filter(
            or_(FootballMatch.home_team_id == match.away_team_id, FootballMatch.away_team_id == match.away_team_id),
            FootballMatch.date < match_date_for_h3h
        ).order_by(
            desc(FootballMatch.date)
        ).limit(3).all()


    return render_template('match_detail.html',
                           match=match,
                           status=status,
                           home_form=home_form,
                           away_form=away_form,
                           home_stats=home_stats,
                           away_stats=away_stats,
                           home_value=home_value,
                           away_value=away_value,
                           home_elo=home_elo,
                           away_elo=away_elo,
                           predictions=predictions,
                           h2h_data=h2h_data,
                           home_h2h_data=home_h2h_data,
                           away_h2h_data=away_h2h_data,
                           home_last_3_matches=home_last_3_matches,
                           away_last_3_matches=away_last_3_matches)


@main.route('/league/<league_code>/team/<team_name>/<string:season_name>')
def team_view(league_code, team_name, season_name):
    # Note: If season_name (e.g., "2024 25") is used to query the Season table,
    # it must be converted back to the database format (e.g., "2024/25").
    # Example: db_season_name = season_name.replace(' ', '/') if season_name != 'all_seasons' else season_name

    # Fetch the team object to get its ID
    team = db.session.query(Team).filter_by(name=team_name).first()
    team_id = team.team_id if team else None

    # Determine a more user-friendly league name for display in the template
    display_league_name = LEAGUE_URL_MAP.get(league_code)
    if display_league_name:
        display_league_name = display_league_name.replace("premier league", "Premier League").replace("spremier league", "Scottish Premiership").title()
    else:
        display_league_name = league_code.replace("premierleague", "Premier League").replace("scotishpremierleague", "Scottish Premiership").title()

    return render_template('team.html', league_code=league_code, team_name=team_name, team_id=team_id, league_name=display_league_name, season_name=season_name)


@main.route('/league/<league_code>')
def league_view(league_code):
    db_code = LEAGUE_URL_MAP.get(league_code)
    if not db_code:
        abort(404, description=f"Nieznana liga: {league_code}")

    league = League.query.filter_by(code=db_code).first_or_404()

    # Get all available seasons for the dropdown
    all_seasons_db = db.session.query(Season.name).order_by(Season.name.desc()).all()
    # Convert list of tuples to list of strings
    available_seasons = [s[0] for s in all_seasons_db]

    # Get selected season from request arguments, default to None (meaning all seasons)
    selected_season_name = request.args.get('season')

    teams_query = db.session.query(Team).join(TeamLeague) \
        .filter(TeamLeague.league_id == league.league_id)

    if selected_season_name and selected_season_name != "all_seasons":
        season_obj = Season.query.filter_by(name=selected_season_name).first()
        if season_obj:
            teams_query = teams_query.filter(TeamLeague.season_id == season_obj.season_id)
        else:
            # If a specific season is requested but not found, fall back to all teams
            print(f"Warning: Requested season '{selected_season_name}' not found.")
            selected_season_name = "all_seasons"
    else:
        selected_season_name = "all_seasons"


    teams = teams_query.distinct().order_by(Team.name).all()

    return render_template(
        'league_view.html',
        league=league,
        teams=teams,
        league_name_to_url=LEAGUE_NAME_TO_URL,
        available_seasons=available_seasons,
        selected_season=selected_season_name
    )


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