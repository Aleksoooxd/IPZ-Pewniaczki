from datetime import datetime
import asyncio
import json
import httpx
import time
def team_modifier(teamh,teama,separator):
    link = teamh+" "+teama
    link = link.replace(" ", separator)
    return link

async def find_match_link(home_team, away_team, match_date):
    teams_in_match = team_modifier(home_team, away_team, "%20")
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
        if date != match_date or ht != home_team or at != away_team:
            continue
        customid = entity['customId']
        id = entity['id']
        teams_link = team_modifier(ht,at,"-")
        match_link = f"www.sofascore.com/football/match/{teams_link}/{customid}#id:{id}"
        print(match_link)

async def main():# Przykład użycia
    home_team = "VfL Wolfsburg"
    away_team = "VfB Stuttgart"
    match_date = "18/12/2018"
    await find_match_link(home_team, away_team, match_date)
asyncio.run(main())