import uuid

from django.core.exceptions import ObjectDoesNotExist

from tardis.tardis_portal.task import Task
from tardis.tardis_portal.staging import get_full_staging_path
from tardis.apps.mrtardis.hpc import HPC
from tardis.apps.mrtardis.models import HPCUser
from tardis.apps.mrtardis.utils import add_staged_file_to_dataset


class HPCTask(Task):
    schema_name = "http://localhost/task/hpctask"
    namespace = schema_name
    myHPC = None

    doNotCopyParams = ['TaskStatus',
                       'readyToSubmit',
                       'jobscript',  # many
                       'hpc_directory',
                       'uploaded_file',  # many
                       'jobid',  # many
                       'jobidstatus',  # many
                       ]

    def get_hpc_dir(self):
        try:
            dir = self.get_param("hpc_directory", value=True)
        except ObjectDoesNotExist:
            dir = "mytardis-task/%s/%s" % (self.schema_name.split("/")[-1],
                                           str(uuid.uuid1()))
            self.set_param("hpc_directory", dir)
        return dir

    def stageToHPC(self, username, location="msg"):
        hpclink = self.connectToHPC(location, username)
        hpcdir = self.get_hpc_dir()
        for upfile in self.get_files():
            upfilename = upfile.get_absolute_filepath()
            hpcfilename = hpcdir + "/" + upfile.filename
            hpclink.upload(upfilename, hpcfilename)
            self.new_param("uploaded_file", upfile.filename)

    def run_staged_task(self, username, location="msg"):
        self.set_param("hpc_username", username)
        jobscripts = self.get_params("jobscript", value=True)
        if location == "msg":
            submitCommand = "source /etc/profile; cd " +\
                self.get_hpc_dir() + "; qsub"
        commandlist = ["%s %s" % (submitCommand, jobscript)
                   for jobscript in jobscripts]
        returnstrings = self.connectToHPC(
            location, username).runCommands(commandlist)
        return [Task.extractJobID(retstring[0]) for retstring in returnstrings]

    def connectToHPC(self, location, username):
        if not self.myHPC:
            self.myHPC = HPC(location, username)
        return self.myHPC

    def retrievalTrigger(self):
        statuses = self.get_params("jobidstatus", value=True)
        for jid in self.get_params("jobid", value=True):
            if jid + "-finished" not in statuses:
                return False
        self.set_status("readyToRetrieve")
        self.retrieveFromHPC()
        return True

    def retrieveFromHPC(self, location="msg"):
        if self.get_status(value=True) != "readyToRetrieve":
            return False
        hpc_username = self.get_param("hpc_username", value=True)
        user = HPCUser.objects.get(hpc_username=hpc_username)
        excludefiles = self.get_params("uploaded_file", value=True)
        hpclink = self.connectToHPC(location, hpc_username)
        newfiles = hpclink.download(self.get_hpc_dir(),
                                    get_full_staging_path(user.user.username),
                                    excludefiles=excludefiles)
        for newfile in newfiles:
            add_staged_file_to_dataset(newfile, self.dataset.id,
                                       user.user.username)
        hpclink.rmtree(self.get_hpc_dir())
        self.set_status("finished")
        return True

    def check_status_on_hpc(self):
        jobids = self.get_params("jobid")
        print jobids

    @staticmethod
    def extractJobID(inputstring):
        import re
        # from txt2re.com
        re1 = '.*?'  # Non-greedy match on filler
        re2 = '(\\d+)'  # Integer Number 1

        rg = re.compile(re1 + re2, re.IGNORECASE | re.DOTALL)
        m = rg.search(inputstring)
        if m:
            int1 = m.group(1)
            return int1
        return False
