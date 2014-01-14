===============================
J4HR
===============================

Human ressources application for your Eve Online alliance, you need to run a flavor of pizza-auth_


Quickstart
----------

::

    git clone https://github.com/adrien-f/j4hr
    cd j4hr
    pip install -r requirements.txt
    cp j4hr/settings_dist.py j4hr/settings.py
    # Edit your settings
    export J4HR_ENV='dev' # OR export J4HR_ENV='prod'
    python manage.py createdb
    python manage.py update_corporations
    python manage.py update_reftypes
    python manage.py update_outposts
    python manage.py runserver


Deployment
----------

::

    /srv/j4hr/bin/gunicorn j4hr.main:app -b 0.0.0.0:5000 -w 1


Note
----------
This does not include the report generating process (which is being rewritten at this moment), you will need to figure this out.
This does not create LDAP accounts, it is only an application to accept applications and for HR people to manage those but also the LDAP users and purge them (based on modifying the accountStatus of pizza-auth to the "purged" status).
However, it should be easy to adapt it to run on your existing auth infrastructure.
Feel free to contact me if you have trouble using it.

Licence
----------

Copyright (c) 2013, Adrien F
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

* Neither the name of J4HR nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

.. _pizza-auth : https://bitbucket.org/Sylnai/pizza-auth
