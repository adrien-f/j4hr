# -*- coding: utf-8 -*-

"""
J4HR models.
"""
import string
import random
import datetime
from ldap import MOD_REPLACE
from .app import db, ldaptools


class Corporation(db.Model):

    __tablename__ = 'corporations'

    id = db.Column(db.Integer, primary_key=True)  # corporationID
    name = db.Column(db.String)  # corporationName
    ticker = db.Column(db.String)  # ticker
    members = db.Column(db.Integer)  # memberCount
    active = db.Column(db.Boolean, default=True)

    def __init__(self, id=None, name=None, ticker=None, members=None):
        self.id = id
        self.name = name
        self.ticker = ticker
        self.members = members

    def __repr__(self):
        return '<Corporation "{name}">'.format(name=self.name)


class Application(db.Model):

    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)  # character name
    character_id = db.Column(db.Integer)
    corporation_id = db.Column(db.Integer, db.ForeignKey('corporations.id'))
    corporation = db.relationship(
        'Corporation', backref=db.backref('applications', lazy='dynamic'))
    email = db.Column(db.String)
    motivation = db.Column(db.Text)
    reddit_id = db.Column(
        db.Integer, db.ForeignKey('reddit.id'), nullable=True)
    reddit = db.relationship(
        'Reddit', backref=db.backref('reddit', lazy='dynamic'))
    key_id = db.Column(db.Integer)
    vcode = db.Column(db.String)
    access_key = db.Column(db.String)
    access_code = db.Column(db.Integer)
    status = db.Column(db.Integer, default=1)
    reject_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    def __init__(self, session=None):
        if session:
            self.name = session['character_name']
            self.character_id = session['character_id']
            self.corporation_id = session['corporation_id']
            self.email = session['email']
            self.motivation = session['motivation']
            self.key_id = session['key_id']
            self.vcode = session['vcode']
            self.access_key = ''.join(random.choice(string.ascii_uppercase + string.digits)
                                      for x in range(24))
            self.access_code = ''.join(random.choice(string.digits)
                                       for x in range(8))
            self.created_at = datetime.datetime.utcnow()
            self.updated_at = datetime.datetime.utcnow()

            if 'reddit' in session:
                reddit = Reddit(session)
                self.reddit_id = reddit.id

    def status_text(self):
        if self.status == 1:
            return 'pending'
        elif self.status == 2:
            return 'accepted'
        else:
            return 'rejected'


class Reddit(db.Model):

    __tablename__ = 'reddit'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String)
    scope = db.Column(db.String)
    access_token = db.Column(db.String)
    refresh_token = db.Column(db.String)
    refreshed_at = db.Column(db.DateTime)

    def __init__(self, session=None):
        if session and session['reddit']:
            reddit = session['reddit']
            self.username = reddit['username']
            self.scope = ','.join(reddit['scope'])
            self.access_token = reddit['access_token']
            self.refresh_token = reddit['refresh_token']
            refreshed_at = reddit['refreshed_at']
            db.session.add(self)
            db.session.commit()


class Purge(db.Model):

    __tablename__ = 'purge'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String)
    reason = db.Column(db.Text)
    purged_by = db.Column(db.String)
    purged_at = db.Column(db.DateTime)

    def __init__(self, username=None, reason=None):
        if username:
            self.username = username
        if reason:
            self.reason = reason

    def do_purge(self):
        user = ldaptools.getuser(self.username)
        if user is None:
            raise Exception('User not found in LDAP directory')
        try:
            ldaptools.modattr(
                user.get_id(), MOD_REPLACE, 'accountStatus', 'purged')
        except Exception, e:
            raise e


db.create_all()
