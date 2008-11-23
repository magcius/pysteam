from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    
    (r'^$', 'steamwhore.steamapps.views.index')
    (r'^cdr/', include('steamwhore.cdr.urls')),
    (r'^app/', include('steamwhore.steamapps.urls')),
    
    # Uncomment the next line to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line for to enable the admin:
    (r'^admin/(.*)', admin.site.root)
)
