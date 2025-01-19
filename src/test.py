from datetime import datetime
import asyncio
import json
import httpx
import requests
import time
def team_modifier(teamh,teama,separator,use_date=False,date="20/09/2005"):
    if use_date:
        date = date[-4:]
    else:
        date=""
    link = teamh+" "+teama+" "+date
    link = link.replace(" ", separator)
    return link

async def find_match_link(home_team, away_team, match_date):
    teams_in_match = team_modifier(home_team, away_team, "%20",use_date=True,date=match_date)
    base_url = f"https://www.sofascore.com/api/v1/search/events?q={teams_in_match}&page=0"
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url)
    if response.status_code != 200:
        print(f"Błąd zapytania: {response.status_code}")
        return None
    data = response.json()
    print(home_team,away_team,match_date)
    for i,entity in enumerate(data['results']):
        entity = entity['entity']
        ht = entity['homeTeam']['name']
        at = entity['awayTeam']['name']
        date = datetime.fromtimestamp(entity['startTimestamp']).strftime("%d/%m/%Y")
        if date.replace(" ", "") != match_date.replace(" ", ""):
            continue
        customid = entity['customId']
        id = entity['id']
        teams_link = team_modifier(ht,at,"-")
        match_link = f"https://www.sofascore.com/football/match/{teams_link}/{customid}#id:{id}"
        lineups_link = f"https://www.sofascore.com/api/v1//event/{id}/lineups"
        print(lineups_link)
        statistics_link = f"https://www.sofascore.com/api/v1//event/{id}/statistics"
        print(statistics_link)
        managers_link = f"https://www.sofascore.com/api/v1//event/{id}/managers"
        return match_link

async def main():# Przykład użycia
    home_team = "Academica"
    away_team = "Maritimo"
    match_date = "03/10/2015"
    match_link = await find_match_link(home_team, away_team, match_date)
    print(match_link)
asyncio.run(main())