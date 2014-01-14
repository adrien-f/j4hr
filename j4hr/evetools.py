import eveapi
import os
import redis
import cPickle
import datetime
import time
import json
from .app import app, db
from .models import Corporation

r = redis.StrictRedis(host=app.config['REDIS'])
OUTPOSTS = json.loads(r.get('eve.stations'))


class RedisEveAPICacheHandler(object):

    def __init__(self):
        self.debug = app.config.get('DEBUG', False)
        self.r = redis.StrictRedis(
            host=app.config['REDIS'], port=int(os.getenv('REDIS_PORT', 6379)))

    def log(self, what):
        if self.debug:
            print "[%s] %s" % (datetime.datetime.now().isoformat(), what)

    def retrieve(self, host, path, params):
        key = hash((host, path, frozenset(params.items())))

        cached = self.r.get(key)
        if cached is None:
            self.log("%s: not cached, fetching from server..." % path)
            return None
        else:
            cached = cPickle.loads(cached)
            if time.time() < cached[0]:
                self.log("%s: returning cached document" % path)
                return cached[1]
            self.log("%s: cache expired, purging !" % path)
            self.r.delete(key)

    def store(self, host, path, params, doc, obj):
        key = hash((host, path, frozenset(params.items())))

        cachedFor = obj.cachedUntil - obj.currentTime
        if cachedFor:
            self.log("%s: cached (%d seconds)" % (path, cachedFor))

            cachedUntil = time.time() + cachedFor
            self.r.set(key, cPickle.dumps((cachedUntil, doc), -1))


class EveBadMaskException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class EveKeyExpirationException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class EveTools(object):
    client = eveapi.EVEAPIConnection(cacheHandler=RedisEveAPICacheHandler())

    def __init__(self, key_id=None, vcode=None):
        if key_id and vcode:
            self.auth(key_id, vcode)

    def auth(self, key_id, vcode):
        self.key_id = key_id
        self.vcode = vcode
        self.client = self.client.auth(keyID=key_id, vCode=vcode)
        self.authed = True

    def assert_mask(self):
        if not self.authed:
            raise Exception('No auth info')
        try:
            api_key_info = self.client.account.APIKeyInfo()
        except eveapi.Error, e:
            raise e
        except Exception, e:
            raise e
        else:
            mask = api_key_info.key.accessMask
            expiration = api_key_info.key.expires
            status = 'Ineligible'
            if mask == app.config['EVE']['alliance_mask']:
                status = 'Alliance'
            else:
                raise EveBadMaskException('Bad mask')
            if len(str(expiration)) > 0:
                raise EveKeyExpirationException(
                    'This key has an expiration date')
            return status, mask

    def get_characters(self, full=False):
        if not self.authed:
            raise Exception('No auth info')
        try:
            api_characters = self.client.account.Characters().characters
        except eveapi.Error, e:
            raise e
        except Exception, e:
            raise e
        if not full:
            return api_characters
        else:
            characters = []
            for character in api_characters:
                characters.append(
                    self.client.char.CharacterSheet(characterID=character.characterID))
            return characters

    def get_character(self, character_id):
        if not self.authed:
            raise Exception('No auth info')
        try:
            api_character = self.client.char.CharacterSheet(
                characterID=character_id)
        except eveapi.Error, e:
            raise e
        except Exception, e:
            raise e
        return api_character

    def check_eligibility(self, characters):
        # Building corporations list
        corporations = [
            corporation.id for corporation in Corporation.query.all()]
        for character in characters:
            if character.corporationID in corporations:
                character.disabled = True
            else:
                character.disabled = False
        return characters


def get_type_name(type_id):
    eve_db = db.get_engine(app, bind='eve')
    query = 'SELECT invTypes.typeID, invTypes.typeName, invTypes.basePrice, invGroups.groupName FROM invTypes JOIN invGroups ON invTypes.groupID=invGroups.groupID WHERE invTypes.typeID = :type_id'
    result = eve_db.engine.execute(query, type_id=type_id)
    item = {'type_id': None, 'name': None, 'group_name': None}
    for row in result:
        item['type_id'] = row[0]
        item['name'] = row[1]
        item['base_price'] = row[2]
        item['group_name'] = row[3]
        break
    return item


def get_location_name(location_id):
    eve_db = db.get_engine(app, bind='eve')
    location = None
    if 66000000 < location_id < 66014933:
        query = 'SELECT stationName FROM staStations WHERE stationID=:location_id;'
        result = eve_db.engine.execute(
            query, location_id=location_id - 6000001)
        for row in result:
            location = row[0]
            break
    if 66014934 < location_id < 67999999:
        location = OUTPOSTS[str(location_id - 6000000)]
    if 60014861 < location_id < 60014928:
        location = OUTPOSTS[str(location_id)]
    if 60000000 < location_id < 61000000:
        query = 'SELECT stationName FROM staStations WHERE stationID=:location_id;'
        result = eve_db.engine.execute(query, location_id=location_id)
        for row in result:
            location = row[0]
            break
    if location_id >= 61000000:
        location = OUTPOSTS[str(location_id)]
    else:
        query = 'SELECT itemName FROM mapDenormalize WHERE itemID=:location_id;'
        result = eve_db.engine.execute(query, location_id=location_id)
        for row in result:
            location = row[0]
            break
    return location


def parse_assets(assets_list):
    assets = []
    for api_asset in assets_list:
        asset = {}
        for index, key in enumerate(api_asset.__dict__['_cols']):
            if key == 'contents':
                continue
            try:
                asset[key] = api_asset.__dict__['_row'][index]
            except IndexError:
                asset[key] = None
        item_type = get_type_name(asset['typeID'])
        if 'locationID' in api_asset:
            asset['location_name'] = get_location_name(api_asset.locationID)
        asset['item_name'] = item_type['name']
        try:
            asset['base_price'] = item_type['base_price']
        except KeyError, e:
            asset['base_price'] = 0
        asset['group_name'] = item_type['group_name']
        assets.append(asset)
        if 'contents' in api_asset:
            parse_assets(api_asset.contents)
    return assets
