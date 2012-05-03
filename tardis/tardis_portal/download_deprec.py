import logging
import subprocess
import urllib
from urllib2 import urlopen
from os import path, devnull

from django.core.servers.basehttp import FileWrapper
from django.http import HttpResponse, HttpResponseRedirect, \
    HttpResponseNotFound
from django.conf import settings

from tardis.tardis_portal.models import *
from tardis.tardis_portal.auth.decorators import *
from tardis.tardis_portal.views import return_response_not_found, \
    return_response_error

def download_datafile_ws(request):
    if 'url' in request.GET and len(request.GET['url']) > 0:
        url = urllib.unquote(request.GET['url'])
        raw_path = url.partition('//')[2]
        experiment_id = request.GET['experiment_id']

	print experiment_id
	print raw_path

        datafile = Dataset_File.objects.filter(
            url__endswith=raw_path, dataset__experiment__id=experiment_id)[0]

	print datafile

        if has_datafile_access(request=request,
                               dataset_file_id=datafile.id):

            file_path = datafile.get_absolute_filepath()

            try:
                wrapper = FileWrapper(file(file_path))

                response = HttpResponse(wrapper,
                                        mimetype=datafile.get_mimetype())
                response['Content-Disposition'] = \
                    'attachment; filename="%s"' % datafile.filename

                return response

            except IOError:
                try:
                    file_path = datafile.get_absolute_filepath_old()
                    wrapper = FileWrapper(file(file_path))

                    response = HttpResponse(wrapper,
                                            mimetype=datafile.get_mimetype())
                    response['Content-Disposition'] = \
                        'attachment; filename="%s"' % datafile.filename

                    return response
                except IOError:
                    return return_response_not_found(request)

        else:
            return return_response_not_found(request)

    else:
        return return_response_error(request)
