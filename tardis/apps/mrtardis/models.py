from django.db import models
from django.contrib.auth.models import User

# import mytardis model/db access
from tardis.tardis_portal.models import Experiment, Dataset

import tardis.apps.mrtardis.backend.hpc as hpc
import tardis.apps.mrtardis.backend.secrets as secrets

# Create your models here.


class myExperiment(Experiment):
    """
    not used currently, may opt for a non-inheriting class later
    """
    question = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')


class MrTUser(models.Model):
    """
    holds hpc log in information for a user account.
    """
    user = models.ForeignKey(User, unique=True)
    hpc_username = models.CharField(max_length=20)
    testedConnection = models.BooleanField()

    def __unicode__(self):
        return self.user.username


class Job(models.Model):
    experiment = models.ForeignKey('tardis_portal.Experiment')
    dataset = models.ForeignKey('tardis_portal.Dataset')
    user = models.ForeignKey(MrTUser)
    jobid = models.CharField(max_length=80)
    hpcjobid = models.CharField(max_length=20)
    jobstatus = models.CharField(max_length=20)
    submittime = models.DateTimeField(auto_now_add=True)

    def updateStatus(self):
        if self.jobstatus == "Finished" or self.jobstatus == "Retrieved":
            return self.jobstatus
        myHPC = hpc.hpc(secrets.hostname, self.user.hpc_username,
                        key=secrets.privatekey,
                        keytype=secrets.keytype)
        (out, err) = myHPC.getOutputError(
            "source /etc/profile;qstat -j " + self.hpcjobid)
        if err.startswith("Following jobs do not exist"):
            status = "Finished"
        else:
            lines = out.split("\n")
            for line in lines:
                if line.startswith("Following jobs do not exist"):
                    status = "Finished"
                    break
                elif line.startswith("usage"):
                    status = "Running"
                    break
                else:
                    status = "Queuing"
        self.jobstatus = status
        self.save()
        return status


#class Choice(models.Model):
#    poll = models.ForeignKey(Poll)
#    choice = models.CharField(max_length=200)
#    votes = models.IntegerField()
