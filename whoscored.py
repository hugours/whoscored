from settings import SITE, HEADERS, regions, tournaments, seasons, stages, matches, wait
from lxml import html
import requests
import json
import re


def get_all_tournaments():
    r = requests.get(SITE, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        return False

    all_regions = re.findall("allRegions = ([^;]+);", r.text)[0].replace("'", '"')
    all_regions = re.sub(r'(\w+):', r'"\1":', all_regions)

    for region in json.loads(all_regions):
        region['regionId'] = region.pop('id')
        tournament_list = region.pop('tournaments')
        region.pop('flg')
        regions.replace_one({'regionId': region['regionId']}, region, upsert=True)

        for tournament in tournament_list:
            tournament['tournamentId'] = tournament.pop('id')
            tournament['regionId'] = region['regionId']
            tournament.pop('url')
            tournaments.replace_one({'tournamentId': tournament['tournamentId']}, tournament, upsert=True)


def get_seasons(select=None, overwrite=False):
    for tournament in tournaments.find(select if select else {}):

        if seasons.find_one({'tournamentId': tournament['tournamentId']}) and not overwrite:
            print('Season already written')
            continue

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
            seasons.replace_one({'seasonId': season['seasonId']}, season, upsert=True)

        if tournament['name'] == '':
            tournament['name'] = content.xpath('//h1[@class="tournament-header"]/text()')[0].strip()
            tournaments.save(tournament)

        wait()


def get_stages(select=None, overwrite=False):
    for season in seasons.find(select if select else {}).sort('seasonId'):

        if stages.find_one({'seasonId': season['seasonId']}) and not overwrite:
            print('Stage already written')
            continue

        page = SITE+'/Regions/{regionId}/Tournaments/{tournamentId}/Seasons/{seasonId}'.format(**season)
        r = requests.get(page, headers=HEADERS)
        print(r.url)

        if r.status_code != 200:
            return False

        content = html.fromstring(r.text)
        stage_links = content.xpath("//select[@id='stages']/option/@value")
        stage_names = content.xpath("//select[@id='stages']/option/text()")

        for stage_link, stage_name in zip(stage_links, stage_names):
            stage = {
                'stageId': int(stage_link.split('/')[-1]),
                'name': stage_name,
                'regionId': season['regionId'],
                'tournamentId': season['tournamentId'],
                'seasonId': season['seasonId'],
            }
            stages.replace_one({'stageId': stage['stageId']}, stage, upsert=True)

        if len(stage_links) == 0:
            fixture_link = content.xpath("//div[@id='sub-navigation']/ul/li/a[text()='Fixtures']/@href")[0]
            stage = {
                'stageId': int(fixture_link.split("/")[-3]),
                'name': content.xpath('//h1/text()')[0].strip(),
                'regionId': season['regionId'],
                'tournamentId': season['tournamentId'],
                'seasonId': season['seasonId'],
            }
            stages.replace_one({'stageId': stage['stageId']}, stage, upsert=True)

        wait()


def get_fixtures(stage_id, overwrite=False):
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

    # Not needed - only first element required
    # fields = ['matchId', 'statusCode', 'startDate', 'koTime',
    #           ['home', 'teamId'], ['home', 'name'], ['home', 'redCards'],
    #           ['away', 'teamId'], ['away', 'name'], ['away', 'redCards'],
    #           'ftScore', 'htScore', 'hasScorer', 'unknown', 'elapsed', '1x2',
    #           ]

    dates = re.findall("'Month', ([^ ]+), min, max", r.text)
    if dates:
        dates = re.sub(r'(\d+)(?=:)', r'"\1"', dates[0])
        d = json.loads(dates)

        months = {format(d): format(d+1, '02') for d in range(0, 12)}
        params = {'d': '201602', 'isAggregate': 'false'}

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
                    match = {'matchId': row[0]}
                    if matches.find_one({'matchId': match['matchId']}) and not overwrite:
                        print('Match already exists')
                    else:
                        for k, v in stage.items():
                            if 'Id' in k:
                                match[k] = v

                        matches.replace_one({'matchId': match['matchId']}, match, upsert=True)
    else:
        matchData = re.findall("calendarParameter\), ([^;]*)\);", r.text)
        matchData = re.sub(r',(?=,)', r',null', matchData[0])
        data = json.loads(matchData.replace("'", '"') if matchData else '{}')

        for row in data:
            match = {'matchId': row[0]}
            if matches.find_one({'matchId': match['matchId']}) and not overwrite:
                print('Match already exists')
            else:
                for k, v in stage.items():
                    if 'Id' in k:
                        match[k] = v

                matches.replace_one({'matchId': match['matchId']}, match, upsert=True)
        wait()


def get_match(match_id, overwrite=False):
    if matches.find_one({'matchId': match_id}) and not overwrite:
        print('Match already exists')
        return True

    page = SITE+'/Matches/{0}/Live'.format(match_id)
    r = requests.get(page, headers=HEADERS)
    print(r.url)

    if r.status_code != 200:
        wait()
        return False

    if r.url != page:
        match = {'matchId': match_id, 'error': 'No page found'}
        print(match['error'])
        matches.update_one({'matchId': match['matchId']}, {'$set': {'error': match['error']}}, upsert=True)
        wait()
        return False

    matchId = re.findall("matchId = ([^;]+);", r.text)
    matchData = re.findall("matchCentreData = ([^;]+});", r.text)

    if matchData and matchData != ['null']:
        match = json.loads(matchData[0])
        match['matchId'] = int(matchId[0])

    else:
        matchHeader = re.findall("matchHeader.load\(([^;]+)\r\n\);", r.text)[0].replace("'", '"')
        matchHeader = re.sub(r',(?=,)', r',""', matchHeader)

        fields = [['home', 'teamId'], ['away', 'teamId'], ['home', 'name'], ['away', 'name'],
                  'startTime', 'startDate', 'statusCode', 'elapsed',
                  'htScore', 'ftScore', 'etScore', 'pkScore', 'score'
                  ]

        match = {'matchId': match_id, 'home': dict(), 'away': dict()}
        for k, v in zip(fields, json.loads(matchHeader)):
            if v:
                if type(k) == list:
                    match[k[0]][k[1]] = v
                else:
                    match[k] = v

    content = html.fromstring(r.text)
    link = content.xpath("//div[@id='breadcrumb-nav']/a/@href")

    if link:
        for key, val in re.findall(r'/(?P<key>\w+)/(?P<val>\d+)', link[0]):
            key = key[:-1].lower() + 'Id'
            match[key] = int(val)

    matches.replace_one({'matchId': match_id}, match, upsert=True)

    wait()
    return True


if __name__ == "__main__":
    get_all_tournaments()
    get_seasons()
    get_stages()
    get_fixtures(1)
