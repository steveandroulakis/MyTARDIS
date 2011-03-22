from django.test import TestCase
from django.test.client import Client
from django.conf.urls.defaults import *


class ModelTestCase(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        user = 'tardis_user1'
        pwd = 'secret'
        email = ''
        self.user = User.objects.create_user(user, email, pwd)


class ViewsTestCase(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        from tardis.tardis_portal.models import Experiment
        user = 'tardis_user1'
        pwd = 'secret'
        email = ''
        self.user = User.objects.create_user(user, email, pwd)
        self.client = Client()
        self.experiment = Experiment(approved=True,
                                     title="Test Experiment",
                                     institution_name="Test Institution",
                                     created_by=self.user,
                                     public=False)
        self.experiment.save()

    def test_view_index(self):
        print self.experiment.id
        print '/apps/mrtardis/index/%d/' % self.experiment.id
        response = self.client.get('/apps/mrtardis/index/%d/' %
                                   self.experiment.id)
        print response.status_code
        #self.assertEqual(response.status_code, 200)
        print "testing"
