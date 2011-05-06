import uuid

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from tardis.tardis_portal.ParameterSetManager import ParameterSetManager
from tardis.tardis_portal.models import DatasetParameterSet
from tardis.tardis_portal.models import Dataset
from tardis.tardis_portal.models import Dataset_File
from tardis.apps.mrtardis.hpc import HPC
from tardis.apps.mrtardis.utils import add_staged_file_to_dataset


class Task(ParameterSetManager):
    schema_name = "http://localhost/task/generic"
    dataset = None
    DPS = None
    myHPC = None

    def __init__(self, dataset=None, dataset_id=None,
                 description="", experiment_id=None):
        """
        instantiate new task or existing task
        :param dataset: optional parameter to instanciate task from
          metadata, will be tested for completeness and copied into
          new task if complete
        :type dataset: Dataset
        """
        if dataset:
            self.dataset = dataset
        elif dataset_id:
            self.dataset = Dataset.objects.get(pk=dataset_id)
        else:
            if description == "":
                raise TypeError("No description given")
            if not experiment_id:
                raise TypeError("No experiment id given")
            self.dataset = Dataset()
            self.dataset.experiment_id = experiment_id
            self.dataset.description = description
            self.dataset.save()
        super(Task, self).__init__(parentObject=self.dataset,
                                   schema=self.schema_name)

    def get_status(self, value=False):
        try:
            return self.get_param("TaskStatus", value)
        except:
            return None

    def set_status(self, status):
        current_status = self.get_status(value=True)
        if current_status != status:
            self.set_param("TaskStatus", status, "Status of task")

    def get_hpc_dir(self):
        try:
            dir = self.get_param("hpc_directory", value=True)
        except ObjectDoesNotExist:
            dir = "mytardis-task/%s/%s" % (self.schema_name.split("/")[-1],
                                           str(uuid.uuid1()))
            self.set_param("hpc_directory", dir)
        return dir

    def get_files(self):
        return Dataset_File.objects.filter(dataset=self.dataset)

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

    def get_by_value(self, value):
        try:
            par = self.parameters.get(string_value=value)
        except ObjectDoesNotExist:
            try:
                par = self.parameters.get(numerical_value=value)
            except (ObjectDoesNotExist, ValueError):
                return None
        return par

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
        excludefiles = self.get_params("uploaded_file", value=True)
        hpclink = self.connectToHPC(location, hpc_username)
        newfiles = hpclink.download(self.get_hpc_dir(),
                                    settings.STAGING_PATH,
                                    excludefiles=excludefiles)
        for newfile in newfiles:
            add_staged_file_to_dataset(newfile, self.dataset.id)
        hpclink.rmtree(self.get_hpc_dir())
        self.set_status("finished")
        return True

    def parseResults(self):
        """
        stub, to be overridden by subclass if needed
        """
        pass

    def sendMail(self, toName, toAddress, returnURI,
                 type="JobComplete"):
        from django.core.mail import send_mail
        subject = "Your Task %s is complete" % self.dataset.description
        message = "Dear %s,\n" % toName
        message += "\nYour job %s is complete " % self.dataset.description
        message += "and the results are stored in myTardis.\n"
        message += "HOSTNAME\n"
        message += "\nBest regards,\nYour myTardis\n"
        send_mail(subject, message, 'mytardis@example.com',
                  [toAddress])

    def check_status_on_hpc(self):
        jobids = self.get_params("jobid")

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

    @classmethod
    def getTaskList(cls, experiment_id, status="any"):
        """
        Get list of all tasks or specify the type as string
        :param experiment: the experiment that is being searched for tasks
        :type experiment: Experiment
        :param taskclass: the subclass of Task
        :type type: string
        yields DatasetParameterSet
        """
        DPSs = DatasetParameterSet.objects.filter(
            schema__namespace__startswith=cls.schema_name,
            dataset__experiment__pk=experiment_id)
        tasklist = [cls(dataset=dps.dataset) for dps in DPSs]
        if status == "any":
            return tasklist
        filteredlist = []
        for thistask in tasklist:
            try:
                if thistask.get_status(value=True) == status:
                    filteredlist.append(thistask)
            except ObjectDoesNotExist:
                continue
        return filteredlist

    @classmethod
    def clone(cls, oldInstance, newDescription):
        newInstance = cls(description=newDescription,
                          experiment_id=oldInstance.dataset.experiment.id)
        doNotCopyParams = ['TaskStatus',
                           'readyToSubmit',
                           'jobscript',  # many
                           'hpc_directory',
                           'uploaded_file',  # many
                           'jobid',  # many
                           'jobidstatus',  # many
                           ]
        for param in oldInstance.parameters:
            if param.name.name not in doNotCopyParams:
                if param.name.isNumeric():
                    value = param.numerical_value
                else:
                    value = param.string_value
                newInstance.new_param(param.name.name, value)
        import shutil
        for filename in oldInstance.get_params("uploaded_file", value=True):
            print filename[-8:]
            if filename[-8:] != ".jobfile":
                print 'yes'
                print filename
                thisfile = Dataset_File.objects.get(
                    dataset=oldInstance.dataset,
                    filename=filename)
                print thisfile
                shutil.copy(thisfile.get_absolute_filepath(),
                            settings.STAGING_PATH)
                add_staged_file_to_dataset(filename, newInstance.dataset.id,
                                           thisfile.mimetype)
                pass  # copy file to new dataset
        return newInstance
