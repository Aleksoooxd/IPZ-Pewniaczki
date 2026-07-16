"""Normalise team names in the database from a JSON mapping."""

import sys
from pathlib import Path
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.flask_app.app.models.team import rename_team
from src.scraping.team_mapping import load_team_mapping


def rename(session: Session):
    """Apply the team-name mapping to the database.

    Loads the raw -> canonical team-name mapping and, for each pair, attempts the
    rename via :func:`rename_team`, printing OK or a diagnostic on failure.
    Errors from a single rename never abort the whole pass.

    Args:
        session (sqlalchemy.orm.Session): Active database session.

    Returns:
        None:
    """
    mappings = load_team_mapping()

    for old_name, new_name in mappings.items():
        try:
            success = rename_team(old_name, new_name)
            if success:
                print(f"OK: '{old_name}' -> '{new_name}'")
            else:
                print(
                    f"Błąd: nie znaleziono '{old_name}' "
                    f"albo '{new_name}' już istnieje.",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Błąd przy zmianie nazwy '{old_name}': {e}")