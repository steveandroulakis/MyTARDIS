from django.http import HttpResponseRedirect
from django.conf import settings


def ajax_only(f):

    def wrap(request, *args, **kwargs):
        if not settings.DEBUG:
            if not request.is_ajax():
                if 'HTTP_REFERER' in request.META:
                    return HttpResponseRedirect(request.META['HTTP_REFERER'])
                else:
                    returnurl = request.build_absolute_uri(request.path)
                    returnurl = returnurl[:-len(request.path_info)]
                    return HttpResponseRedirect(returnurl)
        return f(request, *args, **kwargs)

    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    return wrap
