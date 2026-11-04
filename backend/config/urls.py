from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponseForbidden
from library.api import api
from library.auth import technical

original_permission = admin.site.has_permission
admin.site.has_permission = lambda request: technical(request.user)
original_admin = admin.site.index

def admin_index(request, *args, **kwargs):
    if request.user.is_authenticated and not technical(request.user):
        return HttpResponseForbidden('Admin restrito.')
    return original_admin(request, *args, **kwargs)

admin.site.index = admin_index
urlpatterns = [path('api/v1/', api.urls), path('admin/', admin.site.urls), path('accounts/', include('allauth.urls'))]
