from settings import matches, events, players, teams

for match in matches.find({'events': {'$exists': True}}).sort('matchId'):
    print(match['matchId'], '{0} events'.format(len(match['events'])))

    count = events.count({'matchId': match['matchId']})
    if count and len(match['events']) == count:
        print('Events already written')
    else:
        events.remove({'matchId': match['matchId']})
        for event in match['events']:
            for k in ['matchId', 'stageId', 'seasonId', 'tournamentId', 'regionId']:
                if k in match:
                    event[k] = match[k]
            events.insert_one(event)

    for k, v in match['playerIdNameDictionary'].items():
        players.update_one({'playerId': int(k)}, {'$set': {'playerName': v}}, upsert=True)

    teams.update_one({'teamId': match['home']['teamId']}, {'$set': {'teamName': match['home']['name']}}, upsert=True)
    teams.update_one({'teamId': match['away']['teamId']}, {'$set': {'teamName': match['away']['name']}}, upsert=True)
