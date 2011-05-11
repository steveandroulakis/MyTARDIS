from django.core.exceptions import ObjectDoesNotExist

from tardis.tardis_portal.ParameterSetManager import ParameterSetManager
from tardis.tardis_portal.models import DatasetParameterSet
from tardis.tardis_portal.models import Dataset
from tardis.tardis_portal.models import Dataset_File
from tardis.tardis_portal.staging import get_full_staging_path


class Task(ParameterSetManager):
    schema_name = "http://localhost/task/generic"
    namespace = schema_name
    dataset = None
    DPS = None
    myHPC = None

    doNotCopyParams = ['TaskStatus',
                       'jobscript',  # many
                       'jobid',  # many
                       'jobidstatus',  # many
                       ]

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
        try:
            thisparameterset = DatasetParameterSet.objects.get(
                schema=self.get_schema(),
                dataset=self.dataset)
        except ObjectDoesNotExist:
            thisparameterset = DatasetParameterSet(
                schema=self.get_schema(),
                dataset=self.dataset)
            thisparameterset.save()
        super(Task, self).__init__(parameterset=thisparameterset)

    def get_status(self, value=False):
        try:
            return self.get_param("TaskStatus", value)
        except:
            return None

    def set_status(self, status):
        current_status = self.get_status(value=True)
        if current_status != status:
            self.set_param("TaskStatus", status, "Status of task")

    def get_files(self):
        return Dataset_File.objects.filter(dataset=self.dataset)

    def get_by_value(self, value):
        try:
            par = self.parameters.get(string_value=value)
        except ObjectDoesNotExist:
            try:
                par = self.parameters.get(numerical_value=value)
            except (ObjectDoesNotExist, ValueError):
                return None
        return par

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
    def clone(cls, oldInstance, newDescription, username):
        newInstance = cls(description=newDescription,
                          experiment_id=oldInstance.dataset.experiment.id)
        for param in oldInstance.parameters:
            if param.name.name not in cls.doNotCopyParams:
                if param.name.isNumeric():
                    value = param.numerical_value
                else:
                    value = param.string_value
                newInstance.new_param(param.name.name, value)
        import shutil
        import os
        for filename in oldInstance.get_params("uploaded_file", value=True):
            if filename[-8:] != ".jobfile":
                thisfile = Dataset_File.objects.get(
                    dataset=oldInstance.dataset,
                    filename=filename)
                shutil.copy(thisfile.get_absolute_filepath(),
                            get_full_staging_path(username))
                newfileurl = os.path.join(get_full_staging_path(username),
                                          filename)
                newDatafile = Dataset_File(
                    dataset=newInstance.dataset,
                    url=newfileurl,
                    protocol="staging",
                    mimetype=thisfile.mimetype,
                    )
                newDatafile.save()
        return newInstance
