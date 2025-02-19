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
async def main():# Przykład użycia
    filepath = os.path.join("..",'Data', 'FinalData', 'AllBookmakers','AllLeagues.csv')
    df = pd.read_csv(filepath)
    lineup_columns = [f"H{i}" for i in range(1, 12)] + [f"A{i}" for i in range(1, 12)]
    for col in lineup_columns:
        df[col] = None
    for index, row in df.iterrows():
        if index > 4000:
            home_team = row['HomeTeam']
            away_team = row['AwayTeam']
            match_date = str(row['Date'])
            lineups_link = await find_match_link(home_team, away_team, match_date)

            if lineups_link is None:
                print(f"Match {index}, " f"HT: {home_team}", " ", f"AT: {away_team}", "failed - no match link")
                continue
            home_lineup, away_lineup = await extract_lineups(lineups_link)
            if home_lineup is None or away_lineup is None:
                print(f"Match {index}, " f"HT: {home_team}", " ", f"AT: {away_team}", "failed - no lineups link")
                continue
            lineups = home_lineup + away_lineup
            for ind,col in enumerate(lineup_columns):
                df.at[index, col] = lineups[ind]
            #df.at[index, lineup_columns[:11]] = home_lineup
            #df.at[index, lineup_columns[11:]] = away_lineup
            print(f"Match {index}, " f"HT: {home_team}", " ", f"AT: {away_team}", "processed")
    df.to_csv(filepath,index=False)
asyncio.run(main())