from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from .auth import technical


class PrivacyMiddleware:
    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            request.path.startswith("/admin/")
            and request.user.is_authenticated
            and not technical(request.user)
        ):
            return HttpResponseForbidden("Admin restrito ao administrador.")
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/accounts/", "/admin/", "/colecao/")):
            response["Cache-Control"] = "no-store, private"
            response["X-Robots-Tag"] = "noindex, nofollow"
            response["Referrer-Policy"] = "same-origin"
        return response


class PublicOriginMiddleware:
    """Use the configured browser origin behind the production reverse proxy."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response
        self.origin = urlsplit(settings.APP_ORIGIN) if settings.APP_ORIGIN else None
        if self.origin and (
            self.origin.scheme != "https"
            or not self.origin.hostname
            or self.origin.path not in ("", "/")
            or self.origin.username
            or self.origin.password
            or self.origin.query
            or self.origin.fragment
        ):
            raise ImproperlyConfigured("APP_ORIGIN deve ser uma origem HTTPS válida.")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self.origin:
            request.get_host()  # Validate the received host before canonicalizing it.
            request.META["HTTP_HOST"] = self.origin.netloc
            request.META["wsgi.url_scheme"] = "https"
            request.META["SERVER_PORT"] = str(self.origin.port or 443)
        return self.get_response(request)
