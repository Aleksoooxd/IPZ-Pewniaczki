# IPZ-Pewniaczki
## About the Project

IPZ-Pewniaczki is an academic project focused on developing a system for predicting football match results. It encompasses several key components:
1.  **Data Scraping**: Gathering historical match data, team market values, and future fixture information from various online sources.
2.  **Data Processing and Feature Engineering**: Calculating advanced statistical metrics, ELO ratings, and team form/head-to-head (H2H) statistics.
3.  **Prediction Model**: Training a machine learning model (XGBoost and Neural Network) to predict match outcomes (Home Win, Draw, Away Win).
4.  **Web Application (Flask)**: Providing an interactive interface for users to browse match details, league standings, and view predictions.

## Features

* **Daily Match Updates**: Automatically refreshes data for top European leagues every 12 hours.
* **Comprehensive Match Details**: View historical and upcoming matches with detailed information, including:
    * Match date and time.
    * Home and Away teams.
    * League and Matchday.
    * Final score (for past matches).
    * Team ELO ratings and changes.
    * Team market values.
    * Team form (last 3, last 5, and season).
    * Goals scored in recent matches and season.
    * Team placements in league tables.
    * Head-to-Head (H2H) statistics.
    * Bookmaker odds statistics (mean, standard deviation, Shannon entropy, Gini index, HHI, Coefficient of Variation).
    * Consensus prediction from bookmakers.
    * "Surprise" indicator based on odds.
* **Match Predictions**: Displays predicted results for matches with a confidence score.
* **Interactive League Tables**: Browse league standings for various seasons, including an "All-Time" view, and filter by matchday.
* **Team Profiles**: Access basic information for individual teams within specific leagues and seasons. (Further details are marked as "soon..." in the application).
* **Multi-language Support**: The web application supports several languages (English, German, Spanish, Portuguese, Czech, Danish, Polish, Japanese, Swedish, Italian, Turkish, Croatian, Hebrew).
* **Theme Toggle**: Switch between light and dark modes for better user experience.

## Data Sources

The project scrapes data from the following sources:

* **Football-Data.co.uk**: Provides historical match data, including results and a wide range of bookmaker odds.
* **TheSportsDB.com**: Used for fetching team logos (though a custom scraper `test_logoScraper.py` using `duckduckgo_search` is also present, suggesting an alternative approach for logo retrieval).
* **SofaScore.com**: Explored for match links, lineups, and statistics, though its primary integration for core data scraping might be limited or in development.

## Technical Stack

* **Backend**: Python 3.9
* **Web Framework**: Flask
* **Database**: Local SQLite database (via SQLAlchemy)
* **ORM**: SQLAlchemy
* **Data Manipulation**: Pandas, NumPy
* **Web Scraping**: BeautifulSoup4, Requests, httpx, fuzzywuzzy, chardet, unidecode
* **Machine Learning**: XGBoost, PyTorch (Neural Network)
* **Deployment/Automation**: GitHub Actions (for scheduled data refreshes)
* **Frontend**: HTML, CSS (custom, with Inter font), JavaScript

