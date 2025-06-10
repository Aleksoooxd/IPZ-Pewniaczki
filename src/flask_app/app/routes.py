# src/flask_app/app/routes.py
import datetime
from sqlalchemy import or_, desc, and_ # Added and_ for combined filtering
from sqlalchemy.orm import aliased
from flask import Blueprint, render_template, request, abort, jsonify, redirect, url_for
from .db import db, FootballMatch, Team, League, FutureMatch, TeamValue, Predicted, MatchStats, MatchForm, TeamElo, \
    TeamLeague, Season, PredictedFuture

main = Blueprint('main', __name__)


@main.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':

        pass
    return render_template('index.html')


@main.route('/main')
def mainpage():
    date_param = request.args.get('date')
    if not date_param:
        today = datetime.date.today().strftime('%Y-%m-%d')
        return redirect(url_for('main.mainpage', date=today))

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
        match_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

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

LEAGUE_NAME_TO_URL = {
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
    current_year = datetime.datetime.now().year
    if datetime.datetime.now().month < 8:
        season = f"{current_year - 1}/{str(current_year)[-2:]}"
    else:
        season = f"{current_year}/{str(current_year + 1)[-2:]}"
    return season


@main.route('/match/<string:match_type>/<int:match_id>')
def match_detail(match_type, match_id):
    from datetime import date
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

    home_form = None
    away_form = None
    home_stats = None
    away_stats = None
    home_value = None
    away_value = None
    home_elo = None
    away_elo = None
    predictions = []
    home_h2h_data = None
    away_h2h_data = None
    home_last_3_matches = []
    away_last_3_matches = []

    home_team_id = match.home_team_id
    away_team_id = match.away_team_id
    match_date_for_h3h = match.date
    season_id = match.season.season_id if match.season else None

    if isinstance(match, FutureMatch):
        home_elo_obj = TeamElo.query.filter_by(team_id=home_team_id).order_by(desc(TeamElo.last_updated)).first()
        away_elo_obj = TeamElo.query.filter_by(team_id=away_team_id).order_by(desc(TeamElo.last_updated)).first()
        home_elo = home_elo_obj.rating if home_elo_obj else None
        away_elo = away_elo_obj.rating if away_elo_obj else None

        if season_id:
            home_value_obj = TeamValue.query.filter_by(team_id=home_team_id, season_id=season_id).first()
            away_value_obj = TeamValue.query.filter_by(team_id=away_team_id, season_id=season_id).first()
            home_value = home_value_obj.value if home_value_obj else None
            away_value = away_value_obj.value if away_value_obj else None

        predictions = PredictedFuture.query.filter_by(match_id=match_id).all()

        HomeTeamAlias = aliased(Team)
        AwayTeamAlias = aliased(Team)

        latest_home_past_match = db.session.query(FootballMatch).filter(
            or_(FootballMatch.home_team_id == home_team_id, FootballMatch.away_team_id == home_team_id),
            FootballMatch.date < match_date_for_h3h,
            FootballMatch.result.isnot(None)
        ).order_by(desc(FootballMatch.date), desc(FootballMatch.match_id)).first()

        if latest_home_past_match:
            team_side_in_last_match = 'home' if latest_home_past_match.home_team_id == home_team_id else 'away'
            home_form = MatchForm.query.filter_by(match_id=latest_home_past_match.match_id,
                                                  team_side=team_side_in_last_match).first()

        latest_away_past_match = db.session.query(FootballMatch).filter(
            or_(FootballMatch.home_team_id == away_team_id, FootballMatch.away_team_id == away_team_id),
            FootballMatch.date < match_date_for_h3h,
            FootballMatch.result.isnot(None)
        ).order_by(desc(FootballMatch.date), desc(FootballMatch.match_id)).first()

        if latest_away_past_match:
            team_side_in_last_match = 'home' if latest_away_past_match.home_team_id == away_team_id else 'away'
            away_form = MatchForm.query.filter_by(match_id=latest_away_past_match.match_id,
                                                  team_side=team_side_in_last_match).first()

        past_h2h_matches = db.session.query(FootballMatch).filter(
            or_(
                (FootballMatch.home_team_id == home_team_id) & (FootballMatch.away_team_id == away_team_id),
                (FootballMatch.home_team_id == away_team_id) & (FootballMatch.away_team_id == home_team_id)
            ),
            FootballMatch.date < match_date_for_h3h,
            FootballMatch.result.isnot(None)
        ).order_by(desc(FootballMatch.date)).all()

        h2h_matches_count = len(past_h2h_matches)
        h2h_home_wins_count = 0
        h2h_draws_count = 0
        h2h_away_wins_count = 0
        h2h_home_goals_for = 0
        h2h_home_goals_against = 0
        h2h_last_5_points_home = 0

        for h2h_match in past_h2h_matches:
            if h2h_match.home_team_id == home_team_id:
                if h2h_match.result == 'H':
                    h2h_home_wins_count += 1
                    h2h_last_5_points_home += 3
                elif h2h_match.result == 'D':
                    h2h_draws_count += 1
                    h2h_last_5_points_home += 1
                else:
                    h2h_away_wins_count += 1
                    h2h_last_5_points_home += 0
                h2h_home_goals_for += (h2h_match.fthg or 0)
                h2h_home_goals_against += (h2h_match.ftag or 0)
            else:
                if h2h_match.result == 'A':
                    h2h_home_wins_count += 1
                    h2h_last_5_points_home += 3
                elif h2h_match.result == 'D':
                    h2h_draws_count += 1
                    h2h_last_5_points_home += 1
                else:
                    h2h_away_wins_count += 1
                    h2h_last_5_points_home += 0
                h2h_home_goals_for += (h2h_match.ftag or 0)
                h2h_home_goals_against += (h2h_match.fthg or 0)

        home_h2h_data = {
            'h2h_matches': h2h_matches_count,
            'h2h_wins': h2h_home_wins_count,
            'h2h_draws': h2h_draws_count,
            'h2h_losses': h2h_matches_count - h2h_home_wins_count - h2h_draws_count,
            'h2h_goals_for': h2h_home_goals_for,
            'h2h_goals_against': h2h_home_goals_against,
            'h2h_last_5_points': h2h_last_5_points_home
        }
        away_h2h_data = {
            'h2h_matches': h2h_matches_count,
            'h2h_wins': h2h_away_wins_count,
            'h2h_draws': h2h_draws_count,
            'h2h_losses': h2h_home_wins_count,
            'h2h_goals_for': h2h_home_goals_against,
            'h2h_goals_against': h2h_home_goals_for,
            'h2h_last_5_points': h2h_last_5_points_home
        }

        home_last_3_matches = db.session.query(
            FootballMatch, HomeTeamAlias.name.label('home_team_name'), AwayTeamAlias.name.label('away_team_name')
        ).outerjoin(
            HomeTeamAlias, FootballMatch.home_team_id == HomeTeamAlias.team_id
        ).outerjoin(
            AwayTeamAlias, FootballMatch.away_team_id == AwayTeamAlias.team_id
        ).filter(
            or_(FootballMatch.home_team_id == home_team_id, FootballMatch.away_team_id == home_team_id),
            FootballMatch.date < match_date_for_h3h,
            FootballMatch.result.isnot(None)
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
            or_(FootballMatch.home_team_id == away_team_id, FootballMatch.away_team_id == away_team_id),
            FootballMatch.date < match_date_for_h3h,
            FootballMatch.result.isnot(None)
        ).order_by(
            desc(FootballMatch.date)
        ).limit(3).all()


    else:
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

        home_h2h_data = home_form if home_form and home_form.h2h_matches else None
        away_h2h_data = away_form if away_form and away_form.h2h_matches else None

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
                           home_h2h_data=home_h2h_data,
                           away_h2h_data=away_h2h_data,
                           home_last_3_matches=home_last_3_matches,
                           away_last_3_matches=away_last_3_matches)


@main.route('/league/<league_code>/team/<team_name>/<string:season_name>')
def team_view(league_code, team_name, season_name):
    team = db.session.query(Team).filter_by(name=team_name).first()
    team_id = team.team_id if team else None

    display_league_name = LEAGUE_URL_MAP.get(league_code)
    if display_league_name:
        display_league_name = display_league_name.replace("premier league", "Premier League").replace("spremier league",
                                                                                                      "Scottish Premiership").title()
    else:
        display_league_name = league_code.replace("premierleague", "Premier League").replace("scotishpremierleague",
                                                                                             "Scottish Premiership").title()

    return render_template('team.html', league_code=league_code, team_name=team_name, team_id=team_id,
                           league_name=display_league_name, season_name=season_name)


def calculate_standings_for_league_and_season(league_id, season_id=None, matchday_filter=None): # Added matchday_filter
    standings = {}

    matches_query = db.session.query(FootballMatch) \
        .filter(FootballMatch.league_id == league_id)

    if season_id:
        matches_query = matches_query.filter(FootballMatch.season_id == season_id)

    # Apply matchday filter if provided
    if matchday_filter is not None:
        matches_query = matches_query.filter(
            or_(
                FootballMatch.home_matchday <= matchday_filter,
                FootballMatch.away_matchday <= matchday_filter
            )
        )

    matches = matches_query.order_by(FootballMatch.date, FootballMatch.home_matchday).all() # Ordered by date and matchday

    for match in matches:
        home_team_id = match.home_team_id
        away_team_id = match.away_team_id
        home_goals = match.fthg if match.fthg is not None else 0
        away_goals = match.ftag if match.ftag is not None else 0
        result = match.result

        if home_team_id not in standings:
            home_team_obj = db.session.get(Team, home_team_id)
            home_team_name = home_team_obj.name
            standings[home_team_id] = {'points': 0, 'played': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0,
                                       'goals_against': 0, 'goal_diff': 0, 'team_name': home_team_name,
                                       'team_id': home_team_id}
        if away_team_id not in standings:
            away_team_obj = db.session.get(Team, away_team_id)
            away_team_name = away_team_obj.name
            standings[away_team_id] = {'points': 0, 'played': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0,
                                       'goals_against': 0, 'goal_diff': 0, 'team_name': away_team_name,
                                       'team_id': away_team_id}

        standings[home_team_id]['played'] += 1
        standings[away_team_id]['played'] += 1

        if result == 'H':
            standings[home_team_id]['points'] += 3
            standings[home_team_id]['wins'] += 1
            standings[away_team_id]['losses'] += 1
        elif result == 'D':
            standings[home_team_id]['points'] += 1
            standings[away_team_id]['points'] += 1
            standings[home_team_id]['draws'] += 1
            standings[away_team_id]['draws'] += 1
        elif result == 'A':
            standings[away_team_id]['points'] += 3
            standings[away_team_id]['wins'] += 1
            standings[home_team_id]['losses'] += 1

        standings[home_team_id]['goals_for'] += home_goals
        standings[home_team_id]['goals_against'] += away_goals
        standings[home_team_id]['goal_diff'] = standings[home_team_id]['goals_for'] - standings[home_team_id][
            'goals_against']

        standings[away_team_id]['goals_for'] += away_goals
        standings[away_team_id]['goals_against'] += home_goals
        standings[away_team_id]['goal_diff'] = standings[away_team_id]['goals_for'] - standings[away_team_id][
            'goals_against']

    sorted_standings = sorted(standings.values(),
                              key=lambda x: (-x['points'], -x['goal_diff'], -x['goals_for'], x['team_name']))
    for i, team_data in enumerate(sorted_standings):
        team_data['position'] = i + 1

    return sorted_standings


@main.route('/league/<league_code>')
def league_view(league_code):
    db_code = LEAGUE_URL_MAP.get(league_code)
    if not db_code:
        abort(404, description=f"Nieznana liga: {league_code}")

    league = League.query.filter_by(code=db_code).first_or_404()

    all_seasons_db = db.session.query(Season.name).order_by(Season.name.desc()).all()
    available_seasons = [s[0] for s in all_seasons_db]

    selected_season_name = request.args.get('season')
    selected_matchday = request.args.get('matchday', type=int) # New: Get matchday from request

    teams_query = db.session.query(Team).join(TeamLeague) \
        .filter(TeamLeague.league_id == league.league_id)

    current_season_standings = []
    standings_season_display_name = "Wybierz sezon"
    available_matchdays = [] # New: To store available matchdays

    if selected_season_name and selected_season_name != "all_seasons":
        season_obj = Season.query.filter_by(name=selected_season_name).first()
        if season_obj:
            teams_query = teams_query.filter(TeamLeague.season_id == season_obj.season_id)

            # Get max matchday for the selected season
            max_matchday_result = db.session.query(
                db.func.max(FootballMatch.home_matchday)
            ).filter(
                FootballMatch.league_id == league.league_id,
                FootballMatch.season_id == season_obj.season_id
            ).scalar()

            if max_matchday_result:
                available_matchdays = list(range(1, max_matchday_result + 1))

            current_season_standings = calculate_standings_for_league_and_season(
                league.league_id, season_obj.season_id, selected_matchday # Pass selected_matchday
            )
            standings_season_display_name = selected_season_name
        else:
            print(f"Warning: Requested season '{selected_season_name}' not found for team filtering.")
            selected_season_name = "all_seasons"
    else:
        selected_season_name = "all_seasons"
        # For "Wszech Czasów", we might not need a matchday filter or calculate it differently
        current_season_standings = calculate_standings_for_league_and_season(league.league_id)
        standings_season_display_name = "Wszech Czasów"

    teams = teams_query.distinct().order_by(Team.name).all()

    return render_template(
        'league_view.html',
        league=league,
        teams=teams,
        league_name_to_url=LEAGUE_NAME_TO_URL,
        available_seasons=available_seasons,
        selected_season=selected_season_name,
        standings=current_season_standings,
        standings_season_display_name=standings_season_display_name,
        available_matchdays=available_matchdays,  # New: Pass available matchdays
        selected_matchday=selected_matchday # New: Pass selected_matchday
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