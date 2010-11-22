from django.http import HttpResponse
import django.dispatch
from tardis.tardis_portal.logger import logger

upload_received = django.dispatch.Signal(providing_args=['data'])

def upload(request, *args, **kwargs):
    logger.debug("called upload")
    if request.method == 'POST':
        logger.debug("got POST")
        if request.FILES:
            logger.debug("got FILES")
            upload_received.send(sender='uploadify', data=request.FILES['Filedata'])
    return HttpResponse('True')


