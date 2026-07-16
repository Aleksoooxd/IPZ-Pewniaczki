"""Unit tests for the dispersion/inequality indices in helpfunctions.py.

These take a NumPy array of values (e.g. per-row bookmaker odds) and return a
rounded scalar. They're pure math, so they're easy to lock down with closed-form
expectations.
"""

import numpy as np

from src.calculations.helpfunctions import (
    shannon_index,
    coefficient_of_variation,
    gini_index,
    hhi_index,
)


# --- shannon_index (base-2 entropy of the normalised values) ---------------

def test_shannon_uniform_two_way_is_one_bit():
    """Verify two equal values give Shannon entropy of exactly 1 bit.

    A uniform distribution over two equally-weighted outcomes has maximum
    entropy of 1.0 bit, so ``shannon_index([1.0, 1.0])`` should equal 1.0.

    Returns:
        None.
    """
    assert shannon_index(np.array([1.0, 1.0])) == 1.0


def test_shannon_uniform_four_way_is_two_bits():
    """Verify four equal values give Shannon entropy of exactly 2 bits.

    A uniform distribution over four equally-weighted outcomes has maximum
    entropy of 2.0 bits, so ``shannon_index([1.0, 1.0, 1.0, 1.0])`` should
    equal 2.0.

    Returns:
        None.
    """
    assert shannon_index(np.array([1.0, 1.0, 1.0, 1.0])) == 2.0


def test_shannon_is_scale_invariant():
    """Verify Shannon index is invariant to scaling all values.

    Because the values are normalised before taking entropy, multiplying every
    value by a constant leaves the index unchanged.

    Returns:
        None.
    """
    assert shannon_index(np.array([1.0, 1.0, 1.0, 1.0])) == shannon_index(
        np.array([10.0, 10.0, 10.0, 10.0])
    )


def test_shannon_decreases_as_distribution_concentrates():
    """Verify concentration lowers Shannon entropy.

    A highly concentrated distribution (one large value, the rest tiny) has
    lower entropy than the uniform distribution, confirming the index responds
    to inequality as expected.

    Returns:
        None.
    """
    uniform = shannon_index(np.array([1.0, 1.0, 1.0, 1.0]))
    concentrated = shannon_index(np.array([100.0, 0.0001, 0.0001, 0.0001]))
    assert concentrated < uniform


# --- coefficient_of_variation (pop std / mean) -------------------------------

def test_coefficient_of_variation_known_value():
    """Verify coefficient of variation for a known numeric sequence.

    For [2, 4, 6, 8] the population mean is 5 and the population std is sqrt(5),
    so the coefficient of variation is approximately 0.4472.

    Returns:
        None.
    """
    # [2,4,6,8]: mean 5, pop std sqrt(5) ~= 2.23607 -> CV ~= 0.4472
    assert coefficient_of_variation(np.array([2.0, 4.0, 6.0, 8.0])) == 0.4472


def test_coefficient_of_variation_scale_invariant():
    """Verify coefficient of variation is scale invariant.

    Scaling every value by the same constant leaves the mean/std ratio
    unchanged, so the coefficient of variation is identical for [2,4,6,8] and
    its doubled counterpart.

    Returns:
        None.
    """
    assert coefficient_of_variation(np.array([2.0, 4.0, 6.0, 8.0])) == (
        coefficient_of_variation(np.array([4.0, 8.0, 12.0, 16.0]))
    )


def test_coefficient_of_variation_zero_mean_returns_none():
    """Verify zero mean yields None to avoid division by zero.

    When all values are zero the mean is zero, so the coefficient of variation
    is undefined and the function returns None rather than raising.

    Returns:
        None.
    """
    assert coefficient_of_variation(np.array([0.0, 0.0, 0.0])) is None


# --- gini_index ---------------------------------------------------------------

def test_gini_perfect_equality_is_zero():
    """Verify perfect equality gives a Gini index of zero.

    A perfectly equal distribution (all identical values) has the minimum Gini
    index of 0.0.

    Returns:
        None.
    """
    assert gini_index(np.array([1.0, 1.0, 1.0, 1.0])) == 0.0


def test_gini_known_linear_sequence():
    """Verify Gini index for the known linear sequence [1,2,3,4].

    The closed-form Gini coefficient for the ordered sequence [1, 2, 3, 4] is
    0.25, which the function should reproduce exactly.

    Returns:
        None.
    """
    # [1,2,3,4] -> closed form gives 0.25
    assert gini_index(np.array([1.0, 2.0, 3.0, 4.0])) == 0.25


def test_gini_increases_with_inequality():
    """Verify higher inequality yields a higher Gini index.

    Introducing a large outlier value increases the spread of the distribution,
    so the Gini index of [1,1,1,10] must exceed that of the uniform [1,1,1,1].

    Returns:
        None.
    """
    equal = gini_index(np.array([1.0, 1.0, 1.0, 1.0]))
    unequal = gini_index(np.array([1.0, 1.0, 1.0, 10.0]))
    assert unequal > equal


def test_gini_empty_returns_none():
    """Verify an empty array yields None instead of raising.

    With no values there is nothing to measure, so the Gini index returns None.

    Returns:
        None.
    """
    assert gini_index(np.array([])) is None


# --- hhi_index (1 / values, normalised, sum of squares) ----------------------

def test_hhi_uniform_four_way():
    """Verify HHI for four equal shares equals 0.25.

    With equal values each share is 1/4, so the Herfindahl index (sum of
    squared normalized shares) is 0.25.

    Returns:
        None.
    """
    # equal shares -> HHI = 1/4 = 0.25
    assert hhi_index(np.array([1.0, 1.0, 1.0, 1.0])) == 0.25


def test_hhi_known_two_value_case():
    """Verify HHI for the known two-value case [1.0, 3.0].

    The reciprocals are [1, 1/3], normalized to [0.75, 0.25]; the sum of squares
    of those shares is 0.625, which the function should return.

    Returns:
        None.
    """
    # 1/values = [1, 1/3]; normalised [0.75, 0.25]; sum of squares = 0.625
    assert hhi_index(np.array([1.0, 3.0])) == 0.625


def test_hhi_scale_invariant():
    """Verify HHI is invariant to scaling all values.

    Because the reciprocal shares are normalized before squaring, multiplying
    every input by a constant does not change the HHI.

    Returns:
        None.
    """
    assert hhi_index(np.array([1.0, 1.0, 1.0, 1.0])) == hhi_index(
        np.array([2.0, 2.0, 2.0, 2.0])
    )
