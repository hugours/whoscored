from pymongo import MongoClient
from time import sleep
from random import random


def wait(delay=2, variation=1):
    m, x, c = variation, random(), delay - variation / 2
    sleep(m * x + c)

SITE = 'http://www.whoscored.com'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

client = MongoClient()
if client:
    regions = client.whoscored.regions
    tournaments = client.whoscored.tournaments
    seasons = client.whoscored.seasons
    stages = client.whoscored.stages
    matches = client.whoscored.matches
    events = client.whoscored.events
    players = client.whoscored.players
    teams = client.whoscored.teams
