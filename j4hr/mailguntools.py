from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from jinja2 import Template
import requests


class MailGunTools(object):

    def __init__(self, domain=None, api_key=None, root=None):
        self.configured = False
        if domain and api_key:
            self.domain = domain
            self.api_key = api_key
            self.root = root
            self.configured = True

    def send_email(self, to, mime):
        if not self.configured:
            raise Exception('MailGunTools not configured.')
        return requests.post(
            'https://api.mailgun.net/v2/' + self.domain + '/messages.mime',
            auth=('api', self.api_key),
            data={"to": to},
            files={'message': mime.as_string()}
        )

    def create_email(self, template_name, data):
        try:
            with open(os.path.join(self.root, 'templates/emails/') + template_name) as f:
                template = f.read()
        except Exception, e:
            raise e
        template = Template(template)
        email = MIMEMultipart('alternative')
        try:
            email.attach(MIMEText(template.render(data), 'html'))
        except Exception, e:
            raise e
        return email
