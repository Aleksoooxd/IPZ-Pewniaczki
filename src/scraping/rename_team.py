from __future__ import annotations
import sys
import json
from pathlib import Path
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.flask_app.app.models.team import rename_team


def rename(session: Session):
    mappings_path = Path(__file__).resolve().parent / "mapping.json"
    with open(mappings_path, "r", encoding="utf-8") as f:
        mappings = json.load(f)

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