from settings import SITE, HEADERS, regions, tournaments, seasons, stages, matches, players, wait, matchheaders
from lxml import html
from html import unescape
import requests
import json
import re
from datetime import datetime


def get_all_tournaments():
    r = requests.get(SITE, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        return False

    all_regions = re.findall("allRegions = ([^;]+);", r.text)[0].replace("'", '"')
    all_regions = re.sub(r'(\w+):', r'"\1":', all_regions)

    for region in json.loads(all_regions):
        regions.update_one({'regionId': region['id']},
                           {'$setOnInsert': {
                               'name': region['name'],
                               'type': region['type']}},
                           upsert=True)
        tournament_list = region.pop('tournaments')

        for tournament in tournament_list:
            tournaments.update_one({'tournamentId': tournament['id']},
                                   {'$setOnInsert': {
                                       'name': tournament['name'],
                                       'regionId': region['id']}},
                                   upsert=True)


def get_seasons(tournament_id, overwrite=False):
    if seasons.find_one({'tournamentId': tournament_id}) and not overwrite:
        print('Seasons already exist')
        return True

    tournament = tournaments.find_one({'tournamentId': tournament_id})
    page = SITE+'/Regions/{regionId}/Tournaments/{tournamentId}'.format(**tournament)
    r = requests.get(page, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        return False

    content = html.fromstring(r.text)
    season_links = content.xpath('//select[@id="seasons"]/option/@value')
    season_names = content.xpath('//select[@id="seasons"]/option/text()')

    for season_link, season_name in zip(season_links, season_names):
        season = {
            'seasonId': int(season_link.split('/')[-1]),
            'name': season_name,
            'regionId': tournament['regionId'],
            'tournamentId': tournament['tournamentId'],
        }
        seasons.update_one({'seasonId': season['seasonId']},
                           {'$setOnInsert': {
                               'name': season['name'],
                               'regionId': tournament['regionId'],
                               'tournamentId': tournament['tournamentId']}},
                           upsert=True)

    # Sometimes the tournament doesn't have a name in the main menu - use the title on the page
    if tournament['name'] == '':
        tournament_name = content.xpath('//h1[@class="tournament-header"]/text()')[0].strip()
        tournaments.update_one({'tournamentId': tournament['tournamentId']}, {'$se': {'name': tournament_name}})

    # Some tournaments don't show up in the main menu - take a fuller list from the dropdown menu
    tournament_links = content.xpath('//select[@id="tournaments"]/option/@value')
    tournament_names = content.xpath('//select[@id="tournaments"]/option/text()')

    for tournament_link, tournament_name in zip(tournament_links, tournament_names):
        new_tournament = {
            'tournamentId': int(tournament_link.split('/')[-1]),
            'name': tournament_name,
            'regionId': tournament['regionId'],
        }
        tournaments.update_one({'tournamentId': new_tournament['tournamentId']},
                               {'$setOnInsert': {
                                   'name': new_tournament['name'],
                                   'regionId': new_tournament['regionId']}},
                               upsert=True)

    wait()


def get_stages(season_id, overwrite=False):
    if stages.find_one({'seasonId': season_id}) and not overwrite:
        print('Stages already exist')
        return True

    season = seasons.find_one({'seasonId': season_id})
    page = SITE+'/Regions/{regionId}/Tournaments/{tournamentId}/Seasons/{seasonId}'.format(**season)
    r = requests.get(page, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        return False

    content = html.fromstring(r.text)
    stage_links = content.xpath("//select[@id='stages']/option/@value")
    stage_names = content.xpath("//select[@id='stages']/option/text()")

    for stage_link, stage_name in zip(stage_links, stage_names):
        stages.update_one({'stageId': int(stage_link.split('/')[-1])},
                          {'$setOnInsert': {
                              'name': stage_name,
                              'regionId': season['regionId'],
                              'tournamentId': season['tournamentId'],
                              'seasonId': season['seasonId']}},
                          upsert=True)

    if len(stage_links) == 0:
        fixture_link = content.xpath("//div[@id='sub-navigation']/ul/li/a[text()='Fixtures']/@href")[0]
        stages.update_one({'stageId': int(fixture_link.split("/")[-3])},
                          {'$setOnInsert': {
                              'name': content.xpath('//h1/text()')[0].strip(),
                              'regionId': season['regionId'],
                              'tournamentId': season['tournamentId'],
                              'seasonId': season['seasonId']}},
                          upsert=True)

    wait()


def get_fixtures(stage_id, overwrite=False):
    if matchheaders.find_one({'stageId': stage_id}) and not overwrite:
        print('Matches already exist')
        return True

    stage = stages.find_one({'stageId': stage_id})
    page = SITE+'/Regions/{regionId}/Tournaments/{tournamentId}/Seasons/{seasonId}/Stages/{stageId}/Fixtures'.format(**stage)
    r = requests.get(page, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        wait()
        return False

    model_last_mode = re.findall("'Model-Last-Mode': '([^']+)'", r.text)[0]
    headers = HEADERS.copy()
    headers['Model-Last-Mode'] = model_last_mode
    headers['Referer'] = r.url
    headers['X-Requested-With'] = 'XMLHttpRequest'

    dates = re.findall("'Month', ([^ ]+), min, max", r.text)
    if dates:
        dates = re.sub(r'(\d+)(?=:)', r'"\1"', dates[0])
        d = json.loads(dates)

        if len(d) == 0:
            print('No matches')
            wait()
            return False

        months = {format(d): format(d+1, '02') for d in range(0, 12)}
        params = {'isAggregate': 'false'}

        for y in d:
            for m in d[y]:
                params['d'] = '{0}{1}'.format(y, months[m])
                wait()

                page = SITE+'/tournamentsfeed/{0}/Fixtures/'.format(stage_id)
                r = requests.get(page, params=params, headers=headers, allow_redirects=False)
                print(r.url, r.status_code)

                if r.status_code != 200:
                    wait()
                    return False

                matchData = re.sub(r',(?=,)', r',null', r.text)
                data = json.loads(matchData.replace("'", '"'))

                for row in data:
                    match = {'matchId': row[0], 'statusCode': row[1], 'startDate': row[2], 'startTime': row[3],
                             'home': {'teamId': row[4], 'name': row[5], 'field': 'home'},
                             'away': {'teamId': row[7], 'name': row[8], 'field': 'away'},
                             'score': row[10], 'elapsed': row[14], 'result': row[15], 'international': row[16],
                             'hasKeyEvents': row[12], 'hasPreview': row[13], 'isOpta': row[17], 'isOtherOpta': row[19],
                             }

                    if matchheaders.find_one({'matchId': match['matchId']}) and not overwrite:
                        print('Match already exists')
                    else:
                        match['startDate'] = datetime.strptime(match['startDate'], '%A, %b %d %Y')
                        match['startTime'] = datetime.strptime(match['startTime'], '%H:%M')
                        match['startTime'] = datetime.combine(match['startDate'].date(), match['startTime'].time())
                        for k, v in stage.items():
                            if 'Id' in k:
                                match[k] = v

                        matchheaders.replace_one({'matchId': match['matchId']}, match, upsert=True)
    else:
        matchData = re.findall("calendarParameter\), ([^;]*)\);", r.text)
        matchData = re.sub(r',(?=,)', r',null', matchData[0])
        data = json.loads(matchData.replace("'", '"') if matchData else '{}')

        for row in data:
            match = {'matchId': row[0], 'statusCode': row[1], 'startDate': row[2], 'startTime': row[3],
                     'home': {'teamId': row[4], 'name': row[5], 'field': 'home'},
                     'away': {'teamId': row[7], 'name': row[8], 'field': 'away'},
                     'score': row[10], 'elapsed': row[14], 'result': row[15], 'international': row[16],
                     'hasKeyEvents': row[12], 'hasPreview': row[13], 'isOpta': row[17], 'isOtherOpta': row[19],
                     }

            if matchheaders.find_one({'matchId': match['matchId']}) and not overwrite:
                print('Match already exists')
            else:
                match['startDate'] = datetime.strptime(match['startDate'], '%A, %b %d %Y')
                match['startTime'] = datetime.strptime(match['startTime'], '%H:%M')
                match['startTime'] = datetime.combine(match['startDate'].date(), match['startTime'].time())
                for k, v in stage.items():
                    if 'Id' in k:
                        match[k] = v

                matchheaders.replace_one({'matchId': match['matchId']}, match, upsert=True)
    wait()


def get_fixtures_for_date(d=None, overwrite=False):
    if d is None:
        params = {'d': datetime.strftime(datetime.utcnow(), '%Y%m%d')}
    elif type(d) is datetime:
        params = {'d': datetime.strftime(d, '%Y%m%d')}
    elif type(d) in [str, int]:
        params = {'d': d}
    else:
        print('Unknown date type')
        return False

    page = SITE+'/LiveScores/'
    r = requests.get(page, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        wait()
        return False

    model_last_mode = re.findall("'Model-Last-Mode': '([^']+)'", r.text)[0]
    headers = HEADERS.copy()
    headers['Model-Last-Mode'] = model_last_mode
    headers['Referer'] = r.url
    headers['X-Requested-With'] = 'XMLHttpRequest'
    print(model_last_mode)
    wait()

    page = SITE+'/matchesfeed/'
    r = requests.get(page, params=params, headers=HEADERS, allow_redirects=False)
    print(r.url, r.status_code)
    print(r.text)

    if r.status_code != 200:
        wait()
        return False

    matchData = re.sub(r'([,[])(?=[,\]])', r'\1null', r.text)
    data = json.loads(matchData.replace("'", '"'))
    print(data)

    stageData = data[1]
    matchData = data[2]


def get_match(match_id, overwrite=False):
    if matches.find_one({'matchId': match_id}) and not overwrite:
        print('Match already exists')
        return True

    page = SITE+'/Matches/{0}/Live'.format(match_id)
    r = requests.get(page, headers=HEADERS)

    print(r.url)
    content = unescape(r.text)

    if r.status_code != 200:
        wait()
        return False

    if r.url != page:
        match = {'matchId': match_id, 'error': 'No page found'}
        print(match['error'])
        matches.update_one({'matchId': match['matchId']}, {'$set': {'error': match['error']}}, upsert=True)
        wait()
        return False

    matchId = re.findall("matchId = ([^;]+);", content)
    matchData = re.findall("matchCentreData = ([^;]+});", content)

    if matchData and matchData != ['null']:
        match = json.loads(matchData[0], strict=False)
        match['matchId'] = int(matchId[0])

    else:
        matchData = re.findall("initialMatchDataForScrappers = (.+]);", content, re.DOTALL)

        if matchData:
            matchData = re.sub(r'([,[])(?=[,\]])', r'\1null', matchData[0].replace("'", '"'))
            matchData = json.loads(matchData, strict=False)

            matchHeader = matchData[0][0]
            matchEvents = matchData[0][1]
            matchLineup = matchData[0][2]
            timeInterval = matchData[1]

        else:
            matchData = re.findall("matchHeader.load\(([^;]+)\r\n\);", content)
            matchData = re.sub(r'([,[])(?=[,\]])', r'\1null', matchData[0].replace("'", '"'))

            matchHeader = json.loads(matchData, strict=False)
            matchEvents = []
            matchLineup = []

        fieldHeader = [['home', 'teamId'], ['away', 'teamId'], ['home', 'name'], ['away', 'name'],
                       'startTime', 'startDate', 'statusCode', 'elapsed',
                       'htScore', 'ftScore', 'etScore', 'pkScore', 'score'
                       ]

        match = {'matchId': match_id, 'home': {'field': 'home'}, 'away': {'field': 'away'}}

        for k, v in zip(fieldHeader, matchHeader):
            if v:
                if type(k) == list:
                    match[k[0]][k[1]] = v
                else:
                    match[k] = v

        parseLineup(matchLineup, match)
        if matchEvents[:1]:
            parseEvents(matchEvents, match)

    content = html.fromstring(r.text)
    link = content.xpath("//div[@id='breadcrumb-nav']/a/@href")

    if link:
        for key, val in re.findall(r'/(?P<key>\w+)/(?P<val>\d+)', link[0]):
            key = key[:-1].lower() + 'Id'
            match[key] = int(val)

    match['startDate'] = datetime.strptime(match['startDate'], '%m/%d/%Y %I:%M:%S %p')
    match['startTime'] = datetime.strptime(match['startTime'], '%m/%d/%Y %I:%M:%S %p')
    if 'timeStamp' in match:
        try:
            match['timeStamp'] = datetime.strptime(match['timeStamp'], '%d/%m/%Y %H:%M:%S')
        except ValueError:
            match['timeStamp'] = datetime.strptime(match['timeStamp'], '%Y-%m-%d %H:%M:%S')
    matches.replace_one({'matchId': match_id}, match, upsert=True)

    wait()
    return True


def parseLineup(matchLineup, match):
    if matchLineup[0:1] == 1:
        match.setdefault('playerIdNameDictionary', dict())

    if matchLineup[3:4] == 1:
        match['home'].setdefault('players', list())

    if matchLineup[4:5] == 1:
        for record in matchLineup[9]:
            player = {'name': record[0], 'playerId': record[3], 'field': 'home', 'isFirstEleven': True}
            match['playerIdNameDictionary'][str(player['playerId'])] = player['name']
            match['home']['players'].append(player)

    if matchLineup[5:6] == 1:
        for record in matchLineup[11]:
            player = {'name': record[0], 'playerId': record[3], 'field': 'home'}
            match['playerIdNameDictionary'][str(player['playerId'])] = player['name']
            match['home']['players'].append(player)

    if matchLineup[6:7] == 1:
        match['away'].setdefault('players', list())

    if matchLineup[7:8] == 1:
        for record in matchLineup[10]:
            player = {'name': record[0], 'playerId': record[3], 'field': 'away', 'isFirstEleven': True}
            match['playerIdNameDictionary'][str(player['playerId'])] = player['name']
            match['away']['players'].append(player)

    if matchLineup[8:9] == 1:
        for record in matchLineup[12]:
            player = {'name': record[0], 'playerId': record[3], 'field': 'away'}
            match['playerIdNameDictionary'][str(player['playerId'])] = player['name']
            match['away']['players'].append(player)


def parseEvents(matchEvents, match):
    match.setdefault('keyEvents', list())
    header = ['name', 'substituteName', 'eventType', 'score', 'detail', 'minute', 'playerId', 'substitutePlayerId']

    for field in matchEvents[0:1]:
        home_events = field[1]
        away_events = field[2]

        for record in home_events:
            print(record)
            event = {k: v for k, v in zip(header, record) if v not in ['', 0]}
            event['field'] = 'home'
            match['keyEvents'].append(event)

        for record in away_events:
            print(record)
            event = {k: v for k, v in zip(header, record) if v not in ['', 0]}
            event['field'] = 'away'
            match['keyEvents'].append(event)


def parseTeam(value):
    return int(value.split('/')[-3])


def parseDate(value):
    return datetime.strptime(value, '%d-%m-%Y')


def parseHeight(value):
    return int(value.replace('cm', ''))


def parseWeight(value):
    return int(value.replace('kg', ''))


def get_player(player_id, overwrite=False):
    keys = {
        'Name:': {'xpath': 'dd/text()', 'key': 'name', 'parse': str},
        'Full Name:': {'xpath': 'dd/text()', 'key': 'fullName', 'parse': str},
        'Current Team:': {'xpath': 'dd/a/@href', 'key': 'teamId', 'parse': parseTeam},
        'Shirt Number:': {'xpath': 'dd/text()', 'key': 'number', 'parse': int},
        'Positions:': {'xpath': 'dd/ul/li/text()', 'key': 'position', 'parse': str},
        'Age:': {'xpath': 'dd/i/text()', 'key': 'birthDate', 'parse': parseDate},
        'Height:': {'xpath': 'dd/text()', 'key': 'height', 'parse': parseHeight},
        'Weight:': {'xpath': 'dd/text()', 'key': 'weight', 'parse': parseWeight},
        'Nationality:': {'xpath': 'dd/span/text()', 'key': 'nationality', 'parse': str},
    }

    player = players.find_one({'playerId': player_id})
    if not player:
        player = {'playerId': player_id}
    elif not overwrite:
        print('Player already exists')
        return True

    page = SITE+'/Players/{0}'.format(player_id)
    r = requests.get(page, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        wait()
        return False

    if page != r.url:
        wait()
        return False

    content = html.fromstring(r.text)
    blocks = content.xpath("//div[@class='player-info']/div/div/dl")

    for block in blocks:
        title = block.xpath('dt/text()')[0]
        if title in keys:
            k = keys[title]
        else:
            print('Unexpected info: "{}"'.format(title))
            continue
        value = ', '.join([p.strip() for p in block.xpath(k['xpath']) if p.strip() != ''])
        player[k['key']] = k['parse'](value)

    players.save(player)
    wait()


def fix_dates():
    for match in matches.find({'startDate': {'$type': 2}}).sort('matchId', -1).batch_size(100):
        print(match['matchId'])
        match['startDate'] = datetime.strptime(match['startDate'], '%m/%d/%Y %H:%M:%S')
        match['startTime'] = datetime.strptime(match['startTime'], '%m/%d/%Y %H:%M:%S')
        if 'timeStamp' in match:
            try:
                match['timeStamp'] = datetime.strptime(match['timeStamp'], '%d/%m/%Y %H:%M:%S')
            except ValueError:
                match['timeStamp'] = datetime.strptime(match['timeStamp'], '%Y-%m-%d %H:%M:%S')
        matches.save(match)


def update_matches(status_code=1):
    # 0: Error
    # 1: Pending
    # 2: Postponed
    # 3: In-Play
    # 4: (Not seen)
    # 5: Abandoned
    # 6: Complete
    # 7: Cancelled
    # 8: (Who knows?)
    for match in matches.find({'statusCode': status_code,
                               'error': {'$exists': False},
                               'startDate': {'$lte': datetime.today()}
                               }).sort('startDate', -1):
        print(match['matchId'], match['statusCode'], match['startTime'])
        get_match(match['matchId'], overwrite=True)


if __name__ == "__main__":
    get_all_tournaments()
    get_seasons(2)
    get_stages(2)
    get_fixtures(2)
    get_match(20, overwrite=True)
    get_player(17, overwrite=True)

    fix_dates()
    update_matches()
