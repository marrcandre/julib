from typing import Any

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
