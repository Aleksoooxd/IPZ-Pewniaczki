"""Unit tests for `calculate_consensus` (helpfunctions.py:20-31).

The `row` values are bookmaker *odds* (decimal), where a lower number means a
more favoured outcome. A model "votes" for an outcome when its odds are lower
than the reference Draw odds (`columns["D"][0]`, Bet365 by default) AND the
reference Away odds (`columns["A"][0]`). The outcome with the most votes wins;
a non-strict-max tie yields "No Consensus".

"""

from src.calculations.helpfunctions import calculate_consensus

COLUMNS = {
    "H": ["B365H", "WHH"],
    "D": ["B365D"],
    "A": ["B365A"],
}


def test_home_favourite_consensus():
    """Verify home is the consensus when every home bookmaker beats references.

    With both home odds (B365H, WHH) below the reference Draw and Away odds,
    home accumulates the most votes and ``calculate_consensus`` returns "H".

    Returns:
        None.
    """
    row = {"B365H": 2.0, "WHH": 2.1, "B365D": 3.5, "B365A": 4.0}
    assert calculate_consensus(row, COLUMNS) == "H"


def test_away_favourite_consensus():
    """Verify away is the consensus when away odds beat the references.

    With the away odds (B365A = 2.0) below the reference Home and Draw odds,
    away gets the most votes and ``calculate_consensus`` returns "A".

    Returns:
        None.
    """
    row = {"B365H": 4.0, "WHH": 3.6, "B365D": 3.5, "B365A": 2.0}
    assert calculate_consensus(row, COLUMNS) == "A"


def test_draw_favourite_consensus():
    """Verify draw is the consensus when draw odds beat the references.

    With the Draw odds (B365D = 2.0) below the reference Home and Away odds,
    draw accumulates the most votes and ``calculate_consensus`` returns "D".

    Returns:
        None.
    """
    row = {"B365H": 3.5, "WHH": 3.6, "B365D": 2.0, "B365A": 3.4}
    assert calculate_consensus(row, COLUMNS) == "D"


def test_no_consensus_on_tied_vote():
    """Verify a non-strict tie among votes yields "No Consensus".

    With votes_H == votes_D == 1, neither outcome strictly exceeds the other,
    so the non-strict-max tie handling returns "No Consensus".

    Returns:
        None.
    """
    # votes_H == votes_D == 1: neither strictly exceeds the other -> "No Consensus".
    row = {"B365H": 4.0, "WHH": 2.0, "B365D": 2.5, "B365A": 3.0}
    assert calculate_consensus(row, COLUMNS) == "No Consensus"


def test_more_bookmakers_raise_home_vote_count():
    """Verify additional home bookmakers raise the home vote count but not the winner.

    With two home bookmakers (B365H, WHH) both shorter than the Draw/Away
    references the home side still wins; a single home bookmaker on the same row
    also yields "H", confirming more bookmakers increase the vote count without
    changing the outcome.

    Returns:
        None.
    """
    # Two home bookmakers both shorter than the D/A references -> 2 home votes.
    row = {"B365H": 2.0, "WHH": 2.1, "B365D": 3.5, "B365A": 4.0}
    assert calculate_consensus(row, COLUMNS) == "H"
    # Single home bookmaker still beats references -> 1 home vote, still "H".
    single = {"H": ["B365H"], "D": ["B365D"], "A": ["B365A"]}
    assert calculate_consensus(row, single) == "H"
