"""Load the team-name normalisation mapping from ``mapping.json``."""

import json
from pathlib import Path

_MAPPING_PATH = Path(__file__).resolve().parent / "mapping.json"


def load_team_mapping() -> dict:
    """Compose the raw->canonical team-name mapping.

    Reads ``mapping.json`` and folds its two-stage map (raw -> intermediate,
    intermediate -> canonical) into a single raw -> canonical dictionary. Any
    intermediate name without a canonical target is kept as-is.

    Args:
        None (reads the bundled ``mapping.json``)

    Returns:
        dict: Mapping from raw scraped team name to canonical name.
    """
    with open(_MAPPING_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_to_inter = data.get("raw_to_intermediate", {})
    inter_to_canon = data.get("intermediate_to_canonical", {})

    composed: dict = {}
    for raw, intermediate in raw_to_inter.items():
        composed[raw] = inter_to_canon.get(intermediate, intermediate)
    for intermediate, canonical in inter_to_canon.items():
        composed.setdefault(intermediate, canonical)

    return composed
