from unidecode import unidecode
import numpy as np
from scipy.stats import entropy
import datetime
def shannon_index(values):
    """Compute the Shannon entropy (diversity) index of a set of values.

    The values are normalised to a probability distribution and the base-2
    Shannon entropy is returned as a measure of how evenly distributed they are.

    Args:
        values (array-like): Non-negative counts or magnitudes; their sum must
            be non-zero.

    Returns:
        float: Shannon entropy rounded to 4 decimals (bits). Higher values
        indicate a more even distribution.
    """
    probabilities = values / np.sum(values)
    return np.round(entropy(probabilities, base=2),4)
def coefficient_of_variation(values):
    """Compute the coefficient of variation of a set of values.

    Ratio of the standard deviation to the mean, used as a scale-independent
    dispersion measure. Returns ``None`` when the mean is zero (undefined).

    Args:
        values (array-like): Numeric values to summarise.

    Returns:
        float or None: Standard deviation divided by the mean, rounded to 4
        decimals; ``None`` if the mean is 0.
    """
    mean = np.mean(values)
    return np.round((np.std(values) / mean),4) if mean != 0 else None
def gini_index(values):
    """Compute the Gini coefficient of a set of values.

    Measures inequality among the values (0 = perfectly equal, 1 = maximal
    inequality). Returns ``None`` when there are no values.

    Args:
        values (array-like): Non-negative numeric values.

    Returns:
        float or None: Gini coefficient rounded to4 decimals; ``None`` if the
        input is empty.
    """
    sorted_values = np.sort(values)
    n = len(values)
    cumulative = np.cumsum(sorted_values)
    return np.round((1 - (2 * np.sum(cumulative) / (n * cumulative[-1])) + (1 / n)),4) if n > 0 else None
def hhi_index(values):
    """Compute the Herfindahl-Hirschman (HHI) concentration index.

    Smaller input values are treated as more "dominant" by weighting each with
    the inverse of its magnitude, normalising those weights to a probability
    distribution, and summing their squared probabilities. Higher values mean
    more concentration on a few small inputs.

    Args:
        values (array-like): Positive numeric values (used as inverse weights).

    Returns:
        float: Sum of squared normalised inverse weights, rounded to4 decimals.
    """
    probabilities = 1 / values
    probabilities /= np.sum(probabilities)
    return np.round(np.sum(probabilities ** 2),4)
def calculate_consensus(row, columns):
    """Determine the model consensus outcome for a single match row.

    Treats each predictor column as a "cost" it assigned to each of the three
    outcomes (Home / Draw / Away). A column "votes" for an outcome when that
    outcome's cost is strictly lower than the other two. The outcome with the
    most votes wins; a tie yields ``'No Consensus'``.

    Args:
        row (pandas.Series): A single match's row, indexed by the predictor
            column names.
        columns (dict): Mapping ``{'H': [...], 'D': [...], 'A': [...]}`` where
            each value is the list of column names whose value is the cost that
            predictor assigned to that outcome. ``columns['H'][0]`` is treated as
            the canonical Home-cost column, etc.

    Returns:
        str: ``'H'``, ``'D'``, ``'A'``, or ``'No Consensus'``.
    """
    votes_H = sum([1 for col in columns["H"] if row[col] < row[columns["D"][0]] and row[col] < row[columns["A"][0]]])
    votes_D = sum([1 for col in columns["D"] if row[col] < row[columns["H"][0]] and row[col] < row[columns["A"][0]]])
    votes_A = sum([1 for col in columns["A"] if row[col] < row[columns["H"][0]] and row[col] < row[columns["D"][0]]])
    if votes_H > max(votes_D, votes_A):
        return 'H'
    elif votes_D > max(votes_H, votes_A):
        return 'D'
    elif votes_A > max(votes_H, votes_D):
        return 'A'
    else:
        return 'No Consensus'

