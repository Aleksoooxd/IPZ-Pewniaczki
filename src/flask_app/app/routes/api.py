import datetime
import re

from sqlalchemy import or_
from sqlalchemy.orm import aliased
from flask import Blueprint, jsonify, request, url_for

from ..db import db
from ..models import FootballMatch, FutureMatch, Team, League, TeamLeague, Season, PredictedFuture
from ..leagues_config import LEAGUES, DB_TO_URL, DB_TO_DISPLAY, URL_TO_DISPLAY

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/matches")
def get_matches():
    """Return all past and future matches on a given date as JSON.

    Requires a ``?date=YYYY-MM-DD`` query parameter. Past matches include
    their final scores; future matches report ``home_goals``/``away_goals``
    as ``null``. Both sets are unioned into a single list, each entry tagged
    with ``match_type`` of ``"past"`` or ``"future"``.

    Args:
        None (reads the ``date`` request query parameter)

    Returns:
        flask.Response: A JSON list of match dicts, or a 400 error object
        when the date parameter is missing or malformed.
    """
    date_param = request.args.get("date")
    if not date_param:
        return jsonify({"error": "Missing 'date' parameter"}), 400

    try:
        match_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    def _base(model, is_future):
        """Build a base match query for one match model.

        Projects the match id/date, both team names and ids (via aliased
        ``Team`` joins), the league code, the home/away goals, and the model
        prediction (result + confidence) for future matches. For past matches
        the goal and prediction columns are emitted as ``NULL`` literals.

        Args:
            model: The match ORM model (``FootballMatch`` or ``FutureMatch``).
            is_future (bool): True when ``model`` is the future model, in which
                case goals are rendered as ``NULL``.

        Returns:
            sqlalchemy.orm.Query: A partially-built query filtered to
            ``model.date == match_date``, ready to be union-ed / executed.
        """
        home_goals = db.literal(None) if is_future else model.fthg
        away_goals = db.literal(None) if is_future else model.ftag
        pred_result = db.literal(None)
        pred_conf = db.literal(None)
        if is_future:
            pred_result = PredictedFuture.predicted_result
            pred_conf = PredictedFuture.confidence
        query = db.session.query(
            model.match_id, model.date,
            HomeTeam.name.label("home_team"),
            HomeTeam.team_id.label("home_team_id"),
            AwayTeam.name.label("away_team"),
            AwayTeam.team_id.label("away_team_id"),
            League.code.label("league"),
            home_goals.label("home_goals"),
            away_goals.label("away_goals"),
            pred_result.label("predicted_result"),
            pred_conf.label("confidence"),
        ).join(HomeTeam, model.home_team_id == HomeTeam.team_id
        ).join(AwayTeam, model.away_team_id == AwayTeam.team_id
        ).join(League, model.league_id == League.league_id
        )
        if is_future:
            query = query.outerjoin(
                PredictedFuture, model.match_id == PredictedFuture.match_id
            )
        return query.filter(model.date == match_date)

    matches = _base(FootballMatch, False).union_all(_base(FutureMatch, True)).all()

    return jsonify([
        dict(
            match_id=m.match_id,
            match_type="past" if m.home_goals is not None else "future",
            date=m.date.strftime("%Y-%m-%d"),
            home_team=m.home_team, home_team_id=m.home_team_id,
            away_team=m.away_team, away_team_id=m.away_team_id,
            league=m.league,
            home_goals=m.home_goals, away_goals=m.away_goals,
            predicted_result=m.predicted_result,
            confidence=m.confidence,
        ) for m in matches
    ])


def _league_display(db_code):
    """Map a league DB code to its human-readable display name.

    Args:
        db_code (str): The ``league.code`` DB value.

    Returns:
        str: Display name from ``leagues_config``, or the raw code as fallback.
    """
    return URL_TO_DISPLAY.get(DB_TO_URL.get(db_code, db_code), db_code)


def _team_link(team_id):
    """Resolve a navigable URL for a team's most recent league/season.

    Picks the team's latest ``TeamLeague`` (by season name, descending) and
    builds the ``/league/<code>/team/<name>/<season>`` URL the team view
    expects. Returns ``None`` when the team has no league association (so the
    UI can render the match without a broken link).

    Args:
        team_id (int): ``Team.team_id`` to resolve.

    Returns:
        str or None: The team page URL, or ``None`` if unresolved.
    """
    tl = (
        db.session.query(TeamLeague)
        .join(League, League.league_id == TeamLeague.league_id)
        .join(Season, Season.season_id == TeamLeague.season_id)
        .filter(TeamLeague.team_id == team_id)
        .order_by(Season.name.desc())
        .first()
    )
    if not tl:
        return None
    url_code = DB_TO_URL.get(tl.league.code, tl.league.code)
    season_url = tl.season.name.replace("/", " ")
    return url_for(
        "teams.team_view",
        league_code=url_code,
        team_name=tl.team.name,
        season_name=season_url,
    )


def _team_logo_url(name):
    """Build the static-logo URL for a team, matching the rest of the app.

    Mirrors the convention used by the match/team templates: lower-cased name
    with spaces replaced by hyphens, under ``img/logos/64x64/``.

    Args:
        name (str): ``Team.name`` to build a logo path for.

    Returns:
        str: The ``static`` URL for the team's logo image.
    """
    safe = name.lower().replace(" ", "-")
    return url_for("static", filename=f"img/logos/64x64/{safe}.png")


@api_bp.route("/search")
def search():
    """Live-search teams, leagues and matches by free-text query.

    Returns up to a handful of matches per category as a JSON object with
    ``teams``, ``leagues`` and ``matches`` arrays. Teams link to their most
    recent season page; leagues to the league view; matches to the relevant
    past/future detail page. Queries shorter than two characters return empty
    arrays (the navbar only fires once the user has typed enough).

    Args:
        None (reads the ``q`` request query parameter)

    Returns:
        flask.Response: A JSON object keyed by category, each an array of
        ``{name, url, ...}`` result dicts.
    """
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"teams": [], "leagues": [], "matches": []})

    like = f"%{q}%"
    out = {"teams": [], "leagues": [], "matches": []}

    # ── Teams ───────────────────────────────────────────────
    teams = db.session.query(Team).filter(
        Team.name.ilike(like)
    ).order_by(Team.name).limit(8).all()
    for t in teams:
        out["teams"].append({
            "name": t.name,
            "url": _team_link(t.team_id),
            "logo": _team_logo_url(t.name),
        })

    # ── Leagues (ilike on the league code, mapped to display/url/logo) ──
    for lg_row in db.session.query(League).filter(League.code.ilike(like)).all():
        code = lg_row.code
        display = DB_TO_DISPLAY.get(code, code)
        url_code = DB_TO_URL.get(code, code)
        flag = next((l["flag"] for l in LEAGUES if l["db_code"] == code), None)
        out["leagues"].append({
            "name": display,
            "url": url_for("leagues.league_view", league_code=url_code),
            "logo": url_for("static", filename=f"img/flags/{flag}-small.png") if flag else None,
        })

    # ── Matches ─────────────────────────────────────────────
    # Normalize the query: drop "vs / v / przeciwko / dash" separators so a
    # "Team A vs Team B" phrase becomes a flat list of team-name fragments.
    norm_q = re.sub(r"\b(?:vs\.?|v|przeciwko)\b|\s-\s", " ", q, flags=re.IGNORECASE).lower()
    query_words = [w for w in norm_q.split() if len(w) >= 2]
    all_team_names = db.session.query(Team.team_id, Team.name).all()

    # Detect which teams the user *mentioned*, supporting partial names (so
    # "Ars Man" resolves to Arsenal vs Manchester United instead of requiring
    # the full official names). Each team gets the set of query words that are
    # a *prefix* of one of its name words; a head-to-head is formed only when
    # two teams can be anchored to two *distinct* query words — this avoids
    # false pairs from a single ambiguous fragment such as "man", and prefix
    # (not bare substring) matching avoids false hits like "che" in "manchester".
    _NOISE = {"fc", "cf", "afc", "ac", "sc"}
    query_words = [w for w in query_words if w not in _NOISE]
    candidates = []
    for t in all_team_names:
        team_words = t.name.lower().split()
        matched = {w for w in query_words if any(tw.startswith(w) for tw in team_words)}
        if matched:
            candidates.append((t, matched))

    candidates.sort(key=lambda c: (len(c[1]), c[0].name), reverse=True)

    used_words = set()
    mentioned = []
    for t, matched in candidates:
        if matched - used_words:
            used_words |= matched
            mentioned.append(t)
            if len(mentioned) == 2:
                break

    head_to_head = tuple(m.team_id for m in mentioned) if len(mentioned) == 2 else None

    def _head_to_head_filter(model, a, b):
        """Filter for fixtures between two specific teams (either side).

        Args:
            model: ``FootballMatch`` or ``FutureMatch`` (the column owner).
            a, b (int): The two ``team_id`` values.

        Returns:
            sqlalchemy.sql.elements.BooleanClauseList: An OR of the two possible
            home/away orderings for that model's columns.
        """
        return or_(
            (model.home_team_id == a) & (model.away_team_id == b),
            (model.home_team_id == b) & (model.away_team_id == a),
        )

    def _collect_matches(model, alias_a, alias_b, match_filter, limit=12):
        """Query past/future matches and project them as result dicts.

        Args:
            model: ``FootballMatch`` or ``FutureMatch``.
            alias_a, alias_b: Aliased ``Team`` for the home/away name joins.
            match_filter: SQLAlchemy filter selecting which matches to return.
            limit (int, optional): Max rows to return. Defaults to 12.

        Returns:
            list[dict]: Match result dicts with home/away names, logos, league,
            date and a detail-page URL.
        """
        rows = (
            db.session.query(
                model.match_id, model.date,
                alias_a.name.label("home"), alias_b.name.label("away"),
                League.code.label("league"),
            )
            .join(alias_a, model.home_team_id == alias_a.team_id)
            .join(alias_b, model.away_team_id == alias_b.team_id)
            .join(League, model.league_id == League.league_id)
            .filter(match_filter)
            .order_by(model.date.desc())
            .limit(limit)
            .all()
        )
        match_type = "future" if model is FutureMatch else "past"
        return [
            {
                "home": home, "away": away,
                "home_logo": _team_logo_url(home),
                "away_logo": _team_logo_url(away),
                "date": date.strftime("%Y-%m-%d") if date else "",
                "league": _league_display(league),
                "url": url_for("matches.match_detail", match_type=match_type, match_id=mid),
            }
            for mid, date, home, away, league in rows
        ]

    HomeTeamA = aliased(Team)
    AwayTeamA = aliased(Team)
    match_filter = _head_to_head_filter(FootballMatch, *head_to_head) if head_to_head \
        else or_(HomeTeamA.name.ilike(like), AwayTeamA.name.ilike(like))
    out["matches"] += _collect_matches(FootballMatch, HomeTeamA, AwayTeamA, match_filter)

    FutureTeamA = aliased(Team)
    FutureTeamB = aliased(Team)
    future_filter = _head_to_head_filter(FutureMatch, *head_to_head) if head_to_head \
        else or_(FutureTeamA.name.ilike(like), FutureTeamB.name.ilike(like))
    out["matches"] += _collect_matches(FutureMatch, FutureTeamA, FutureTeamB, future_filter)

    # Sort matches chronologically (most recent first) and cap the combined list.
    out["matches"].sort(key=lambda m: m["date"], reverse=True)
    out["matches"] = out["matches"][:12]

    return jsonify(out)