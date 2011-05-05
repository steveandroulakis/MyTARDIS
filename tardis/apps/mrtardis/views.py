#from django.conf import settings
from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import HttpResponseNotFound
from django.template import Context
from django.core.urlresolvers import reverse
from django.forms.formsets import formset_factory
from django.core.exceptions import ObjectDoesNotExist

from tardis.tardis_portal.models import Dataset
from tardis.tardis_portal.models import Dataset_File
from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.ajax import ajax_only

from tardis.apps.mrtardis.utils import test_hpc_connection
from tardis.apps.mrtardis.models import HPCUser
from tardis.apps.mrtardis.forms import DatasetDescriptionForm
from tardis.apps.mrtardis.forms import selectDSForm
from tardis.apps.mrtardis.forms import HPCSetupForm
from tardis.apps.mrtardis.forms import ParamForm
from tardis.apps.mrtardis.forms import RmsdForm
from tardis.apps.mrtardis.mrtask import MRtask

#from tardis.tardis_portal.logger import logger


@authz.experiment_access_required
@ajax_only
def index(request, experiment_id):
    """
    return start page for MR processing
    :param experiment_id: experiment id for experiment to be processed
    :type experiment_id: integer
    :returns: mrtardis/index.html template
    """
    hpc_error = False
    hpc_username = False
    try:
        hpc_username = test_hpc_connection(request.user)
    except Exception, e:
        hpc_error = e

    newDSForm = DatasetDescriptionForm()

    def getChoices(status):
        return [(mytask.dataset.id, mytask.dataset.description)
                for mytask in MRtask.getTaskList(experiment_id, status=status)]
    continueChoices = getChoices("unsubmitted")
    if continueChoices:
        continueForm = selectDSForm(continueChoices)
    else:
        continueForm = False
    viewFormChoices = getChoices("finished")
    if viewFormChoices:
        viewForm = selectDSForm(viewFormChoices)
    else:
        viewForm = False
    rerunFormChoices = getChoices("finished")
    if rerunFormChoices:
        rerunForm = selectDSForm(rerunFormChoices)
    else:
        rerunForm = False

    c = {'newDSForm': newDSForm,
         'continueForm': continueForm,
         'viewForm': viewForm,
         'rerunForm': rerunForm,
         'experiment_id': experiment_id,
         'hpc_username': hpc_username,
         'hpc_error': hpc_error,
         }
    return render_to_response('mrtardis/index.html',  Context(c))


@authz.experiment_access_required
@ajax_only
def test_user_setup(request, experiment_id):
    """
    tests whether user is setup for HPC processing and presents setup form
    if not
    :param experiment_id: id of experiment
    :type experiment_id: integer
    :returns: index page if tested ok and setup page mrtardis/usersetup.html
        if tested false
    """
    if request.method == 'POST':
        form = HPCSetupForm(request.POST)
        if form.is_valid():
            hpc_username = form.cleaned_data['hpc_username']
            try:
                thisHPCUser = HPCUser.objects.get(user=request.user)
            except ObjectDoesNotExist:
                thisHPCUser = HPCUser(user=request.user,
                                      hpc_username=hpc_username)
            thisHPCUser.hpc_username = hpc_username
            thisHPCUser.testedConnection = False
            thisHPCUser.save()
            return HttpResponseRedirect(reverse(
                    'tardis.apps.mrtardis.views.index',
                    args=[experiment_id]))
    else:
        form = HPCSetupForm()
    c = Context({
            'experiment_id': experiment_id,
            'HPCSetupForm': form,
            })
    return render_to_response("mrtardis/usersetup.html", c)


@authz.experiment_access_required
@ajax_only
def MRform(request, experiment_id):
    """
    setup of a new MR process overview
    :param experiment_id: experiment id of current experiment
    :type experiment_id: integer
    :returns: overview page corresponding to dataset submitted via POST
        using mrtardis/MRform.html template
    """
    #logger.debug(repr(request.POST))
    if 'action' not in request.POST:
        return HttpResponseNotFound('<h1>Wrong use of function</h1>')
    action = request.POST['action']
    if action == "newDS":
        newMRtask = MRtask(description=request.POST['description'],
                           experiment_id=experiment_id)
        newMRtask.set_status("unsubmitted")
        dataset = newMRtask.dataset
    elif action == "continue":
        dataset = Dataset.objects.get(pk=int(request.POST['dataset']))
        pass  # load existing parameters into form
    elif action == "rerunDS":
        olddataset = Dataset.objects.get(pk=request.POST['dataset'])
        oldMRtask = MRtask(dataset=olddataset)
        newMRtask = MRtask.clone(oldInstance=oldMRtask,
                                 newDescription=request.POST['description'])
        newMRtask.set_status("unsubmitted")
        dataset = newMRtask.dataset
        pass  # run new MR based on finished one
    if "message" in request.POST:
        message = request.POST['message']
    else:
        message = ""
    DSfileSelectChoices = [
        (otherDataset.id, otherDataset.description)
        for otherDataset in
        Dataset.objects.filter(experiment__pk=experiment_id)
        if otherDataset.id != dataset.id]
    datasetSelectForm = selectDSForm(DSfileSelectChoices)
    c = Context({
            'message': message,
            'dataset': dataset,
            'experiment_id': experiment_id,
            'datasetSelectForm': datasetSelectForm,
            })
    return render_to_response("mrtardis/MRform.html", c)


@authz.dataset_access_required
@ajax_only
def type_filtered_file_list(request, dataset_id):
    """
    show list of files in dataset_id filtered by POST['type']
    :param dataset_id: id of dataset to list files of
    :type dataset_id: integer
    :returns: template mrtardis/file_list.html
    """
    if 'type' not in request.POST:
        return HttpResponseNotFound('<h1>Wrong use of function</h1>')
    type = request.POST['type']
    filequeryset = Dataset_File.objects.filter(
        dataset__pk=dataset_id, filename__iendswith=type).order_by('filename')
    c = Context({
        'filequeryset': filequeryset,
        })
    return render_to_response('mrtardis/file_list.html', c)


@authz.dataset_access_required
@ajax_only
def add_pdb_files(request, dataset_id):
    """
    Extracts pdb files out of zips, adds them to the dataset and
    removes the zip. Then adds all pdb files to the MR parameters
    :param dataset_id: dataset in which to find zip files
    :type dataset_id: integer
    :returns: 'true' for ajax if successful.
    """
    thisMR = MRtask(dataset_id=dataset_id)
    thisMR.add_pdb_files()
    return HttpResponse("true")


@authz.dataset_access_required
@ajax_only
def parseMTZfile(request, dataset_id):
    """
    parse MTZ file to extract metadata
    :param dataset_id: dataset_id in which to look for MTZ file
    :type dataset_id: integer
    :returns: "true" or 404
    """
    thisMR = MRtask(dataset_id=dataset_id)
    if thisMR.add_mtz_file():
        return HttpResponse("true")
    else:
        return HttpResponseNotFound()


@authz.dataset_access_required
@ajax_only
def parForm(request, dataset_id):
    """
    shows/saves django form for MR parameters
    :param dataset_id: dataset to find parameters in
    :type dataset_id: integer
    :returns: template mrtardis/parform.html
    """
    contextdict = dict()
    thisMR = MRtask(dataset_id=dataset_id)
    f_choices = [(x.string_value, x.string_value)
                             for x in thisMR.get_params("f_values")]
    sigf_choices = [(x.string_value, x.string_value)
                    for x in thisMR.get_params("sigf_values")]
    try:
        sg_num = int(thisMR.get_param("spacegroup_mtz").string_value)
    except ObjectDoesNotExist:
        sg_num = None
    if request.method == 'POST':
        print request.POST
        paramForm = ParamForm(f_choices,
                              sigf_choices,
                              sg_num,
                              request.POST)
        rmsd_formfactory = formset_factory(RmsdForm)
        rmsdForms = rmsd_formfactory(request.POST)
        print rmsdForms.is_valid()
        print rmsdForms.errors
        print "is validated"
        if paramForm.is_valid() and rmsdForms.is_valid():
            thisMR.set_params_from_dict(paramForm.cleaned_data)
            thisMR.delete_params("rmsd")
            print rmsdForms.cleaned_data
            thisMR.set_param_list("rmsd",
                                  [r.cleaned_data['rmsd']
                                   for r in rmsdForms.forms
                                   if 'rmsd' in r.cleaned_data
                                   and r.cleaned_data['rmsd']])
            print thisMR.get_params("rmsd")
            contextdict["saved"] = "Saved successfully"
    formargs = thisMR.get_form_dictionary()
    if len(formargs["space_group"]) == 0:
        formargs["space_group"] = [sg_num]
    print formargs
    paramForm = ParamForm(
        f_choices,
        sigf_choices,
        sg_num,
        initial=formargs)
    rmsd_pars = thisMR.get_params("rmsd")
    rmsd_formfactory = formset_factory(RmsdForm, extra=1)
    rmsds = [{"rmsd": r.string_value} for r in rmsd_pars]
    rmsdForms = rmsd_formfactory(initial=rmsds)
    contextdict['paramForm'] = paramForm
    contextdict['rmsdForms'] = rmsdForms
    c = Context(contextdict)
    return render_to_response("mrtardis/parform.html", c)


@authz.dataset_access_required
@ajax_only
def runMR(request, dataset_id):
    """
    runs molecular replacement if all inputs are complete
    :param dataset_id: id of dataset to process
    :type dataset_id: integer
    :returns: run status in template mrtardis/running.html
    """
    print "runMR"
    thisMR = MRtask(dataset_id=dataset_id)
    jobids = thisMR.run(request)
    experiment_id = Dataset.objects.get(pk=dataset_id).experiment.id
    if not jobids:
        request.POST = dict()
        request.POST['action'] = "continue"
        request.POST['dataset'] = dataset_id
        request.POST['message'] = "Some parameters are missing"
        return access_error_avoider_function(request, dataset_id)
#        experiment_id = Dataset.objects.get(pk=dataset_id).experiment.id
#        return MRform(request, experiment_id)
    c = Context({
            'jobids': jobids,
            'experiment_id': experiment_id,
            })
    return render_to_response("mrtardis/running.html", c)


@authz.dataset_access_required
@ajax_only
def access_error_avoider_function(request, dataset_id):
    experiment_id = Dataset.objects.get(pk=dataset_id).experiment.id
    return MRform(request, experiment_id)


@authz.dataset_access_required
@ajax_only
def deleteFile(request, dataset_id):
    """
    delete a file completely, totally and utterly
    :returns: true or 404
    """
    if request.POST and "file_id" in request.POST:
        file_id = request.POST["file_id"]
        thisfile = Dataset_File.objects.get(pk=file_id)
        thisMR = MRtask(dataset_id=dataset_id)
        par = thisMR.get_by_value(thisfile.filename)
        print par
        if par != None:
            par.delete()
        thisfile.deleteCompletely()
        return HttpResponse("true")
    return HttpResponseNotFound()


@authz.experiment_access_required
@ajax_only
def runningJobs(request, experiment_id):
    MRlist = [thistask
              for thistask in
              MRtask.getTaskList(experiment_id, status="running")]
    jobids = [jobs.get_params("jobid") for jobs in MRlist]
    c = Context({
            'jobids': jobids,
            })
    return render_to_response("mrtardis/joblist.html", c)


def jobfinished(request, dataset_id):
    thisMR = MRtask(dataset_id=dataset_id)
    if 'jobid' not in request.GET and \
            thisMR.get_status(value=True) != "running":
        return HttpResponseNotFound()
    jobid = request.GET['jobid']
    for jid in thisMR.get_params("jobid", value=True):
        if jid == jobid:
            thisMR.new_param("jobidstatus", jobid + "-finished")
    thisMR.retrievalTrigger()
    return HttpResponse("true")


@authz.experiment_access_required
@ajax_only
def displayResults(request, experiment_id):
    """
    display results of POST submitted dataset in experiment_id
    :param experiment_id: experiment id containing results
    :type experiment_id: integer
    :returns: mrtardis/displayResults.html
    """
    if 'dataset' in request.POST:
        thisMR = MRtask(dataset_id=request.POST['dataset'])
    else:
        return HttpResponseNotFound()
    results = thisMR.parseResults()
    c = Context({
            'dataset': thisMR.dataset,
            'results': results,
            'experiment_id': experiment_id,
            'f_value': thisMR.get_param("f_value", value=True),
            'sigf_value': thisMR.get_param("sigf_value", value=True),
            'mol_weight': thisMR.get_param("mol_weight", value=True),
            'num_in_asym': thisMR.get_param("num_in_asym", value=True),
            'packing': thisMR.get_param("packing", value=True),
            'ensemble_number': thisMR.get_param("ensemble_number", value=True),
            })
    return render_to_response("mrtardis/displayResults.html", c)


@ajax_only
@authz.experiment_access_required
def loadDSFileList(request, experiment_id):
    if 'dataset_id' not in request.POST:
        return HttpResponseNotFound()
    files = Dataset_File.objects.filter(dataset__pk=request.POST['dataset_id'],
                                        filename__iendswith=".mtz")
    return render_to_response("mrtardis/DSfilelist.html", Context({
                'files': files,
                }))


@ajax_only
@authz.dataset_access_required
def addFile(request, dataset_id):
    import shutil
    from tardis.apps.mrtardis.utils import add_staged_file_to_dataset
    from django.conf import settings
    if 'file_id' not in request.POST:
        return HttpResponseNotFound()
    file_id = request.POST['file_id']
    file = Dataset_File.objects.get(pk=file_id)
    shutil.copy(file.get_absolute_filepath(), settings.STAGING_PATH)
    add_staged_file_to_dataset(file.filename, dataset_id, file.mimetype)
    return parseMTZfile(request, dataset_id=dataset_id)
