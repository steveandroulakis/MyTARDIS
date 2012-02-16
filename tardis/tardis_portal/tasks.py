from celery.task import Task
from celery.registry import tasks
from tardis.tardis_portal.forms import ExperimentForm
from django.core.mail import send_mail

class SaveExperiment(Task):
    def run(self, post, files, user, instance=None, extra=0, **kwargs):
        
        ef = None
        if not instance: # new
            ef = ExperimentForm(post, files)
            if ef.is_valid():
                full_experiment = ef.save(commit=False)            

                # group/owner assignment stuff, soon to be replaced

                full_experiment.create_default_ACL(user)                
                
                send_mail('Experiment Creation Successful', 'Yay \o/ ' + str(full_experiment['experiment'].id), 'steve.androulakis@gmail.com',
                    ['steve.androulakis@gmail.com'], fail_silently=False)
        else:
            ef = ExperimentForm(post, files, instance=instance, extra=extra)
            if ef.is_valid():
                full_experiment = ef.save(commit=False)
                
                send_mail('Experiment Save Successful', 'Woo \o/ ' + str(full_experiment['experiment'].id), 'steve.androulakis@gmail.com',
                    ['steve.androulakis@gmail.com'], fail_silently=False)

tasks.register(SaveExperiment)