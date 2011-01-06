# Create your views here.
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import Context
#from django.conf import settings
from tardis.apps.mrtardis import utils
from tardis.apps.mrtardis.forms import HPCSetupForm, MRFileSelect, MRForm, RmsdForm
from tardis.apps.mrtardis.models import Job, MrTUser
from tardis.tardis_portal.forms import CreateDatasetCurrentExperiment
from tardis.tardis_portal.models import Experiment, Dataset, Dataset_File
from tardis.tardis_portal.views import return_response_not_found
from tardis.tardis_portal.logger import logger
from django.forms.formsets import formset_factory

import tardis.apps.mrtardis.backend.hpcjob as hpcjob

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
        utils.update_job_status(experiment_id=experiment_id,
                                user_id=request.user.id)
        jobs = Job.objects.filter(experiment_id=experiment_id)

        c = Context({
                'jobs': jobs,
            })
    except Experiment.DoesNotExist:
        return return_response_not_found(request)

    return render_to_response('mrtardis/jobstatus.html', c)


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


def MRParams(request):
    """
    shows the parameter entry form,
    takes request.GET["dataset_id"] as input.
    """
#    return True
    dataset_id = request.GET["dataset_id"]
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
        param_form = MRForm(request.POST)
        rmsd_formset = rmsd_formfactory(request.POST)
        if param_form.is_valid() and rmsd_formset.is_valid():
            newJob = hpcjob.HPCJob()
            jobparameters = {"f_value": param_form.f_value,
                             "sigf_value": param_form.sigf_value,
                             "num_in_asym": param_form.num_in_asym,
                             "ensemble_number": param_form.ensemble_number,
                             "packing": param_form.packing,
                             }
            jobparameters["rmsd"] = []
            for form in rmsd_formset:
                jobparameters["rmsd"].append(form.rmsd)
            sgarray = []
            for sg in param_form.space_group:
                if sg:
                    sgarray.append(sg.value)
            jobparameters["space_group"] = sgarray
            jobparameters["mol_weight"] = param_form.mol_weight

            filepaths = utils.get_pdb_files(dataset_id,
                         storagePaths=True) + [mtz_file.get_storage_path()]
            newJob.stage(jobparameters, filepaths)
            #newJob.submit()
            #newJob save to db
            c = Context({})
            return render_to_response("mrtardis/running_job.html", c)
    else:
        param_form = MRForm(f_choices=f_choices,
                            sigf_choices=sigf_choices,
                            sg_num=sg_num)
        rmsd_formset = rmsd_formfactory()
    c = Context({
            'mtz_params': mtz_params,
            'rmsd_formset': rmsd_formset,
            'paramForm': param_form,
            'fileName': mtz_file.filename,
            'pdbfilelist': pdbfilelist,
            'spacegroupname': utils.sgNumNameTrans(number=sg_num),
            })
    return render_to_response("mrtardis/parameters.html", c)
