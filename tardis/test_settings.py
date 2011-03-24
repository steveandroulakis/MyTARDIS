import logging
from os import path


DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (('bob', 'bob@bobmail.com'), )

MANAGERS = ADMINS

# 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = ':memory:'
DATABASE_USER = 'x'  # Not used with sqlite3.
DATABASE_PASSWORD = ''  # Not used with sqlite3.
DATABASE_HOST = ''  # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''  # Set to empty string for default. Not used with sqlite3.

TIME_ZONE = 'Australia/Melbourne'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = True
ADMIN_MEDIA_PREFIX = '/media/'

MIDDLEWARE_CLASSES = ('django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tardis.tardis_portal.minidetector.Middleware',
    'tardis.tardis_portal.auth.AuthorizationMiddleware',
    'django.middleware.transaction.TransactionMiddleware')

ROOT_URLCONF = 'tardis.urls'

TEMPLATE_CONTEXT_PROCESSORS = ('django.core.context_processors.request',
                               'django.core.context_processors.auth',
                               'django.core.context_processors.debug',
                               'django.core.context_processors.i18n')


TEMPLATE_DIRS = ['.']

# LDAP configuration
LDAP_ENABLE = False

DISABLE_TRANSACTION_MANAGEMENT = False

STATIC_DOC_ROOT = path.join(path.dirname(__file__),
                               'tardis_portal/site_media').replace('\\', '/')

ADMIN_MEDIA_STATIC_DOC_ROOT = ''

FILE_STORE_PATH = path.abspath(path.join(path.dirname(__file__),
                                               '../var/store/')).replace('\\', '/')
STAGING_PATH = path.abspath(path.join(path.dirname(__file__),
                                            "../var/staging/")).replace('\\', '/')

HANDLEURL = ''

MEDIA_ROOT = STATIC_DOC_ROOT

MEDIA_URL = '/site_media/'

#set to empty tuple () for no apps
#TARDIS_APPS = ('mrtardis', )
TARDIS_APPS = ()
TARDIS_APP_ROOT = 'tardis.apps'

if TARDIS_APPS:
    apps = tuple(["%s.%s" % (TARDIS_APP_ROOT, app) for app in TARDIS_APPS])
else:
    apps = ()

INSTALLED_APPS = (
    'django_extensions',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'tardis.tardis_portal',
    'registration',
    'tardis.tardis_portal.templatetags',
    'tardis.apps.equipment',
    'django_nose',
    'south'
    ) + apps

USER_PROVIDERS = ('tardis.tardis_portal.auth.localdb_auth.DjangoUserProvider',)
GROUP_PROVIDERS = ('tardis.tardis_portal.auth.localdb_auth.DjangoGroupProvider',
                   'tardis.tardis_portal.auth.ip_auth.IPGroupProvider',)

AUTH_PROVIDERS = (
    ('localdb', 'Local DB', 'tardis.tardis_portal.auth.localdb_auth.DjangoAuthBackend'),
    ('vbl', 'VBL', 'tardis.tardis_portal.tests.mock_vbl_auth.MockBackend'),
    )


VBLSTORAGEGATEWAY = \
'https://vbl.synchrotron.org.au/StorageGateway/VBLStorageGateway.wsdl'

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

LOG_FILENAME = None

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# logging levels are: DEBUG, INFO, WARN, ERROR, CRITICAL
LOG_LEVEL = logging.ERROR
