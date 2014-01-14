# -*- coding: utf-8 -*-
import os
import logging
from logging import Formatter
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.assets import Environment
from flask.ext.babel import Babel
from webassets.loaders import PythonLoader
from flask.ext.login import LoginManager
from j4hr import assets
from ldaptools import LDAPTools
from mailguntools import MailGunTools

app = Flask(__name__)
# The environment variable, either 'prod' or 'dev'
env = os.environ.get("J4HR_ENV", "dev")
# Use the appropriate environment-specific settings
app.config.from_object('j4hr.settings.{env}Config'
                        .format(env=env.capitalize()))
app.config['ENV'] = env
db = SQLAlchemy(app)
babel = Babel(app)
login_manager = LoginManager()
login_manager.init_app(app)
ldaptools = LDAPTools(app.config)
mailgun = MailGunTools(domain=app.config['DOMAIN'], api_key=app.config['MAILGUN_API_KEY'], root=app.config['APP_DIR'])

# Register asset bundles
assets_env = Environment()
assets_env.init_app(app)
assets_loader = PythonLoader(assets)
for name, bundle in assets_loader.load_bundles().iteritems():
    assets_env.register(name, bundle)

file_handler = RotatingFileHandler(app.config['LOG_FILE'])
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(Formatter(
    '%(asctime)s %(levelname)s: %(message)s '
    '[in %(pathname)s:%(lineno)d]'
))
app.logger.addHandler(file_handler)
