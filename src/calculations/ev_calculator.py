"""Expected-value (EV) math for the value-bet calculator.

Pure, side-effect-free functions that turn a model's outcome probabilities and
bookmaker decimal odds into edge / EV / Kelly metrics. No database or Flask
dependencies, so the module is trivially unit-testable.

All functions are defensive: missing or malformed inputs return ``None`` rather
than raising, so callers can simply skip an outcome when data is absent.
"""

from typing import Optional

OUTCOMES = ("H", "D", "A")


def decimal_to_implied(odds: Optional[float]) -> Optional[float]:
    """Convert a decimal odds value to its implied probability (``1/odds``)."""
    if odds is None:
        return None
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if o <= 0:
        return None
    return 1.0 / o


def overround(home: Optional[float], draw: Optional[float],
              away: Optional[float]) -> Optional[float]:
    """Sum of the three implied probabilities — the bookmaker margin.

    A value > 1 means vig is baked in; ~1.08-1.12 is typical. Returns ``None``
    when no valid odds are supplied.
    """
    vals = [decimal_to_implied(home), decimal_to_implied(draw),
            decimal_to_implied(away)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def expected_value(prob: Optional[float], odds: Optional[float]) -> Optional[float]:
    """EV of a 1-unit bet at decimal ``odds`` given true probability ``prob``.

    ``EV = prob * odds - 1``. Positive => +edge over the bookmaker. Returns
    ``None`` when inputs are invalid (prob outside [0, 1], odds <= 1).
    """
    if prob is None or odds is None:
        return None
    try:
        p = float(prob)
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if p < 0 or p > 1 or o <= 1:
        return None
    return p * o - 1.0


def edge_pct(ev: Optional[float]) -> Optional[float]:
    """EV expressed as a percentage of the stake."""
    if ev is None:
        return None
    return ev * 100.0


def kelly_fraction(prob: Optional[float], odds: Optional[float],
                   fraction: float = 0.25) -> Optional[float]:
    """Fractional-Kelly suggested stake as a fraction of bankroll.

    Full Kelly is ``(p*o - 1) / (o - 1)``; we return ``fraction`` of it
    (default 0.25 = quarter-Kelly, a conservative sizing), clamped to [0, 1].
    Returns ``0.0`` for non-positive edge and ``None`` for invalid inputs.
    """
    if prob is None or odds is None:
        return None
    try:
        p = float(prob)
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if p <= 0 or p > 1 or o <= 1:
        return None
    full = (p * o - 1.0) / (o - 1.0)
    if full <= 0:
        return 0.0
    return max(0.0, min(1.0, fraction * full))


def _bet_row(outcome: str, prob, odds) -> Optional[dict]:
    """Build a single outcome's EV row, or ``None`` if uncomputable."""
    ev = expected_value(prob, odds)
    if ev is None:
        return None
    return {
        "outcome": outcome,
        "prob": prob,
        "odds": odds,
        "ev": ev,
        "edge_pct": edge_pct(ev),
        "kelly": kelly_fraction(prob, odds),
    }


def best_value_bet(probs: dict, odds: dict,
                   outcomes=OUTCOMES) -> Optional[dict]:
    """Find the single highest-EV outcome among the three.

    Args:
        probs (dict): ``{'H': p_home, 'D': p_draw, 'A': p_away}`` model probs.
        odds (dict): ``{'H': o_home, 'D': o_draw, 'A': o_away}`` decimal odds.
        outcomes: Ordering of the three outcomes.

    Returns:
        dict or None: The best EV row (``outcome/prob/odds/ev/edge_pct/kelly``),
        or ``None`` when no outcome has both a probability and odds.
    """
    best = None
    for oc in outcomes:
        row = _bet_row(oc, probs.get(oc), odds.get(oc))
        if row is None:
            continue
        if best is None or row["ev"] > best["ev"]:
            best = row
    return best


def all_value_bets(probs: dict, odds: dict,
                   outcomes=OUTCOMES) -> list:
    """Return an EV row for every outcome that has both a prob and odds."""
    rows = []
    for oc in outcomes:
        row = _bet_row(oc, probs.get(oc), odds.get(oc))
        if row is not None:
            rows.append(row)
    return rows
