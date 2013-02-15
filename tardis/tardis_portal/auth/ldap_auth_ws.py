# -*- coding: utf-8 -*-
#
# Copyright (c) 2010-2011, Monash e-Research Centre
#   (Monash University, Australia)
# Copyright (c) 2010-2011, VeRSI Consortium
#   (Victorian eResearch Strategic Initiative, Australia)
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    *  Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    *  Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#    *  Neither the name of the VeRSI, the VeRSI Consortium members, nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
'''
LDAP Authentication module.

.. moduleauthor:: Gerson Galang <gerson.galang@versi.edu.au>
.. moduleauthor:: Russell Sim <russell.sim@monash.edu>
.. moduleauthor:: Steve Androulakis <steve.androulakis@monash.edu>
'''

import logging
import urllib
import json

from django.conf import settings

from tardis.tardis_portal.auth.interfaces import AuthProvider, \
    GroupProvider, UserProvider
from tardis.tardis_portal.models import UserAuthentication


logger = logging.getLogger(__name__)


auth_key = u'ldap_ws'
auth_display_name = u'LDAP'


class LDAP_WSBackend(AuthProvider, UserProvider, GroupProvider):
    def __init__(self):

        # Basic info
        self._url = settings.LDAP_WS_URL

    #
    # AuthProvider
    #
    def authenticate(self, request):
        username = request.POST['username']
        password = request.POST['password']

        if not username or not password:
            return None

        params = urllib.urlencode({'username': username, 'password': password})
        f = urllib.urlopen(self._url, params)

        if f.getcode() != 200:
            return None

        response = f.read()

        user = json.loads(response)
        logger.info(user)

        user['first_name'] = user['firstname']
        user['last_name'] = user['surname']

        user['display'] = "%s %s" \
            % (user['first_name'], user['last_name'])

        return user

    def get_user(self, user_id):
        return self.getUserById(user_id)

    #
    # User Provider
    #
    def getUserById(self, user_id):
        """
        return the user dictionary in the format of::

            {"id": 123,
            "display": "John Smith",
            "email": "john@example.com"}

        """
        f = urllib.urlopen("%s%s/" % (self._url, user_id))

        if f.getcode() != 200:
            return None

        response = f.read()
        user = json.loads(response)
        user['first_name'] = user['display']
        user['last_name'] = user['surname']

        return user

    #
    # Group Provider
    #
    def getGroups(self, request):
        """return an iteration of the available groups.
        """
        return []

    def searchGroups(self, **filter):
        return []
