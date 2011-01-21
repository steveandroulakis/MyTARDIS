# Create your views here.
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template import Context
from django.conf import settings
import tardis.apps.mrtardis.utils as utils
from tardis.apps.mrtardis.forms import HPCSetupForm, MRFileSelect, MRForm
from tardis.apps.mrtardis.forms import RmsdForm
from tardis.apps.mrtardis.models import Job, MrTUser
from tardis.tardis_portal.forms import CreateDatasetCurrentExperiment
from tardis.tardis_portal.models import Experiment, Dataset
from tardis.tardis_portal.views import return_response_not_found
from tardis.tardis_portal.views import add_tree_to_dataset
from tardis.tardis_portal.logger import logger
from django.forms.formsets import formset_factory
from os import path
import tardis.apps.mrtardis.hpcjob as hpcjob

import uuid
import datetime
#import zipfile


def index(request, experiment_id):
    """return overview page for MR processing
    this page also contains javascript for moving between ajax inserts
    """
    hpc_connection_test = utils.test_hpc_connection(request.user)
    c = Context({
            'experiment_id': experiment_id,
            'untested': not hpc_connection_test,
            })
    return render_to_response('mrtardis/index.html', c)


def startMR(request, experiment_id):
    datasets = Dataset.objects.filter(experiment=experiment_id
                                      ).values_list('id', 'description')
    #logger.debug(repr(datasets))
    datasetForm = MRFileSelect(choices=datasets)
    createForm = CreateDatasetCurrentExperiment()
    #datasetForm.choices = datasets
    c = Context({
            'datasetForm': datasetForm,
            'createForm': createForm,
            'experiment_id': experiment_id,
            'upload_complete_url': '/apps/mrtardis/upload_complete/' +\
                experiment_id + "/",
            })
    return render_to_response('mrtardis/startmr.html', c)


def jobstatus(request, experiment_id):
    if not request.user.is_authenticated():
        return "Not logged in"
    try:
        #utils.update_job_status(experiment_id=experiment_id,
        #                        user_id=request.user.id)
        jobs = Job.objects.filter(experiment=Experiment.objects.get(
                pk=experiment_id))
        for job in jobs:
            job.updateStatus()
        datasets = jobs.values_list('dataset').distinct()
        logger.debug(repr(datasets))
        disparray = []
        for dataset in datasets:
            dataset = dataset[0]
            jobids = jobs.filter(dataset=dataset).values_list(
                'jobid').distinct()
            jobidarray = []
            for jobid in jobids:
                finished = True
                retrieved = True
                jobid = jobid[0]
                inttime = uuid.UUID(jobid).time
                submittime = datetime.datetime.fromtimestamp(
                    (inttime - 0x01b21dd213814000L)*100/1e9)
                thesejobs = jobs.filter(jobid=jobid)
                jobdataarray = []
                for job in thesejobs:
                    if job.jobstatus.strip() != "Finished":
                        finished = False
                    if job.jobstatus.strip() != "Retrieved":
                        retrieved = False
                    jobdata = {
                        'status': job.jobstatus,
                        'hpcjobid': job.hpcjobid,
                        'submittime': job.submittime,
                        }
                    jobdataarray.append(jobdata)
                jobiddict = {'jobid': jobid,
                             'joblist': jobdataarray,
                             'finished': finished,
                             'retrieved': retrieved,
                             'submittime': submittime.strftime(
                        "%d %b %Y, %H:%M:%S")}
                jobidarray.append(jobiddict)
            datasetdict = {'dataset': dataset,
                           'jobidlist': jobidarray}
            disparray.append(datasetdict)
            logger.debug(repr(disparray))
        c = Context({
                #'jobs': jobs,
                'disparray': disparray,
            })
    except Experiment.DoesNotExist:
        return return_response_not_found(request)

    return render_to_response('mrtardis/jobstatus.html', c)


def updateJobStatus(request):
    hpcjobid = request.GET['hpcjobid']
    job = Job.objects.get(hpcjobid=hpcjobid)
    if 'status' in request.GET:
        status = request.GET['status']
        job.jobstatus = status
        job.save()
    else:
        job.updateStatus()
    return HttpResponse("OK")


def test_user_setup(request):
    if request.method == 'POST':
        form = HPCSetupForm(request.POST)
        if form.is_valid():
            hpc_username = form.cleaned_data['hpc_username']
            newHPCUser = MrTUser(user=request.user,
                                 hpc_username=hpc_username)
            newHPCUser.save()
            return HttpResponseRedirect('/apps/mrtardis/test_user_setup')
    else:
        user = MrTUser.objects.filter(user=request.user)
        if len(user) == 0 or user[0].hpc_username == "":
            setup = False
            form = HPCSetupForm()
            user = None
        else:
            form = None
            user = user[0]
            setup = True
    c = Context({
            'authenticated': request.user.is_authenticated(),
            'user': user,
            'setup': setup,
            'form': form,
            })
    return render_to_response("mrtardis/usersetup.html", c)


# def upload_complete(request, experiment_id):
#     cont = {
#         'numberOfFiles': request.POST['filesUploaded'],
#         'bytes': request.POST['allBytesLoaded'],
#         'speed': request.POST['speed'],
#         'errorCount': request.POST['errorCount'],
#         }
#     c = Context(cont)
#     return render_to_response("mrtardis/upload_complete.html", c)

def upload_files(request):
    dataset_id = request.GET['dataset_id']

    mtzfile = utils.get_mtz_file(dataset_id)
    if mtzfile == None:
        has_mtz_file = False
        mtzfilename = ""
    else:
        has_mtz_file = True
        mtzfilename = mtzfile.filename

    pdbfilenames = utils.get_pdb_files(dataset_id)
    has_pdb_file = False
    if len(pdbfilenames) > 0:
        has_pdb_file = True
    else:
        has_pdb_file = False

    c = Context({
            'dataset_id': dataset_id,
            'dataset_name': Dataset.objects.get(
                id=dataset_id).description,
            'has_mtz_file': has_mtz_file,
            'has_pdb_file': has_pdb_file,
            'mtzfilename': mtzfilename,
            'pdbfilenames': pdbfilenames,
            })
    return render_to_response("mrtardis/upload_files.html", c)


#@login_required
def MRParams(request, dataset_id):
    """
    shows the parameter entry form,
    takes request.GET["dataset_id"] as input.
    """
#    return True
    #dataset_id = request.GET["dataset_id"]
    #getMTZfile
    mtz_file = utils.get_mtz_file(dataset_id)
    mtz_params = utils.processMTZ(mtz_file.get_storage_path())
    tochoice = lambda x: (x, x)
    f_choices = map(tochoice, mtz_params["f_value"])
    sigf_choices = map(tochoice, mtz_params["sigf_value"])
    sg_num = mtz_params["spacegroup"]
    pdbfilelist = utils.get_pdb_files(dataset_id)
    rmsd_formfactory = formset_factory(RmsdForm)
    if request.method == 'POST':
        logger.debug("we're POSTing")
        param_form = MRForm(f_choices,
                            sigf_choices,
                            sg_num,
                            request.POST)
        rmsd_formset = rmsd_formfactory(request.POST)
        logger.debug(repr(param_form.is_valid()) +
                     repr(rmsd_formset.is_valid()) +
                     repr(rmsd_formset.errors) +
                     repr(request.POST))
        if param_form.is_valid() and rmsd_formset.is_valid():
            hpcUsername = MrTUser.objects.get(user=request.user).hpc_username
            newJob = hpcjob.HPCJob(hpcUsername)
            jobparameters = {
                "f_value": param_form.cleaned_data['f_value'],
                "sigf_value": param_form.cleaned_data['sigf_value'],
                "num_in_asym": param_form.cleaned_data['num_in_asym'],
                "ensemble_number": param_form.cleaned_data['ensemble_number'],
                "packing": param_form.cleaned_data['packing'],
                "space_group": param_form.cleaned_data['space_group'],
                }
            if "sg_all" in param_form.cleaned_data:
                if param_form.cleaned_data["sg_all"] == True:
                    jobparameters["space_group"].append("ALL")
            jobparameters["rmsd"] = []
            for form in rmsd_formset.forms:
                jobparameters["rmsd"].append(form.cleaned_data['rmsd'])
            jobparameters["mol_weight"] = param_form.cleaned_data['mol_weight']
            filepaths = utils.get_pdb_files(dataset_id,
                         storagePaths=True) + [mtz_file.get_storage_path()]
            logger.debug("params: " + repr(jobparameters))
            logger.debug("files: " + repr(filepaths))
            newJob.stage(jobparameters, filepaths)
            newJob.submit()
            dataset = Dataset.objects.get(pk=dataset_id)
            newJob.dbSave(dataset.experiment_id, dataset,
                          request.user)
            c = Context({})
            return render_to_response("mrtardis/running_job.html", c)
    else:
        param_form = MRForm(f_choices=f_choices,
                            sigf_choices=sigf_choices,
                            sg_num=sg_num)
        rmsd_formset = rmsd_formfactory()
    c = Context({
            'dataset_id': dataset_id,
            'mtz_params': mtz_params,
            'rmsd_formset': rmsd_formset,
            'paramForm': param_form,
            'fileName': mtz_file.filename,
            'pdbfilelist': pdbfilelist,
            'spacegroupname': utils.sgNumNameTrans(number=sg_num),
            })
    return render_to_response("mrtardis/parameters.html", c)


def retrieveFromHPC(request):
    jobid = request.GET['jobid']
    hpc_username = MrTUser.objects.get(user=request.user).hpc_username
    myJob = hpcjob.HPCJob(hpc_username, jobid)
    jobs = Job.objects.filter(jobid=jobid)
    dataset = jobs[0].dataset
    destpath = settings.STAGING_PATH
    try:
        myJob.retrieve(destpath)
        del(myJob)
        srcpath = path.join(destpath, jobid)
        add_tree_to_dataset(dataset, srcpath)
        for job in jobs:
            job.jobstatus = "Retrieved"
            job.save()
        c = Context({'retrieved': True,
                     'error': ""})
    except IOError as e:
        # could mark differently, but it makes no difference to user and user interface...
        for job in jobs:
            job.jobstatus = "Retrieved"
            job.save()
        c = Context({'retrieved': False,
                     'error': e.strerror})
    return render_to_response("mrtardis/retrieve.html", c)
