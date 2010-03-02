from django.contrib import admin
from steamwhore.cdr import models

admin.site.register(models.CDR)
admin.site.register(models.Application)
admin.site.register(models.ApplicationFilesystemRecord)
admin.site.register(models.ApplicationLaunchOptionRecord)
admin.site.register(models.ApplicationUserDefinedRecord)
admin.site.register(models.ApplicationVersionLaunchRecord)
admin.site.register(models.ApplicationVersionRecord)