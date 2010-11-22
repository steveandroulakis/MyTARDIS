from django.db import models
from django.contrib.auth.models import User

# import mytardis model/db access
from tardis.tardis_portal.models import Experiment
# Create your models here.


class myExperiment(Experiment):
    question = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')


class Job(models.Model):
    experiment_id = models.ForeignKey('tardis_portal.Experiment')
    username = models.CharField(max_length=20)
    jobid = models.CharField(max_length=80, primary_key=True)
    jobstatus = models.CharField(max_length=20)


class MrTUser(models.Model):
    user = models.ForeignKey(User, unique=True)
    hpc_username = models.CharField(max_length=20)
    testedConnection = models.BooleanField()

    def __unicode__(self):
        return self.user.username


#class Choice(models.Model):
#    poll = models.ForeignKey(Poll)
#    choice = models.CharField(max_length=200)
#    votes = models.IntegerField()
