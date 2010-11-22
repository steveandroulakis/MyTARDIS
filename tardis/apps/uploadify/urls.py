from django.conf.urls.defaults import *
from tardis.apps.uploadify.views import *

urlpatterns = patterns('',
    url(r'upload/$', upload, name='uploadify_upload'),
)
