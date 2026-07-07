from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.flask_app.app.db import rename_team


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Jednorazowa korekta dokładnej nazwy drużyny w bazie danych."
    )
    parser.add_argument("old_name", help="Aktualna dokładna nazwa drużyny")
    parser.add_argument("new_name", help="Nowa dokładna nazwa drużyny")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    success = rename_team(args.old_name, args.new_name)

    if success:
        print(f"OK: '{args.old_name}' -> '{args.new_name}'")
        return 0

    print(
        "Błąd: nie znaleziono drużyny o podanej nazwie albo nowa nazwa jest już zajęta.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

