from django.test import TestCase
from django.test.client import Client
from django.conf.urls.defaults import patterns, include, handler500, handler404


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
        from tardis.tardis_portal.models import ExperimentACL
        from tardis.tardis_portal.models import Dataset
        user = 'tardis_user1'
        pwd = 'secret'
        email = ''
        self.user = User.objects.create_user(user, email, pwd)
        self.client = Client()
        self.client.login(username=user, password=pwd)
        self.experiment = Experiment(approved=True,
                                     title="Test Experiment",
                                     institution_name="Test Institution",
                                     created_by=self.user,
                                     public=False)
        self.experiment.save()
        acl = ExperimentACL(pluginId="django_user",
                            entityId="1",
                            experiment=self.experiment,
                            canRead=True,
                            canWrite=True,
                            canDelete=True,
                            isOwner=True)
        acl.save()
        self.test_dataset = Dataset(experiment=self.experiment,
                                    description="test dataset")
        self.test_dataset.save()
        print acl

    def test_view_index(self):
        response = self.client.get('/apps/mrtardis/index/%d/' %
                                   self.experiment.id,
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

    def test_hpc_user_setup(self):
        import tardis.apps.mrtardis.utils as utils
        testresult = utils.test_hpc_connection(self.user)
        self.assertEqual(testresult, False)

    def test_views_test_user_setup(self):
        # with POST:
        posturl = '/apps/mrtardis/test_user_setup/%d/' % self.experiment.id
        response = self.client.post(posturl, {'hpc_username': 'john'},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 302)
        from tardis.apps.mrtardis.models import HPCUser
        self.assertEqual(HPCUser.objects.get(user=self.user).hpc_username,
                         'john')

    def test_views_MRform(self):
        posturl = '/apps/mrtardis/MRform/%d/' % self.experiment.id
        postdataarray = [{'postdata':
                              {'action': 'newDS',
                               'description': 'who is testing the testers?'},
                          'expectedoutcome': ""},
                         {'postdata':
                              {'action': 'continue',
                               'dataset': '1'},
                          'expectedoutcome': ""},
                         {'postdata':
                              {'action': 'rerunDS',
                               'dataset': '1'},
                          'expectedoutcome': ""},
                         ]
        for actiontype in postdataarray:
            postdata = actiontype['postdata']
            response = self.client.post(posturl, postdata,
                                        HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertEqual(len(response.content), 4669)

    def test_views_displayResults(self):
        posturl = '/apps/mrtardis/displayResults/%d/' % self.experiment.id
        response = self.client.post(posturl, {'dataset': 1},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

    def test_views_type_filtered_file_list(self):
        posturl = '/apps/mrtardis/type_filtered_file_list/%d/' %\
            self.test_dataset.id
        filetypes = [".mtz", ".pdb"]
        for filetype in filetypes:
            response = self.client.post(posturl, {'type': filetype},
                                        HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertEqual(response.status_code, 200)

    def test_views_add_pdb_files(self):
        from tardis.tardis_portal.models import Dataset
        posturl = '/apps/mrtardis/type_filtered_file_list/%d/' %\
            self.test_dataset.id

