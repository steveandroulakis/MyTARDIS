from django.conf.urls.defaults import patterns
#from django.conf import settings

urlpatterns = patterns('',
#    (r'^$', 'tardis.apps.mrtardis.views.index'),
                       (r'^index/(?P<experiment_id>\d+)/$',
                        'tardis.apps.mrtardis.views.index'),
                       (r'^startMR/(?P<experiment_id>\d+)/$',
                        'tardis.apps.mrtardis.views.startMR'),
                       (r'^test_user_setup$',
                        'tardis.apps.mrtardis.views.test_user_setup'),
                       (r'^jobstatus/(?P<experiment_id>\d+)/$',
                        'tardis.apps.mrtardis.views.jobstatus'),
                       (r'^upload_complete/(?P<experiment_id>\d+)/$',
                        'tardis.apps.mrtardis.views.upload_complete'),
                       (r'^MRparams/$',
                        'tardis.apps.mrtardis.views.MRParams'),
                       )
