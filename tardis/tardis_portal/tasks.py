from celery.task import Task
from celery.registry import tasks
from tardis.tardis_portal.forms import ExperimentForm
from django.conf import settings
from django.core.mail import send_mail

import logging
logger = logging.getLogger(__name__)

class SendMail(Task):
    def run(self, subject, body, to, **kwargs):
        
        try:
            logger.debug('Sending mail to ' + str(to))
            send_mail(subject, body, settings.EMAIL_HOST_USER,
                to, fail_silently=False)
        except:
            logger.error('Email sending failed to ' + str(to))
            # can't really notify by email of email settings failure, hey

tasks.register(SendMail)

class SaveExperiment(Task):
    def run(self, post, files, user, instance=None, extra=0, **kwargs):
        
        try:
            ef = None
            if not instance: # new
                ef = ExperimentForm(post, files)
                if ef.is_valid():
                    full_experiment = ef.save(commit=False)
                    
                    # group/owner assignment stuff, soon to be replaced
                    
                    full_experiment.create_default_ACL(user)
                    
                    subject = 'Experiment Creation Successful'
                    body = 'Yay \o/ ' + str(full_experiment['experiment'].id)
                    to = [user.email,]
                    
                    SendMail.delay(subject=subject,
                        body=body,
                        to=to)
                else:
                    # todo raise specific exception
                    raise Exception("Form incomplete. Please resubmit");
            
            else:
                ef = ExperimentForm(post, files, instance=instance, extra=extra)
                if ef.is_valid():
                    full_experiment = ef.save(commit=False)
                    
                    subject = 'Experiment Save Successful'
                    body = 'Woo \o/ ' + str(full_experiment['experiment'].id)
                    to = [user.email,]
                    
                    SendMail.delay(subject=subject,
                        body=body,
                        to=to)
                else:
                    # todo raise specific exception
                    raise Exception("Form incomplete. Please resubmit");
        except Exception as e:
            logger.error('User: ' + user.username + ' - ' \
                + str(type(e)) + ': ' + str(e))
            
            subject = 'Experiment Save Failed'
            body = str(type(e)) + ': ' + str(e)
            to = [user.email,]
            
            SendMail.delay(subject=subject,
                body=body,
                to=to)

tasks.register(SaveExperiment)