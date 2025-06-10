import pandas as pd
import requests
import os
import time
from duckduckgo_search import DDGS

# Ścieżka zapisu
base_dir = os.path.dirname(os.path.abspath(__file__))
save_dir = os.path.join(base_dir, "flask_app", "app", "static", "logos")
os.makedirs(save_dir, exist_ok=True)

# Wczytaj CSV — zakładam, że nie ma nagłówka
df = pd.read_csv("teams_from_pewniaczki.csv", sep=";", header=None, names=["team_id", "name"])

# Użycie DDGS
with DDGS(timeout=30) as ddgs:
    for _, row in df.iterrows():
        team_name = row["name"]
        team_id = row["team_id"]
        print(f"Pobieram logo dla: {team_name}")
        query = f"{team_name} transparent background football club logo 2024"

        try:
            results = ddgs.images(
                keywords=query,
                region="wt-wt",
                safesearch="moderate",
                max_results=5,
                size="Large",
                type_image="transparent"  # << kluczowe!
            )

            result = results[0] if results else None  # ← TO NAPRAWIA BŁĄD

            if result:
                image_url = result["image"]
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    file_path = os.path.join(save_dir, f"{team_id}.png")
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    print(f"Zapisano: {file_path}")
                else:
                    print(f"Nie udało się pobrać obrazu (kod {response.status_code})")
            else:
                print(f"Nie znaleziono logo dla {team_name}")

        except Exception as e:
            print(f"Błąd dla {team_name}: {e}")
