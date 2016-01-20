from settings import regions, tournaments, seasons, stages, teams, players, events
from whoscored import get_player
import csv

FIELDNAMES = ['id', 'isGoal', 'x', 'y', 'Region', 'Tournament', 'Season', 'Stage', 'Team', 'Player']

QUALIFIERS = [
    # 'Zone',
    'Offensive',
    'BigChance',
    'BigChanceCreated',
    'KeyPass',
    'IntentionalGoalAssist',
    'IntentionalAssist',
    'Assisted',
    'RightFoot',
    'LeftFoot',
    'Head',
    'OtherBodyPart',
    'RegularPlay',
    'FastBreak',
    'SetPiece',
    'FromCorner',
    'Penalty',
    'DirectFreekick',
    'ThrowinSetPiece',
    # 'SmallBoxRight',
    # 'SmallBoxCentre',
    # 'SmallBoxLeft',
    # 'BoxLeft',
    # 'BoxCentre',
    # 'BoxRight',
    # 'DeepBoxRight',
    # 'DeepBoxLeft',
    # 'OutOfBoxLeft',
    # 'OutOfBoxCentre',
    # 'OutOfBoxRight',
    # 'OutOfBoxDeepLeft',
    # 'OutOfBoxDeepRight',
    # 'ThirtyFivePlusRight',
    # 'ThirtyFivePlusCentre',
    # 'ThirtyFivePlusLeft',
    # 'MissHigh',
    # 'MissLeft',
    # 'MissRight',
    # 'HighLeft',
    # 'HighCentre',
    # 'HighRight',
    # 'LowLeft',
    # 'LowCentre',
    # 'LowRight',
    # 'GoalMouthY',
    # 'GoalMouthZ',
    # 'Blocked',
    # 'BlockedX',
    # 'BlockedY',
    # 'SixYardBlock',
    # 'SavedOffline',
    # 'RelatedEventId',
    # 'OppositeRelatedEvent',
]


def extract_data(filename='shots.csv'):
    r, c, s, g, t, p = dict(),  dict(),  dict(),  dict(),  dict(),  dict()
    for region in regions.find():
        player_id = region['regionId']
        r[player_id] = region['name']
    for tournament in tournaments.find():
        player_id = tournament['tournamentId']
        c[player_id] = tournament['name']
    for season in seasons.find():
        player_id = season['seasonId']
        s[player_id] = season['name']
    for stage in stages.find():
        player_id = stage['stageId']
        g[player_id] = stage['name']
    for team in teams.find():
        player_id = team['teamId']
        t[player_id] = team['name']
    for player in players.find():
        player_id = player['playerId']
        p[player_id] = player['name']

    f = open(filename, 'w', newline='\n')
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES + QUALIFIERS, extrasaction='ignore')
    writer.writeheader()

    # goals = events.count({'isGoal': True, 'isOwnGoal': {'$exists': False}})
    # shots = events.count({'isShot': True, 'isOwnGoal': {'$exists': False}})
    # print('{0:,} goals from {1:,} shots ({2:.1%} shot rate)'.format(goals, shots, goals / shots))

    for event in events.find({'isShot': True, 'isOwnGoal': {'$exists': False}}).sort('matchId', -1):
        event['isGoal'] = 1 if event.get('isGoal') else 0
        event['Region'] = r[event['regionId']] if event.get('regionId') else None
        event['Tournament'] = c[event['tournamentId']] if event.get('tournamentId') else None
        event['Season'] = s[event['seasonId']] if event.get('seasonId') else None
        event['Stage'] = g[event['stageId']] if event.get('stageId') else None
        event['Team'] = t[event['teamId']] if event.get('teamId') else None
        try:
            event['Player'] = p[event['playerId']] if event.get('playerId') else None
        except KeyError:
            player_id = event['playerId']
            print('Missing playerId: {}'.format(player_id))
            get_player(player_id)
            event['Player'] = None
        event_qualifiers = {q['type']['displayName']: q.get('value', 1) for q in event['qualifiers']}
        for qualifier in QUALIFIERS:
            event[qualifier] = event_qualifiers.get(qualifier, 0)

        writer.writerow(event)

if __name__ == "__main__":
    extract_data()
