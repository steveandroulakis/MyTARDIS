from celery.task import Task
from celery.registry import tasks
from tardis.tardis_portal.forms import ExperimentForm

class SaveExperiment(Task):
    def run(self, post, files, **kwargs):
        
        ef = ExperimentForm(post, files)
        
        if ef.is_valid():
            ef.save(commit=False)

tasks.register(SaveExperiment)