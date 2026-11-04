from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.http import HttpRequest


class JulibAdminSite(AdminSite):
    site_header = "Julib · Administração"

    def has_permission(self, request: HttpRequest) -> bool:
        from .auth import technical

        return technical(request.user)


class JulibAdminConfig(AdminConfig):
    default_site = "library.admin_site.JulibAdminSite"
