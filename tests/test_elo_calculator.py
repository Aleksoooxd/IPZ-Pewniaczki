"""Unit tests for `calculate_elo_change` (elo_calculator.py:8-31).

`calculate_elo_change` is a pure function: it maps (home_elo, away_elo, result,
goal_diff) -> (home_change, away_change). These tests lock in the ELO math,
including the home-advantage term, the expected-score formula, and the
goal-margin multiplier.
"""

from src.calculations.elo_calculator import calculate_elo_change


def _expected_home_win_change():
    """Compute the expected home ELO change at equal ratings.

    Helper that mirrors the function's math at equal ELO: home gains
    +100 (HOME_ADVANTAGE) with K=40, returning ``round(40 * (1 - exp_home), 2)``.
    Used to assert the exact numeric ELO change the function should produce.

    Returns:
        float: The expected rounded home rating change at equal ELO.
    """
    # At equal ELO, home gets +100 (HOME_ADVANTAGE) and K=40.
    exp_home = 1.0 / (1.0 + 10.0 ** (-100.0 / 400.0))
    return round(40 * (1.0 - exp_home), 2)


def test_equal_elo_home_win_favours_home():
    """Verify a home win at equal ELO gains for home and loses for away.

    At equal ratings a home win should move the home rating up and the away
    rating down.

    Returns:
        None.
    """
    home, away = calculate_elo_change(1500, 1500, "H")
    assert home > 0
    assert away < 0


def test_draw_moves_rating_from_home_favourite():
    """Verify a draw at equal ELO costs the home side and is zero-sum.

    Because of the +100 home advantage, a draw is worse than expected for the
    home side, so home loses rating while away gains; the two changes sum to 0.

    Returns:
        None.
    """
    # A draw at equal rating still "costs" the home side rating because the
    # +100 home advantage makes a draw a worse-than-expected result for them.
    home, away = calculate_elo_change(1500, 1500, "D")
    assert home < 0
    assert away > 0
    assert round(home + away, 2) == 0.0


def test_changes_always_sum_to_zero():
    """Verify ELO changes are zero-sum across all results.

    Whatever one side gains the other loses; even with a 3-goal margin the
    changes for every result (H/D/A) should round to a net sum of 0.

    Returns:
        None.
    """
    # ELO is zero-sum: whatever one side gains, the other loses (the margin
    # multiplier scales both sides equally, so the invariant holds).
    for result in ("H", "D", "A"):
        h, a = calculate_elo_change(1500, 1500, result, goal_diff=3)
        assert round(h + a, 2) == 0.0


def test_exact_expected_score_at_equal_elo():
    """Verify the exact numeric home change matches the closed-form expectation.

    The home change for a home win at equal ELO must equal the value computed by
    ``_expected_home_win_change`` and the away change its negation.

    Returns:
        None.
    """
    expected = _expected_home_win_change()
    home, away = calculate_elo_change(1500, 1500, "H")
    assert home == expected
    assert away == -expected


def test_margin_factor_no_boost_for_one_goal():
    """Verify a single-goal win applies no margin multiplier.

    With goal_diff == 1 the margin factor is 1, so the resulting home change
    equals the change computed with no goal_diff at all.

    Returns:
        None.
    """
    # goal_diff == 1 -> margin_factor = 1 + 0.75*(0)/3 = 1, so K stays 40.
    h_one, _ = calculate_elo_change(1500, 1500, "H", goal_diff=1)
    h_none, _ = calculate_elo_change(1500, 1500, "H", goal_diff=None)
    assert h_one == h_none


def test_margin_factor_boosts_large_goal_difference():
    """Verify a large goal difference boosts the margin multiplier.

    A 4-goal home win should produce a larger home rating change than a 1-goal
    home win, confirming the goal-margin multiplier scales with the difference.

    Returns:
        None.
    """
    h_small, _ = calculate_elo_change(1500, 1500, "H", goal_diff=1)
    h_big, _ = calculate_elo_change(1500, 1500, "H", goal_diff=4)
    assert h_big > h_small


def test_margin_factor_capped_at_1_75():
    """Verify the margin multiplier saturates at 1.75.

    For goal_diff >= 4 the multiplier is capped at 1.75 (K -> 70), so a 4-goal
    and a 10-goal home win yield the same change, and that change matches the
    closed-form capped value.

    Returns:
        None.
    """
    # goal_diff >= 4 saturates the multiplier at 1.75 (K -> 70).
    h_four, _ = calculate_elo_change(1500, 1500, "H", goal_diff=4)
    h_ten, _ = calculate_elo_change(1500, 1500, "H", goal_diff=10)
    assert h_four == h_ten
    # Mirror the function exactly: exp_home is rounded to 4 dp before applying K.
    exp_home = round(1.0 / (1.0 + 10.0 ** (-100.0 / 400.0)), 4)
    assert h_four == round(70 * (1.0 - exp_home), 2)


def test_away_win_rewards_away_team():
    """Verify an away win rewards the away team and costs the home team.

    At equal ELO an away win moves the away rating up and the home rating down.

    Returns:
        None.
    """
    home, away = calculate_elo_change(1500, 1500, "A")
    assert home < 0
    assert away > 0


def test_higher_elo_away_team_beating_home_gains_rating():
    """Verify a higher-ELO away team beating home gains rating and stays zero-sum.

    When the away team is rated higher (1600 vs 1500) and wins, it gains rating
    and the two changes still sum to zero.

    Returns:
        None.
    """
    home, away = calculate_elo_change(1500, 1600, "A")
    assert away > 0
    assert round(home + away, 2) == 0.0


def test_draw_ignores_goal_diff_for_margin():
    """Verify the margin multiplier is ignored for draws.

    The goal-margin multiplier only applies to non-draw results, so a draw with
    a 10-goal difference yields the same change as a draw with none.

    Returns:
        None.
    """
    # The margin multiplier only applies when result != 'D'.
    h_with, _ = calculate_elo_change(1500, 1500, "D", goal_diff=10)
    h_without, _ = calculate_elo_change(1500, 1500, "D")
    assert h_with == h_without


def test_unknown_result_defaults_to_away_win():
    """Verify an unknown result falls through to away-win semantics.

    A result code with no matching branch ("X") hits the else clause, so the
    home rating drops, the away rating rises, and they still sum to zero.

    Returns:
        None.
    """
    # No branch matches -> falls through to the else (away win) semantics.
    home, away = calculate_elo_change(1500, 1500, "X")
    assert home < 0
    assert away > 0
    assert round(home + away, 2) == 0.0
