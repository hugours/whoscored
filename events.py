from settings import matches, events, players, teams, matchheaders
from datetime import datetime


def load_events():
    print(datetime.now(), 'Starting')
    for match in matches.find({'events': {'$exists': True}}).sort('matchId', -1):

        count = events.count({'matchId': match['matchId']})
        if count and len(match['events']) == count:
            # print('Events already written')
            continue
        else:
            print(datetime.now(), match['matchId'], '{0} events'.format(len(match['events'])))
            events.remove({'matchId': match['matchId']})
            for event in match['events']:
                for k in ['matchId', 'stageId', 'seasonId', 'tournamentId', 'regionId']:
                    if k in match:
                        event[k] = match[k]
                events.insert_one(event)
    print(datetime.now(), 'Complete')


def load_players():
    for match in matches.find({'playerIdNameDictionary': {'$exists': True}}).sort('matchId', 1):
        print(match['matchId'])
        for k, v in match['playerIdNameDictionary'].items():
            players.update_one({'playerId': int(k)}, {'$setOnInsert': {'name': v}}, upsert=True)


def load_teams():
    for match in matchheaders.find().sort('matchId'):
        print(match['matchId'])
        teams.update_one({'teamId': match['home']['teamId']}, {'$setOnInsert': {'name': match['home']['name']}}, upsert=True)
        teams.update_one({'teamId': match['away']['teamId']}, {'$setOnInsert': {'name': match['away']['name']}}, upsert=True)

if __name__ == "__main__":
    load_events()
    load_players()
    load_teams()
