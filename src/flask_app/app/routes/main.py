import datetime
from flask import Blueprint, render_template, request, redirect, url_for

main_bp = Blueprint("main", __name__)

LEAGUE_NAMES = {
    "Premierleague":        "Premier League",
    "Bundesliga":           "Bundesliga",
    "Eredivisie":           "Eredivisie",
    "EthnikiKatigoria":     "Ethniki Katigoria",
    "FutbolLig1":           "1. Lig",
    "JupiterLeague":        "Jupiler League",
    "LaLiga":               "La Liga",
    "Ligue1":               "Ligue 1",
    "LigaI":                "Liga I",
    "ScotishPremierLeague": "Premiership",
    "SerieA":               "Serie A",
}


@main_bp.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        pass
    return render_template("index.html")


@main_bp.route("/main")
def mainpage():
    date_param = request.args.get("date")
    if not date_param:
        today = datetime.date.today().strftime("%Y-%m-%d")
        return redirect(url_for("main.mainpage", date=today))
    return render_template("MainPage.html", league_names=LEAGUE_NAMES)