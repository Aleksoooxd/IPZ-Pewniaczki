from datetime import datetime
import asyncio
import json
import httpx
import pandas as pd
import os
import requests
import time
def team_modifier(teamh,teama,separator,use_date=False,date="20/09/2005"):
    if use_date:
        date = date[:4]
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
        #print(f"Błąd zapytania: {response.status_code}")
        return None
    data = response.json()
    for i,entity in enumerate(data['results']):
        entity = entity['entity']
        ht = entity['homeTeam']['name']
        at = entity['awayTeam']['name']
        date = datetime.fromtimestamp(entity['startTimestamp']).strftime("%Y-%m-%d")
        if date.replace(" ", "") != match_date.replace(" ", ""):
            continue
        #customid = entity['customId']
        id = entity['id']
        #teams_link = team_modifier(ht,at,"-")
        #match_link = f"https://www.sofascore.com/football/match/{teams_link}/{customid}#id:{id}"
        #print(match_link)
        lineups_link = f"https://www.sofascore.com/api/v1/event/{id}/lineups"
        #print(lineups_link)
        #statistics_link = f"https://www.sofascore.com/api/v1/event/{id}/statistics"
        #print(statistics_link)
        #managers_link = f"https://www.sofascore.com/api/v1//event/{id}/managers"
        return lineups_link
async def extract_lineups(base_url):
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url)
    if response.status_code != 200:
        #print(f"Błąd zapytania: {response.status_code}")
        return None,None
    data = response.json()
    homeplayers = data["home"]["players"]
    awayplayers = data["away"]["players"]
    homep = []
    awayp =[]
    for player in homeplayers:
        homep.append(player["player"]["name"])
    for player in awayplayers:
        awayp.append(player["player"]["name"])
    homep = homep[:11]
    awayp = awayp[:11]
    return homep,awayp
async def main():
    hometeam = 'Manchester United'
    ht_logo = await get_team_logo(hometeam)
    print(ht_logo)


async def get_team_logo(team_name):
    api_key = "123"
    formatted_team_name = team_name.replace(" ", "%20")
    url = f"https://www.thesportsdb.com/api/v1/json/{api_key}/searchteams.php?t={formatted_team_name}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != 200:
        return None

    data = response.json()
    if data and data.get('teams'):
        team_info = data['teams'][0]
        return team_info['strBadge']
    return None
if __name__ == "__main__":
    asyncio.run(main())