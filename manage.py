#!/usr/bin/env python
import json
import sys
import os
import subprocess
from flask.ext.script import Manager, Shell, Server, prompt, prompt_pass
import redis
import requests
from j4hr.main import app, db, ldaptools
from j4hr.models import Corporation
from j4hr.evetools import EveTools

manager = Manager(app)
TEST_CMD = "nosetests"


def _make_context():
    '''Return context dict for a shell session so you can access
    app, db, and models by default.
    '''
    return {'app': app, 'db': db, 'models': models}


@manager.command
def test():
    '''Run the tests.'''
    status = subprocess.call(TEST_CMD, shell=True)
    sys.exit(status)


@manager.command
def createdb():
    '''Create a database from the tables defined in models.py.'''
    db.create_all()


@manager.command
def update_corporations():
    '''Update corporations from alliance list.'''
    api = EveTools(app.config['EVE']['corporationKeyID'],
                   app.config['EVE']['corporationKeyvCode'])
    app.logger.info('Starting updating of alliance\'s corporations')
    alliances = api.client.eve.AllianceList().alliances
    # Looking for our alliance
    for api_alliance in alliances:
        if api_alliance.allianceID == app.config['EVE']['allianceID']:
            alliance = api_alliance
            break
    else:
        raise Exception('Alliance not found')
    app.logger.info(
        'Alliance "{alliance} found, updating corporations"'.format(alliance=alliance.name))
    corporations = []
    for member_corporation in alliance.memberCorporations:
        corporation_sheet = api.client.corp.CorporationSheet(
            corporationID=member_corporation.corporationID)
        corporation = Corporation(
            id=corporation_sheet.corporationID,
            name=corporation_sheet.corporationName,
            ticker=corporation_sheet.ticker,
            members=corporation_sheet.memberCount)
        if member_corporation.corporationID in app.config['EVE']['disabled_corporations']:
            corporation.active = False
        else:
            corporation.active = True
        db.session.merge(corporation)
    app.logger.info('Updating database with the corporations')
    db.session.commit()
    app.logger.info('Corporations updated with success !')


@manager.command
def update_reftypes():
    '''Update Reference Types from Eve API'''
    api = EveTools()
    reftypes = api.client.eve.RefTypes()
    refs = {}
    for ref in reftypes.refTypes:
        refs[str(ref.refTypeID)] = ref.refTypeName
    r = redis.StrictRedis(host=app.config['REDIS'])
    r.set('eve.refs', json.dumps(refs))
    app.logger.info('Wallet Reference Types updated with success !')


@manager.command
def update_outposts():
    '''Update Conquerable stations amd Outposts from Eve API'''
    api = EveTools()
    api_stations = api.client.eve.ConquerableStationList()
    stations = {}
    for station in api_stations.outposts:
        stations[str(station.stationID)] = station.stationName + \
            ' (%s)' % station.corporationName
    r = redis.StrictRedis(host=app.config['REDIS'])
    r.set('eve.stations', json.dumps(stations))


manager.add_command("runserver", Server(
    host='0.0.0.0', port=os.getenv('PORT', 5000), debug=True))
manager.add_command("shell", Shell(make_context=_make_context))

if __name__ == '__main__':
    manager.run()
