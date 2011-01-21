from tardis.apps.mrtardis.models import myExperiment, Job, MrTUser
from django.contrib import admin

class JobAdmin(admin.ModelAdmin):
    list_display = ('submittime', 'jobstatus', 'hpcjobid', 'user')

admin.site.register(myExperiment)
admin.site.register(Job, JobAdmin)
admin.site.register(MrTUser)
