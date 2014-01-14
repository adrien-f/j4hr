# -*- coding: utf-8 -*-
import os

class Config(object):
    SECRET_KEY = '' # Your secret key
    APP_DIR = os.path.abspath(os.path.dirname(__file__))  # This directory
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))
    EVE = {
        "alliance_mask": 0, # API MASK TO SET PEOPLE TO ALLIANCE
        "allianceID": 0, # YOUR ALLIANCE ID
        "corporationKeyID": 0, # CEO CORP KEY ID
        "corporationKeyvCode": "", # CEO ALLIANCE KEY
        "disabled_corporations": [] # THE CORPORATIONS YOU DON'T WANT PEOPLE TO APPLY
    }
    REDDIT = {
        "client_id": "", # REDDIT CLIENT ID
        "client_secret": "", # REDDIT SECRET
        "state": "" # REDDIT STATE
    }
    AUTH = {
        "domain": "", # AUTH DOMAIN
        "alliance": "", # ALLIANCE NAME
        "allianceshort": "" # ALLIANCE SHORT
    }
    DOMAIN = '' # AUTH DOMAIN
    MAILGUN_API_KEY = '' # MAIL GUN API
    REDIS = '' # REDIS ADDRESS
    LOG_FILE = 'j4hr.log' # LOG FILE


class ProdConfig(Config):
    DEBUG = False # THIS IS PROD, NOT DEV
    SQLALCHEMY_DATABASE_URI = '' # CLASSIC SQLALCHEMY URL
    SQLALCHEMY_ECHO = False # YEAH
    SQLALCHEMY_BINDS = {
        'eve': 'sqlite:////srv/eve/eve.db' # THIS IS IMPORTANT, GET THE SQLITE EVEDB AND PUT THE PATH THERE
    }
    REDIS = '' # YA REDIS AGAIN
    LDAP = {
        "server": "", # LDAP SERVER ldap://ldap.j4lp.com/
        "admin": "", # LDAP ADMIN cn=administrator,dc=j4lp,dc=com
        "password": "", # LDAP USER ADMIN PASSWORD
        "basedn": "", # BASE DN dc=j4lp,dc=com
        "memberdn": "" # MEMBER DN ou=People,dc=j4lp,dc=com
    }
    SERVER_NAME = '' # SERVER NAME FOR FLASK URL j4lp.com
    LOG_FILE = '' # LOG FILE


class DevConfig(Config):
    DEBUG = True
    DB_NAME = "dev.db" # SQLITE DEV DB
    # Put the db file in project root
    DB_PATH = os.path.join(Config.PROJECT_ROOT, DB_NAME)
    EVE_PATH = os.path.join(Config.PROJECT_ROOT, 'eve.db')
    SQLALCHEMY_DATABASE_URI = "sqlite:///{0}".format(DB_PATH) # YOU GET THE THING
    SQLALCHEMY_BINDS = {
        'eve': 'sqlite:///{0}'.format(EVE_PATH) # SAME HERE
    }
    #SQLALCHEMY_ECHO = True
    LDAP = {
        "server": "", # LDAP SERVER ldap://ldap.j4lp.com/
        "admin": "", # LDAP ADMIN cn=administrator,dc=j4lp,dc=com
        "password": "", # LDAP USER ADMIN PASSWORD
        "basedn": "", # BASE DN dc=j4lp,dc=com
        "memberdn": "" # MEMBER DN ou=People,dc=j4lp,dc=com
    }


