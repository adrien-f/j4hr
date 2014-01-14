import datetime
import json
from collections import Counter
from time import sleep
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, session, jsonify
from .forms import LoginForm, AcceptApplicationForm, RejectApplicationForm, PurgeForm
from .app import app, db, login_manager, ldaptools, mailgun
from .models import Application, Corporation, Purge
from flask.ext.login import login_user, logout_user, login_required, current_user
from evetools import EveTools, parse_assets, EveBadMaskException, EveKeyExpirationException
import redis
import requests
from eveapi import IndexRowset, Rowset, Element
from eveapi import Error as EveAPIError
from sqlalchemy import desc
from ldaptools import UserPurgedException


admin = Blueprint('admin', 'j4hr', template_folder='templates/admin')

login_manager.login_view = 'admin.login'

@login_manager.user_loader
def load_user(userid):
    return ldaptools.getuser(userid)

@admin.route('/', methods=['GET'])
@login_required
def index():
    corporation = Corporation.query.filter_by(name=current_user.corporation[0]).first()
    applications = corporation.applications.all()
    stats = {}
    counters = Counter(accepted=0, rejected=0, created=len(applications))
    if applications:
        for application in applications:
            if application.created_at.strftime('%Y-%m-%d') not in stats:
                stats[application.created_at.strftime('%Y-%m-%d')] = Counter(accepted=0, rejected=0, new=0)
            stats[application.created_at.strftime('%Y-%m-%d')]['new'] =+ 1
            if application.status > 1:
                if application.updated_at.strftime('%Y-%m-%d') not in stats:
                    stats[application.updated_at.strftime('%Y-%m-%d')] = Counter(accepted=0, rejected=0, new=0)
                stats[application.updated_at.strftime('%Y-%m-%d')][application.status_text()] =+ 1
            counters[application.status_text()] =+ 1
    else:
        stats[datetime.datetime.utcnow().strftime('%Y-%m-%d')] = Counter(accepted=0, rejected=0, new=0)
    stats = [{'date': key, 'new': int(item['new']), 'accepted': int(item['accepted']), 'rejected': int(item['rejected'])} for key, item in stats.iteritems()]
    return render_template('index.html', corporation=corporation, stats=json.dumps(stats), counters=counters)

@admin.route('/applications', methods=['GET'])
@login_required
def applications():
    corporation = Corporation.query.filter_by(name=current_user.corporation[0]).first()
    db_applications = corporation.applications.order_by(desc(Application.created_at)).all()
    applications = {'pending': [], 'accepted': [], 'rejected': []}
    for application in db_applications:
        if application.status == 1:
            applications['pending'].append(application)
        elif application.status == 2:
            applications['accepted'].append(application)
        else:
            applications['rejected'].append(application)
    return render_template('applications.html', applications=applications, now=datetime.datetime.utcnow())


@admin.route('/application/<int:application_id>/report', methods=['GET'])
@login_required
def report(application_id):
    application = Application.query.get(application_id)
    r = redis.StrictRedis(host=app.config['REDIS'])
    if not application:
        abort(404)
    if application.corporation.name != current_user.corporation[0] and session['admin'] is False:
        flash('This application is not for your application. You bad.', 'danger')
        app.logger.error('{0} tried to access application {1} for corporation {3}'.format(current_user.get_id(), application_id, application.corporation.name))
        return redirect(url_for('admin.index'))
    report = r.get('j4hr:report:%s' % application_id)
    if report is None:
        return render_template('report_pending.html', application_id=application_id)
    accept_form = AcceptApplicationForm()
    reject_form = RejectApplicationForm()

    return render_template('report.html',
        report=json.loads(report),
        application=application,
        accept_form=accept_form,
        reject_form=reject_form)


@admin.route('/application/<int:application_id>/accept', methods=['POST'])
@login_required
def accept(application_id):
    application = Application.query.get(application_id)
    if not application:
        abort(404)
    if application.corporation.name != current_user.corporation[0] and session['admin'] is False:
        flash('This application is not for your application. You bad.', 'danger')
        app.logger.error('{0} tried to access application {1} for corporation {3}'.format(current_user.get_id(), application_id, application.corporation.name))
        return redirect(url_for('admin.index'))
    form = AcceptApplicationForm(request.form)
    if not form.validate():
        flash('Invalid API Form', 'danger')
        return redirect(url_for('home'))
    if form.validate_on_submit():
        application.status = 2
        application.updated_at = datetime.datetime.utcnow()
        db.session.add(application)
        try:
            email = mailgun.create_email('accepted.html', {
                'character_name': application.name,
                'corporation': application.corporation.name})
            email['Subject'] = 'You have been accepted ! | J4LP Human Resources'
            email['From'] = 'J4LP HR <hr@j4lp.com>'
            mailgun.send_email(application.email, email)
        except Exception as e:
            app.logger.exception(e)
            session.clear()
            flash('That\'s embarassing... We were not able to send the confirmation email so please contact that user IG !', 'danger')
        db.session.commit()
        app.logger.info('{0} accepted application #{1}'.format(current_user.uid[0], application_id))
        flash('Application accepted with success, an email has been sent.', 'success')
        return redirect(url_for('admin.applications'))


@admin.route('/application/<int:application_id>/reject', methods=['POST'])
@login_required
def reject(application_id):
    application = Application.query.get(application_id)
    if not application:
        abort(404)
    if application.corporation.name != current_user.corporation[0] and session['admin'] is False:
        flash('This application is not for your application. You bad.', 'danger')
        app.logger.error('{0} tried to access application {1} for corporation {3}'.format(current_user.get_id(), application_id, application.corporation.name))
        return redirect(url_for('admin.index'))
    form = RejectApplicationForm(request.form)
    if not form.validate():
        flash('Invalid API Form', 'danger')
        return redirect(url_for('home'))
    if form.validate_on_submit():
        application.status = 99
        application.updated_at = datetime.datetime.utcnow()
        application.reject_message = request.form.get('message', None)
        db.session.add(application)
        try:
            email = mailgun.create_email('rejected.html', {
                'character_name': application.name,
                'corporation': application.corporation.name,
                'message': request.form.get('message', None)})
            email['Subject'] = 'Your application has been rejected | J4LP Human Resources'
            email['From'] = 'J4LP HR <hr@j4lp.com>'
            mailgun.send_email(application.email, email)
        except Exception as e:
            app.logger.exception(e)
            session.clear()
            flash('That\'s embarassing... We were not able to send the confirmation email so please contact that user IG !', 'danger')
        db.session.commit()
        app.logger.info('{0} rejected application #{1}'.format(current_user.uid[0], application_id))
        flash('Application rejected with success, an email has been sent.', 'success')
        return redirect(url_for('admin.applications'))


@admin.route('/application/<int:application_id>/report/status', methods=['GET'])
@login_required
def report_status(application_id):
    application = Application.query.get(application_id)
    if application is None:
        return jsonify(status='error')
    r = redis.StrictRedis(host=app.config['REDIS'])
    lock = r.get('j4hr:report:%s:lock' % application_id)
    report = r.get('j4hr:report:%s' % application_id)
    if lock is not None and report is None:
        return jsonify(status='generating')
    elif report is not None:
        return jsonify(status='done')
    else:
        return jsonify(status='error')

@admin.route('/application/<int:application_id>/report/generate', methods=['GET'])
@login_required
def generate_report(application_id):
    application = Application.query.get(application_id)
    r = redis.StrictRedis(host=app.config['REDIS'])
    lock = r.get('j4hr:report:%s:lock' % application_id)
    if lock is not None:
        abort(418)
    r.set('j4hr:report:%s:lock' % application_id, True)
    r.expire('j4hr:report:%s:lock' % application_id, 240)
    r.delete('j4hr:report:%s' % application_id)
    report = {'characters': [], 'errors': []}
    app.logger.info('Starting generating report #%s' % application_id)
    api = EveTools(application.key_id, application.vcode)

    # Double check api key expiration
    try:
        status, mask = api.assert_mask()
    except EveAPIError as e:
        app.logger.exception(e)
        report['errors'].append(str(e))
    except EveBadMaskException as e:
        app.logger.exception(e)
        report['errors'].append(str(e))
    except EveKeyExpirationException as e:
        app.logger.exception(e)
        report['errors'].append(str(e))
    except Exception as e:
        app.logger.exception(e)
        report['errors'].append(str(e))
    except RuntimeError as e:
        app.logger.exception(e)
        report['errors'].append(str(e))
    else:
        for api_character in api.client.account.Characters().characters:
            # Get character informations
            character = {'sheet': {}, 'corporations': [], 'wallet': [], 'contacts': [], 'assets': []}

            # YEAH, not giving that away, you can figure it out.

            report['characters'].append(character)
    r.set('j4hr:report:%s' % application_id, json.dumps(report))
    r.delete('j4hr:report:%s:lock' % application_id)
    app.logger.info('Report generated for application #{0}'.format(application_id))
    return redirect(url_for('admin.report', application_id=application_id))


@admin.route('/badies', methods=['GET'])
@login_required
def badies():
    corporation = Corporation.query.filter_by(name=current_user.corporation[0]).first()
    if corporation is None:
        abort(404)

    r = redis.StrictRedis(host=app.config['REDIS'])
    badies = r.get('j4hr:badies:{0}'.format(corporation.id))
    if badies is None:
        limit = 200
        done = False
        page = 0
        badies = []
        ldap_users = [user.characterName[0] for user in ldaptools.getusers('corporation={0}'.format(corporation.name))]
        while not done:
            req = requests.get('http://evewho.com/api.php?type=corplist&id={0}&page={1}'.format(corporation.id, page))
            sleep(3)
            page += 1
            characters = req.json()['characters']
            for character in characters:
                if character['name'] not in ldap_users:
                    badies.append((character['name'], character['character_id']))
            if len(characters) < limit:
                done = True
        r.set('j4hr:badies:{0}'.format(corporation.id), json.dumps(badies))
        r.expire('j4hr:badies:{0}'.format(corporation.id), 3600)
    else:
        badies = json.loads(badies)
    return render_template('badies.html', badies=badies, corporation=corporation)


@admin.route('/auth', methods=['GET'])
@login_required
def auth_users():
    purge_form = PurgeForm(request.form)
    users = ldaptools.getusers('corporation={0}'.format(current_user.corporation[0]))
    return render_template('users.html', users=users, purge_form=purge_form)


@admin.route('/auth/purge', methods=['POST'])
@login_required
def auth_purge():
    purge_form = PurgeForm(request.form)
    if not purge_form.validate():
        flash('Form error', 'danger')
        return redirect(url_for('admin.applications'))
    user = ldaptools.getuser(request.form.get('user_id'))
    if user is None:
        flash('There was an error purging this user: User not found', 'danger')
        return redirect(url_for('admin.applications'))
    purge = Purge(username=user.get_id(), reason=request.form.get('message', 'No message'))
    purge.purged_by = current_user.get_id()
    purge.purged_at = datetime.datetime.utcnow()
    db.session.add(purge)
    db.session.commit()
    try:
        purge.do_purge()
    except Exception, e:
        app.logger.exception(e)
        flash('There was an error purging this user: %s' % str(e), 'danger')
    else:
        flash('User purged.', 'success')
    return redirect(url_for('admin.auth_users'))


@admin.route('/logout', methods=['GET'])
def logout():
    username = current_user.get_id()
    logout_user()
    app.logger.info('User {0} logged out of J4HR'.format(username))
    flash('You have been logged out.', 'success')
    return redirect(url_for('admin.login'))

@admin.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST':
        if not form.validate():
            flash('Form validation error', 'danger')
            return redirect(url_for('admin.login'))
        else:
            username = request.form["username"]
            password = request.form["password"]
            try:
                ldap_check = ldaptools.check_credentials(username, password)
            except UserPurgedException, e:
                app.logger.exception(e)
                flash('You have been purged.', 'danger')
                return redirect(url_for('home'))
            if ldap_check:
                user = ldaptools.getuser(username)
                if ('hr' not in user.get_authgroups()):
                    app.logger.error('Attempted authentication with login {0}'.format(username))
                    session.clear()
                    flash('You do not have the authorization to access this resource.', 'danger')
                    return redirect(url_for('home'))
                if 'admin' in user.get_authgroups():
                    session['admin'] = True
                else:
                    session['admin'] = False
                login_user(user)
                app.logger.info('User {0} successfully logged into J4HR'.format(user.get_id()))
                return redirect(url_for('admin.index'))
            else:
                flash('So bad. Invalid credentials, please try again.', 'danger')
                return redirect(url_for('admin.login'))
    return render_template('login.html', form=form)
