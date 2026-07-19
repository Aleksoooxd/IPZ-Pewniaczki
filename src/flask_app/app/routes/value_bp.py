"""Value / expected-value (EV) calculator routes.

Surfaces upcoming matches where the model's implied probability exceeds the
bookmaker's (positive EV) and lets users browse the model's historical EV
against real outcomes. Odds come from :class:`FutureMatchOdds` /
:class:`MatchOdds`; probabilities from :class:`PredictedFuture` /
:class:`Predicted`.
"""

from sqlalchemy.orm import aliased
from flask import Blueprint, render_template, jsonify

from ..db import db
from ..models import (
    FutureMatch, FootballMatch, Team, League,
    PredictedFuture, Predicted,
)
from ..leagues_config import DB_TO_DISPLAY
from src.calculations.ev_calculator import (
    best_value_bet, all_value_bets, overround,
)

value_bp = Blueprint("value", __name__)


def _odds_to_dict(odds_row):
    """Pick best-available (Max*) odds, falling back to average, per outcome."""
    if odds_row is None:
        return None
    return {
        "H": odds_row.best_home or odds_row.avg_home,
        "D": odds_row.best_draw or odds_row.avg_draw,
        "A": odds_row.best_away or odds_row.avg_away,
    }


def _probs_to_dict(pred_row):
    """Project a prediction row's outcome probabilities into a dict.

    Args:
        pred_row: A :class:`Predicted` / :class:`PredictedFuture` row exposing
            ``prob_home`` / ``prob_draw`` / ``prob_away``.

    Returns:
        dict: ``{'H': p_home, 'D': p_draw, 'A': p_away}`` for the EV calculators.
    """
    return {
        "H": pred_row.prob_home,
        "D": pred_row.prob_draw,
        "A": pred_row.prob_away,
    }


def _build_upcoming_value_bets():
    """Return upcoming matches with their best EV bet, serialisable.

    Skips matches lacking either stored odds or a full probability vector
    (older :class:`PredictedFuture` rows written before probabilities were
    persisted). Sorted +EV first, then by edge descending.
    """
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    rows = (
        db.session.query(
            FutureMatch, PredictedFuture, HomeTeam, AwayTeam, League,
        )
        .join(PredictedFuture, PredictedFuture.match_id == FutureMatch.match_id)
        .join(HomeTeam, FutureMatch.home_team_id == HomeTeam.team_id)
        .join(AwayTeam, FutureMatch.away_team_id == AwayTeam.team_id)
        .join(League, FutureMatch.league_id == League.league_id)
        .outerjoin(FutureMatch.future_odds)
        .order_by(FutureMatch.date)
        .all()
    )

    bets = []
    for fm, pred, ht, at, lg in rows:
        odds_dict = _odds_to_dict(fm.future_odds)
        if not odds_dict or any(o is None for o in odds_dict.values()):
            continue
        probs = _probs_to_dict(pred)
        if any(p is None for p in probs.values()):
            continue
        best = best_value_bet(probs, odds_dict)
        if best is None:
            continue
        bets.append({
            "match_id": fm.match_id,
            "date": fm.date.strftime("%Y-%m-%d") if fm.date else None,
            "home": ht.name,
            "away": at.name,
            "league": DB_TO_DISPLAY.get(lg.code, lg.code),
            "probs": {k: (round(v, 4) if v is not None else None)
                      for k, v in probs.items()},
            "odds": {k: (round(v, 2) if v is not None else None)
                     for k, v in odds_dict.items()},
            "overround": round(
                overround(odds_dict["H"], odds_dict["D"], odds_dict["A"]) or 0, 4),
            "best": {
                "outcome": best["outcome"],
                "prob": round(best["prob"], 4),
                "odds": round(best["odds"], 2),
                "ev": round(best["ev"], 4),
                "edge_pct": round(best["edge_pct"], 2),
                "kelly": round(best["kelly"], 4) if best["kelly"] is not None else None,
            },
            "all": [
                {
                    "outcome": r["outcome"],
                    "prob": round(r["prob"], 4),
                    "odds": round(r["odds"], 2),
                    "ev": round(r["ev"], 4),
                    "edge_pct": round(r["edge_pct"], 2),
                } for r in all_value_bets(probs, odds_dict)
            ],
        })

    bets.sort(key=lambda b: (b["best"]["ev"] <= 0, -b["best"]["ev"]))
    return bets


@value_bp.route("/value-bets")
def value_bets():
    """Render the upcoming +EV bets page."""
    bets = _build_upcoming_value_bets()
    positive_count = sum(1 for b in bets if b["best"]["ev"] > 0)
    return render_template("value_bets.html", bets=bets,
                           positive_count=positive_count)


@value_bp.route("/api/value-bets")
def api_value_bets():
    """JSON feed of upcoming +EV bets (for widgets / external consumers)."""
    return jsonify(_build_upcoming_value_bets())


@value_bp.route("/value-history")
def value_history():
    """Browse past matches: model EV vs actual outcome and realised ROI."""
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    rows = (
        db.session.query(FootballMatch, Predicted, HomeTeam, AwayTeam, League)
        .join(Predicted, Predicted.match_id == FootballMatch.match_id)
        .join(HomeTeam, FootballMatch.home_team_id == HomeTeam.team_id)
        .join(AwayTeam, FootballMatch.away_team_id == AwayTeam.team_id)
        .join(League, FootballMatch.league_id == League.league_id)
        .outerjoin(FootballMatch.match_odds)
        .order_by(FootballMatch.date.desc())
        .limit(400)
        .all()
    )

    history = []
    total_staked = 0.0
    total_profit = 0.0
    wins = 0
    for m, pred, ht, at, lg in rows:
        odds_dict = _odds_to_dict(m.match_odds)
        if not odds_dict or any(o is None for o in odds_dict.values()):
            continue
        probs = _probs_to_dict(pred)
        if any(p is None for p in probs.values()):
            continue
        best = best_value_bet(probs, odds_dict)
        if best is None:
            continue
        outcome = best["outcome"]
        actual = m.result
        won = actual is not None and actual == outcome
        profit = (best["odds"] - 1) if won else -1.0
        total_staked += 1.0
        total_profit += profit
        if won:
            wins += 1
        history.append({
            "match_id": m.match_id,
            "date": m.date.strftime("%Y-%m-%d") if m.date else None,
            "home": ht.name,
            "away": at.name,
            "league": DB_TO_DISPLAY.get(lg.code, lg.code),
            "probs": {k: (round(v, 4) if v is not None else None)
                      for k, v in probs.items()},
            "odds": {k: (round(v, 2) if v is not None else None)
                     for k, v in odds_dict.items()},
            "best": {
                "outcome": outcome,
                "prob": round(best["prob"], 4),
                "odds": round(best["odds"], 2),
                "ev": round(best["ev"], 4),
                "edge_pct": round(best["edge_pct"], 2),
            },
            "actual": actual,
            "won": won,
            "profit": round(profit, 2),
        })

    history.sort(key=lambda b: (b["best"]["ev"] <= 0, -b["best"]["ev"]))
    roi = (total_profit / total_staked * 100) if total_staked else None
    return render_template(
        "value_history.html",
        history=history,
        total_staked=round(total_staked, 2),
        total_profit=round(total_profit, 2),
        roi=round(roi, 2) if roi is not None else None,
        wins=wins,
    )
