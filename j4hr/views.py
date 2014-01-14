# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
from flask.ext.babel import format_date, format_datetime
from flask import render_template, session, request, flash, redirect, url_for, abort
from jinja2 import Markup
from .app import app, db, ldaptools, login_manager
from .forms import APIForm, ApplicationLoginForm, ApplicationDetailsForm
from .utils import flash_errors
from .models import Corporation, Application
from .admin import admin
from evetools import EveTools, EveBadMaskException, EveKeyExpirationException
from .app import mailgun
from eveapi import Error as EveAPIError
import praw


@app.route('/', methods=['GET'])
def home():
    api_form = APIForm(request.form)
    application_form = ApplicationLoginForm(request.form)
    return render_template('home.html', api_form=api_form, application_form=application_form)


@app.route('/apply/api_check', methods=['POST'])
def api_check():
    api_form = APIForm(request.form)
    if not api_form.validate():
        flash('Invalid API Form', 'danger')
        return redirect(url_for('home'))
    if api_form.validate_on_submit():
        key_id = session['key_id'] = request.form['key_id']
        vcode = session['vcode'] = request.form['vcode']
        api = EveTools(key_id, vcode)
        try:
            status, mask = session['status'], session['mask'] = api.assert_mask()
        except EveAPIError as e:
            app.logger.exception(e)
            session.clear()
            flash('API Error, please verify your API Key, try again and make sure API servers are up', 'danger')
            return redirect(url_for('home'))
        except EveBadMaskException as e:
            app.logger.exception(e)
            session.clear()
            flash('Wrong mask, please insure you created the right API Key', 'danger')
            return redirect(url_for('home'))
        except EveKeyExpirationException as e:
            app.logger.exception(e)
            session.clear()
            flash('Please set the expiration date to "No expiry" on your API Key', 'danger')
            return redirect(url_for('home'))
        except Exception as e:
            app.logger.exception(e)
            session.clear()
            flash('System error, please try again or contact someone from HR', 'danger')
            return redirect(url_for('home'))
        else:
            return redirect(url_for('characters'))


@app.route('/apply/characters', methods=['GET'])
def characters():
    if not session['key_id']:
        session.clear()
        flash('Session error, no API Key found in session', 'danger')
        return redirect(url_for('home'))
    api = EveTools(session['key_id'], session['vcode'])
    try:
        characters = api.get_characters(full=True)
    except EveAPIError as e:
        app.logger.exception(e)
        session.clear()
        flash('API Error, could not retrieve list of characters', 'danger')
        return redirect(url_for('home'))
    except Exception as e:
        app.logger.exception(e)
        session.clear()
        flash('System error, please try again or contact someone from HR', 'danger')
        return redirect(url_for('home'))
    characters = api.check_eligibility(characters)
    return render_template('characters.html', characters=characters)


@app.route('/apply/characters/<int:character_id>', methods=['GET'])
def use_character(character_id):
    if not session['key_id']:
        session.clear()
        flash('Session error, no API Key found in session', 'danger')
        return redirect(url_for('home'))
    api = EveTools(session['key_id'], session['vcode'])
    characters = api.check_eligibility(api.get_characters(full=True))
    for character in characters:
        if character.characterID == character_id and not character.disabled:
            session['character_id'] = character_id # character_id is in the list
            session['character_name'] = character.name
            break
    else:
        app.logger.error('Attempt to select a character who does not belong to the user')
        session.clear()
        abort(403)
    return redirect(url_for('corporations'))


@app.route('/apply/corporations', methods=['GET'])
def corporations():
    corporations = Corporation.query.filter_by(active=True).all()
    return render_template('corporations.html', corporations=corporations)


@app.route('/apply/corporations/<int:corporation_id>', methods=['GET'])
def apply_corporation(corporation_id):
    if not session['key_id']:
        session.clear()
        flash('Session error, no API Key found in session', 'danger')
        return redirect(url_for('home'))
    corporations = Corporation.query.filter_by(active=True).all()
    for _corporation in corporations:
        if _corporation.id == corporation_id:
            corporation = _corporation
            session['corporation_id'] = corporation_id
            break # corporation_id is an available corporation
    else:
        app.logger.error('Attempt to apply to a disable/not existent corporation')
        session.clear()
        abort(403)
    # Special case for Fweddit (corporation #98114328)
    if corporation_id == 98114328:
        return redirect(url_for('associate_reddit'))
    else:
        return redirect(url_for('apply'))


@app.route('/apply/fweddit', methods=['GET'])
def associate_reddit():
    if not session['key_id']:
        session.clear()
        flash('Session error, no API Key found in session', 'danger')
        return redirect(url_for('home'))
    if not session['corporation_id'] or session['corporation_id'] != 98114328:
        session.clear()
        flash('Session error, no corporation found in session', 'danger')
        return redirect(url_for('home'))
    r = praw.Reddit('HR Tool 0.1 for J4LP /r/fweddit alliance by sakacoco')
    r.set_oauth_app_info(
        client_id=app.config['REDDIT']['client_id'],
        client_secret=app.config['REDDIT']['client_secret'],
        redirect_uri=url_for('associate_reddit_callback', _external=True))
    url = r.get_authorize_url(app.config['REDDIT']['state'], 'identity,history', True)
    return render_template('reddit.html', url=url)


@app.route('/apply/fweddit_callback', methods=['GET'])
def associate_reddit_callback():
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')
    if error and error == 'access_denied':
        session.clear()
        flash('Reddit error, you have denied us access to your reddit account, application process cancelled')
        return redirect(url_for('home'))
    if not code or not state:
        session.clear()
        abort(400)
    if state != app.config['REDDIT']['state']:
        session.clear()
        abort(403)
    r = praw.Reddit('HR Tool 0.1 for J4LP /r/fweddit alliance by sakacoco')
    r.set_oauth_app_info(
        client_id=app.config['REDDIT']['client_id'],
        client_secret=app.config['REDDIT']['client_secret'],
        redirect_uri=url_for('associate_reddit_callback', _external=True))
    reddit_access = r.get_access_information(code)
    r.set_access_credentials(**reddit_access)
    reddit_user = r.get_me()
    reddit_access['username'] = reddit_user.name
    reddit_access['refreshed_at'] = datetime.datetime.utcnow()
    reddit_access['scope'] = list(reddit_access['scope'])
    # Let's store this in session for the time being
    session['reddit'] = reddit_access
    flash('Reddit authentication successful', 'success')
    return redirect(url_for('apply'))


@app.route('/apply', methods=['GET'])
def apply():
    if not session['key_id'] or not session['vcode'] or not session['character_id'] or not session['corporation_id']:
        session.clear()
        flash('Session error', 'danger')
        return redirect(url_for('home'))
    corporation = Corporation.query.get(session['corporation_id'])
    form = ApplicationDetailsForm(request.form)
    return render_template('apply.html', corporation=corporation, form=form)


@app.route('/apply/summary', methods=['POST'])
def apply_summary():
    if not session['key_id'] or not session['vcode'] or not session['character_id'] or not session['corporation_id']:
        session.clear()
        flash('Session error', 'danger')
        return redirect(url_for('home'))
    form = ApplicationDetailsForm(request.form)
    if not form.validate():
        flash('Invalid Motivation Form', 'danger')
        return redirect(url_for('apply'))
    if form.validate_on_submit():
        api = EveTools(session['key_id'], session['vcode'])
        session['motivation'] = request.form['motivation']
        session['email'] = request.form['email']
        corporation = Corporation.query.get(session['corporation_id'])
        character = api.get_character(session['character_id'])
        return render_template('apply_summary.html', corporation=corporation, character=character)


@app.route('/apply/do_apply', methods=['GET'])
def do_apply():
    if not session['key_id'] or not session['vcode'] or not session['character_id'] or not session['corporation_id'] or not session['motivation'] or not session['email']:
        session.clear()
        flash('Session error', 'danger')
        return redirect(url_for('home'))
    try:
        application = Application(session)
        db.session.add(application)
    except Exception, e:
        app.logger.exception(e)
        abort(500)
    try:
        email = mailgun.create_email('new_application.html', {
            'character_name': application.name,
            'application_id': application.access_key,
            'application_secret': application.access_code})
        email['Subject'] = 'New Application | J4LP Human Resources'
        email['From'] = 'J4LP HR <hr@j4lp.com>'
        mailgun.send_email(application.email, email)
    except Exception, e:
        app.logger.exception(e)
        session.clear()
        flash('That\'s embarassing... We were not able to send you the confirmation email, please try again !', 'danger')
        return redirect(url_for('home'))
    db.session.commit()
    session.clear()
    flash('Your application has been registered, check your email for more informations !', 'success')
    return redirect(url_for('home'))


@app.route('/status', methods=['POST'])
def status():
    form = ApplicationLoginForm(request.form)
    if not form.validate():
        flash('Invalid Form', 'danger')
        return redirect(url_for('home'))
    if form.validate_on_submit():
        try:
            application = Application.query.filter_by(access_key=request.form['application_id']).filter_by(access_code=request.form['application_secret']).first()
        except Exception, e:
            app.logger.exception(e)
            flash('An error happened while logging you in, make sure you put the right login infos', 'danger')
            return redirect(url_for('home'))
        if application is None:
            flash('Invalid credentials', 'danger')
            app.logger.error('Invalid credentials {0}/{1}'.format(request.form.application_id, request.forn.application_secret))
            return redirect(url_for('home'))
        app.logger.info('Application #{0} opened by user'.format(application.id))
        return render_template('status.html', application=application)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.template_filter('datetime')
def filter_datetime(value, format='medium'):
    if format == 'full':
        format="EEEE, d. MMMM y 'at' HH:mm"
    elif format == 'medium':
        format="EE dd.MM.y HH:mm"
    return format_datetime(value, format)


@app.template_filter('date')
def filter_date(value):
    format="EE dd MMM y"
    return format_date(value, format)


@app.template_filter('date_from_unix')
def filter_date_from_unix(value):
    value = datetime.datetime.fromtimestamp(value)
    format="EE dd MMM y"
    return format_date(value, format)

@app.template_filter('datetime_from_unix')
def filter_datetime_from_unix(value, format='medium'):
    value = datetime.datetime.fromtimestamp(value)
    if format == 'full':
        format="EEEE, d. MMMM y 'at' HH:mm"
    elif format == 'medium':
        format="EE dd.MM.y HH:mm"
    return format_datetime(value, format)


@app.context_processor
def inject_icon():
    def icon(icon_name):
        return Markup('<i class="fa fa-{icon}"></i>'.format(icon=icon_name))
    return dict(icon=icon)


app.register_blueprint(admin, url_prefix='/admin')
