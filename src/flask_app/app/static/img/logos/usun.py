import os
import sys
import argparse

FRAGMENT = ".football-logos.cc"


def clean_filenames(folder: str, dry_run: bool = False, non_collection: bool = False) -> None:
    if not os.path.isdir(folder):
        print(f"Blad: '{folder}' nie jest istniejacym folderem.")
        sys.exit(1)
    usunite = 0
    zmienione = 0
    for nazwa in os.listdir(folder):
        pelna_sciezka = os.path.join(folder, nazwa)

        if not os.path.isfile(pelna_sciezka):
            continue
        
        if FRAGMENT in nazwa and not non_collection:
            nowa_nazwa = nazwa.replace(FRAGMENT, "").strip()
            # usuniecie ewentualnych podwojnych podkreslen/myslnikow/spacji
            # powstalych po wycieciu fragmentu
            for znak in ["--", "__", "  "]:
                while znak in nowa_nazwa:
                    nowa_nazwa = nowa_nazwa.replace(znak, znak[0])
            nowa_nazwa = nowa_nazwa.strip("-_ .")

            if not nowa_nazwa:
                print(f"Pominieto (nazwa bylaby pusta): {nazwa}")
                continue

            nowa_pelna_sciezka = os.path.join(folder, nowa_nazwa)

            if os.path.exists(nowa_pelna_sciezka):
                print(f"Pominieto (plik docelowy juz istnieje): {nazwa} -> {nowa_nazwa}")
                continue

            if dry_run:
                print(f"[DRY-RUN] {nazwa}  ->  {nowa_nazwa}")
            else:
                os.rename(pelna_sciezka, nowa_pelna_sciezka)
                print(f"Zmieniono: {nazwa}  ->  {nowa_nazwa}")

            zmienione += 1
        if non_collection:
            try:
                nazwa_split = nazwa.split("_")
                nowa_nazwa = nazwa_split[1] + ".png"
            except IndexError:
                continue
            if not nowa_nazwa:
                print(f"Pominieto (nazwa bylaby pusta): {nazwa}")
                continue

            nowa_pelna_sciezka = os.path.join(folder, nowa_nazwa)

            if os.path.exists(nowa_pelna_sciezka):
                os.remove(pelna_sciezka)
                print(f"Usunięto (plik docelowy juz istnieje): {nazwa} -> {nowa_nazwa}")
                usunite += 1
                continue

            if dry_run:
                print(f"[DRY-RUN] {nazwa}  ->  {nowa_nazwa}")
            else:
                os.rename(pelna_sciezka, nowa_pelna_sciezka)
                print(f"Zmieniono: {nazwa}  ->  {nowa_nazwa}")

            zmienione += 1
    print(f"\nGotowe. Zmienionych plikow: {zmienione}")
    print(f"Usuniętych plikow: {usunite}")


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Usuwa 'football-logos.cc' z nazw plikow w folderze.")
    # parser.add_argument("folder", help="Sciezka do folderu z plikami")
    # parser.add_argument("--non-collection", action="store_true", help="Wypadek usuwania w przypadku osobnych logotypow (bez kolekcji). Wtedy usuwany jest fragment przed pierwszym podkresleniem.")
    # parser.add_argument("--dry-run", action="store_true", help="Tylko wyswietl zmiany bez ich wykonywania")
    #
    # args = parser.parse_args()
    folders = ["64x64", "128x128", "256x256", "512x512"]
    for folder in folders:
        clean_filenames(folder, dry_run=False, non_collection=True)
