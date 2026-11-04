from django.contrib import admin
from django.urls import include, path

from library.api import api

urlpatterns = [
    path("api/v1/", api.urls),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
]
