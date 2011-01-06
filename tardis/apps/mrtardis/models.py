from django.db import models
from django.contrib.auth.models import User

# import mytardis model/db access
from tardis.tardis_portal.models import Experiment
# Create your models here.


class myExperiment(Experiment):
    """
    not used currently, may opt for a non-inheriting class later
    """
    question = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')


class Job(models.Model):
    experiment_id = models.ForeignKey('tardis_portal.Experiment')
    user = models.ManyToManyField(User)
    jobid = models.CharField(max_length=80)
    hpcjobid = models.CharField(max_length=20)
    jobstatus = models.CharField(max_length=20)


class MrTUser(models.Model):
    """
    holds hpc log in information for a user account.
    """
    user = models.ForeignKey(User, unique=True)
    hpc_username = models.CharField(max_length=20)
    testedConnection = models.BooleanField()

    def __unicode__(self):
        return self.user.username


#class Choice(models.Model):
#    poll = models.ForeignKey(Poll)
#    choice = models.CharField(max_length=200)
#    votes = models.IntegerField()
