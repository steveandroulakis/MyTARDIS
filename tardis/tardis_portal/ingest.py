from django.db import transaction
from django.http import HttpResponse
from django.template import Context
from os import path
from tardis import settings
from tardis.tardis_portal.ProcessExperiment import ProcessExperiment
from tardis.tardis_portal.auth import auth_service
from tardis.tardis_portal.auth.localdb_auth import auth_key as localdb_auth_key, \
    django_user
from tardis.tardis_portal.forms import RegisterExperimentForm
from tardis.tardis_portal.metsparser import parseMets
from tardis.tardis_portal.models import Experiment, RegistrationStatus, \
    ExperimentACL
from tardis.tardis_portal.shortcuts import render_response_index, \
    return_response_error
from tardis.tardis_portal.views import getNewSearchDatafileSelectionForm
from urllib import urlencode, urlopen
from xml.sax._exceptions import SAXParseException
import logging

""" ingest.py
    Receive automatic ingest requests, which include a METS file, and data file
    source location. Errors, warnings and information encountered during processing
    is written to the RegistrationStatus table.
"""    

# globals
logger = logging.getLogger(__name__)
experiment = None
current_action='Ingest Received' # updated as actions take place

# TODO removed username from arguments
@transaction.commit_on_success
def _registerExperimentDocument(filename, created_by, expid=None,
                                owners=[], username=None):
    '''
    Register the experiment document and return the experiment id.

    :param filename: path of the document to parse (METS or notMETS)
    :type filename: string
    :param created_by: a User instance
    :type created_by: :py:class:`django.contrib.auth.models.User`
    :param expid: the experiment ID to use
    :type expid: int
    :param owners: a list of email addresses of users who 'own' the experiment, as registered in the local db
    :type owner: list
    :param username: **UNUSED**
    :rtype: int
    '''

    global current_action, experiment
    current_action = "Ingest Processing"

    f = open(filename)
    firstline = f.readline()
    f.close()

    if firstline.startswith('<experiment'):
        logger.debug('processing simple xml')
        processExperiment = ProcessExperiment()
        eid = processExperiment.process_simple(filename, created_by, expid)

    else:
        logger.debug('processing METS')
        try:
            eid = parseMets(filename, created_by, expid)
        except SAXParseException:
            add_status(status=RegistrationStatus.ERROR,
                       message="Processing METS failed: Document isn't XML, or well formed.<br> (%s)" % filename,
                       exception=True)

    auth_key = ''
    try:
        auth_key = settings.DEFAULT_AUTH
    except AttributeError:
        add_status(status=RegistrationStatus.ERROR,
                   message='No default authentication for experiment ownership set (settings.DEFAULT_AUTH)')

    if auth_key:
        for owner in owners:
            # for each PI
            if owner:
                user = auth_service.getUser({'pluginname': auth_key,
                                             'id': owner})
                # if exist, create ACL
                if user:
                    logger.debug('registering owner: ' + owner)

                    acl = ExperimentACL(experiment=experiment,
                                        pluginId=django_user,
                                        entityId=str(user.id),
                                        canRead=True,
                                        canWrite=True,
                                        canDelete=True,
                                        isOwner=True,
                                        aclOwnershipType=ExperimentACL.OWNER_OWNED)
                    acl.save()

                else:
                    # Make this a critical error
                    add_status(status=RegistrationStatus.ERROR,
                               message="Can't create ACL for experiment: no user found for owner '%s'. Auth_key: %s.: " %
                                     (owner, auth_key,))

    return experiment.id # unneeded?



def send_retry_response(request, form, status):
    '''Returns the form te be filled out again'''

    c = Context({
        'form': form,
        'status': status,
        'subtitle': 'Register Experiment',
        'searchDatafileSelectionForm': getNewSearchDatafileSelectionForm()})
    return HttpResponse(render_response_index(request,
                        'tardis_portal/register_experiment.html', c))    

def add_status(status, message, exception=False):
        if exception:
            import traceback
            message = message + '<div class="traceback"/>' +  traceback.format_exc().replace("\n", "<br/>") + "</div>"  
        rs = RegistrationStatus(action=current_action,
                                status=status,
                                message=message,
                                experiment=experiment,
                                )
        rs.save()
        appropriate_logger = { 
                      RegistrationStatus.PASS: logger.info,
                      RegistrationStatus.WARNING: logger.warning,
                      RegistrationStatus.ERROR: logger.error,
                      }[status]
        #if exception:
        #    appropriate_logger = logger.exception # this logger prints exception information too.
        #message="" + message
        if experiment:
            appropriate_logger("#%d: %s" % (experiment.id, message,))
        else:
            appropriate_logger(message)
            global idless_statuses
            idless_statuses.append(rs.id) # keep track of statuses before we got an experiment, for later

def authentication_ok(user):
    if user and user.is_active:
        return True
    if not user:
        fail_message = "Authentication failure: <br/>" \
            "User does not exist, or password incorrect.<br/>" \
            "Debug: <samp>%s</samp>" % debug_POST
    else:
        # not user.is_active:
        fail_message = "Authorisation failure: <br/>" \
            "User credentials passed, but user is not active<br/>" \
            "Debug: <samp>%s</samp>" % debug_POST

    add_status(RegistrationStatus.ERROR, fail_message)
    return False

def check_owner(owners):
    global debug_POST
    owner_string = ""
    for owner in owners:
        owner_string = owner_string + owner
        debug_POST2 = debug_POST + "owner: " + owner + "<br/>"

    if len(owner_string) == 0:
        fail_message = "No owners submitted with ingest <br/>" \
            "Debug: " + str(debug_POST2)
        add_status(status=RegistrationStatus.WARNING,
                   message=fail_message)
    


def do_file_transfer(file_transfer_url, originid, request):
    data = urlencode({
                      'originid': str(originid),
                      'eid': str(experiment.id),
                      'site_settings_url':
                        request.build_absolute_uri(
                        '/site-settings.xml/'),
                      })
    try:
        
        logger.debug("Starting file transfer to %s" % file_transfer_url)
        transfer_result = urlopen(file_transfer_url, data)
        logger.info('=== file-transfer request submitted to %s, result %d'
                    % (file_transfer_url, transfer_result.code))
        
        msg="Contacting " + file_transfer_url +  \
            " returned HTTP code: " + \
            str(transfer_result.code)
                 
        if transfer_result.code != 200:
            add_status(status=RegistrationStatus.ERROR,
                       message=msg)
        else:
            add_status(status=RegistrationStatus.PASS,
                       message=msg)

    except:
        msg = "Contacting %s failed with this data: <br/><samp> %s</samp>" % (file_transfer_url, data,)

        add_status(status=RegistrationStatus.ERROR,
                   message=msg, exception=True)
        logger.exception('=== file-transfer request to %s FAILED!'
                         % file_transfer_url)

    
    # end do_file_transfer


# web service
def register_experiment_ws_xmldata(request):
    ''' Web-service mechanism for registering an experiment, and triggering a corresponding file transfer.
        Although intended to be called as a web service, it actually works fine as a normal form, at 
        /experiment/register '''

    # --- start function body ---
    global experiment, idless_statuses, current_action, debug_POST
    experiment=None
    idless_statuses=[]
    logger.debug("Starting ingest process")
    # Check that we have received a form, abort otherwise
    try:
        if request.method != 'POST':
            # Happens when just viewing the form
            form = RegisterExperimentForm()  # An unbound form
            return send_retry_response(request, form, '')
        
        logger.info("Starting experiment ingest processing")
        
        from datetime import datetime
    
        temp_title = "Ingest Received: " + \
                     datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
    
        # A form bound to the POST data
        form = RegisterExperimentForm(request.POST, request.FILES)
        
        # Check that the form is filled out, abort otherwise.
        if not form.is_valid():  
            fail_message = "Form validation failure: <br/>" \
                "Form Errors: " + str(form.errors) + "<br/>" \
    
            try:
                add_status(RegistrationStatus.ERROR, fail_message)
                return send_retry_response(request, form, '')
            except Exception as ex:
                logger.error("Really an exception %s" % ex)
       
        logger.debug("Form validation: ok")
        xmldata = request.FILES['xmldata']
        xmldata_meta = xmldata.name
        username = form.cleaned_data['username']
        originid = form.cleaned_data['originid']
        from_url = form.cleaned_data['from_url']
        owners = request.POST.getlist('experiment_owner')

        debug_POST = "username: " + username + "<br/>" \
            "xmldata: " + xmldata_meta + "<br/>" \
            "originid: " + originid + "<br/>" \
            "from_url: " + from_url + "<br/>" \
    
    
        user = auth_service.authenticate(request=request,
                       authMethod=localdb_auth_key)
        
        # Check user is authenticated, and user information is present, abort otherwise
        if not authentication_ok(user):
            return return_response_error(request)
        logger.debug("User authentication: ok")
        # Basic checks have passed, so create the experiment.
        global experiment
        experiment = Experiment(title=temp_title, approved=True, created_by=user,)
        experiment.save()
        
        # Now update old registration statuses with the new experiment number.
        
        for oldstatus in idless_statuses:
            rs = RegistrationStatus.objects.get(pk=oldstatus)
            rs.experiment=experiment
            rs.save()
    
        # If no owner provided, record a warning.
        check_owner(owners)        

        # Write the submitted XML file to disk
        filename = path.join(experiment.get_or_create_directory(),
                             'mets_upload.xml')
    
        f = open(filename, 'wb+')
        for chunk in xmldata.chunks():
            f.write(chunk)
        f.close()
    
        add_status(status=RegistrationStatus.PASS,
                   message="Ingest Successfully Received")
    
        # Now process METS/XML file
        current_action = "Ingest Processing"
        try:
            _registerExperimentDocument(filename=filename,
                                        created_by=user,
                                        expid=experiment.id,
                                        owners=owners,
                                        username=username)
        except:
            add_status(status=RegistrationStatus.ERROR,
                       message="METS metadata ingest failed",
                       exception=True)
            return return_response_error(request)
    
        add_status(status=RegistrationStatus.PASS,
                   message="Ingest Successfully Processed")
    
        if from_url:
        # form is ok, METS file ingested ok, and they also specified a file to transer
            current_action = 'File Transfer Request'
            logger.debug("transferring file")
            file_transfer_url = from_url + '/file_transfer/'
            do_file_transfer(file_transfer_url, originid, request) 
    
        # Success: respond with just the ID of the newly created and processed experiment.
        response = HttpResponse(str(experiment.id), status=200)
        response['Location'] = request.build_absolute_uri(
            '/experiment/view/' + str(experiment.id))
        return response
    except Exception as ex:
        add_status(RegistrationStatus.ERROR, "Unhandled exception in METS ingest.", exception=True)

