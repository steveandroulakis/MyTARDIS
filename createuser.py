#!/usr/bin/env python
# first run the command below in /opt/mytardis/current
# ln -s bin/django django_env.py
#
# Run the command below to create users.json. 
# bin/django dumpdata --indent=4 auth.User > users.json
# Transfer users.json across to the mytardis system to import to and run this script
import os
import sys
import site
import django_env

if __name__ == '__main__':

# Setup environ
    os.environ['DJANGO_SETTINGS_MODULE'] = "tardis.settings"
    site.addsitedir('/opt/mytardis/current/eggs')
    sys.path.append('/opt/mytardis/current')
    
from django.contrib.auth.models import User
from django.db import transaction
from tardis.tardis_portal.models import UserProfile, UserAuthentication
import json
'''
Created on Aug 13, 2013

@author: sindhue
'''

@transaction.commit_on_success
def create_user(username, email, password):
    status = 'failure'
    try:
        user = User.objects.create_user(username, email, password)

        userProfile = UserProfile(user=user, isDjangoAccount=True)
        userProfile.save()

        authentication = UserAuthentication(userProfile=userProfile,
                                            username=username,
                                            authenticationMethod=u'localdb')
        authentication.save()
        status = 'success'
    except:
        transaction.rollback()
        print 'Could not create user %s ', username
    return status
    
jsonfile = open('users.json', 'r')
users = json.loads(jsonfile.read())  
jsonfile.close()

for user in users:
    fields = user['fields']
    username = fields['username']
    email = fields['email']
    password = fields['password']
    status =create_user(username, email, password)
    print 'create user, %s: %s' % (username, status)
    
