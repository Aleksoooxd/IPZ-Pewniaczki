from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.flask_app.app.db import rename_team

def rename():
    import json
    mappings_path = Path(__file__).resolve().parent / "mapping.json"
    with open(mappings_path, "r", encoding="utf-8") as f:
        mappings = json.load(f)
    for old_name, new_name in mappings.items():
        try:
            success = rename_team(old_name, new_name)
            if success:
                print(f"OK: '{old_name}' -> '{new_name}'")
            else:
                print(f"Błąd: nie znaleziono drużyny o nazwie '{old_name}' albo nowa nazwa '{new_name}' jest już zajęta.", file=sys.stderr)
        except Exception as e:
            print(f"Błąd: wystąpił błąd podczas próby zmiany nazwy drużyny '{old_name}': {e}")
    return 1

if __name__ == "__main__":
    rename()

