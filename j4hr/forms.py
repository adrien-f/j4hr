# -*- coding: utf-8 -*-
from flask_wtf import Form
from wtforms import PasswordField, TextAreaField
from wtforms_html5 import TextField
from wtforms.validators import DataRequired, Length, Email


class APIForm(Form):
    key_id = TextField('Key ID', validators=[DataRequired(), Length(min=7, max=7)])
    vcode = TextField('vCode', validators=[DataRequired(), Length(min=64, max=64)])


class ApplicationLoginForm(Form):
    application_id = TextField('Application #', validators=[DataRequired()])
    application_secret = PasswordField('Application secret', validators=[DataRequired()])


class ApplicationDetailsForm(Form):
    email = TextField('Email', validators=[DataRequired(), Email()])
    motivation = TextAreaField('Motivation', validators=[DataRequired()])


class LoginForm(Form):
    username = TextField('Username', validators=[DataRequired()])
    password = TextField('Password', validators=[DataRequired()])


class AcceptApplicationForm(Form):
    pass


class RejectApplicationForm(Form):
    message = TextField('Message')


class PurgeForm(Form):
    user_id = TextField('User')
    message = TextAreaField('Message')
