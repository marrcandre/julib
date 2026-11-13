from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponseForbidden
from ninja.errors import HttpError
from ninja.security import SessionAuth

from .models import Library, Membership, User


def permitted(user: User | AnonymousUser) -> bool:
    return (
        isinstance(user, User) and user.is_active and user.email.lower() in settings.ALLOWED_EMAILS
    )


def technical(user: User | AnonymousUser) -> bool:
    return (
        isinstance(user, User)
        and permitted(user)
        and bool(settings.ADMIN_EMAIL)
        and user.email.lower() == settings.ADMIN_EMAIL
        and user.is_staff
    )


class AllowedSession(SessionAuth):
    def authenticate(self, request: HttpRequest, key: str | None) -> User | None:
        user = super().authenticate(request, key)
        if user and not permitted(user):
            raise HttpError(403, "Conta sem autorização.")
        return user


def require_membership(request: HttpRequest) -> Membership:
    if not isinstance(request.user, User) or not permitted(request.user):
        raise HttpError(403, "Conta sem autorização.")
    memberships = Membership.objects.filter(user=request.user).select_related("library")
    library_id = request.headers.get("X-Library-ID")
    if library_id is None:
        selected_memberships = list(memberships[:2])
        if len(selected_memberships) == 1:
            return selected_memberships[0]
        if not selected_memberships:
            raise HttpError(403, "Conta sem biblioteca autorizada.")
        raise HttpError(403, "Selecione uma biblioteca para continuar.")
    if not library_id.isdecimal() or int(library_id) < 1:
        raise HttpError(403, "Biblioteca não autorizada.")
    try:
        return memberships.get(library_id=int(library_id))
    except Membership.DoesNotExist:
        raise HttpError(403, "Biblioteca não autorizada.") from None


def require_library(request: HttpRequest) -> Library:
    return require_membership(request).library


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False


class GoogleAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: Any) -> bool:
        return self._allowed(sociallogin)

    def _allowed(self, sociallogin: Any) -> bool:
        return sociallogin.account.provider == "google" and any(
            e.verified and e.email.lower() in settings.ALLOWED_EMAILS
            for e in sociallogin.email_addresses
        )

    def pre_social_login(self, request: HttpRequest, sociallogin: Any) -> None:
        if not self._allowed(sociallogin) or not sociallogin.user.is_active:
            raise ImmediateHttpResponse(HttpResponseForbidden("Conta Google não autorizada."))

    def save_user(self, request: HttpRequest, sociallogin: Any, form: Any = None) -> User:
        user = super().save_user(request, sociallogin, form)
        user.is_staff = user.email.lower() == settings.ADMIN_EMAIL
        user.is_superuser = user.is_staff
        update_fields = ["is_staff", "is_superuser"]
        if user.is_staff:
            user.can_create_libraries = True
            update_fields.append("can_create_libraries")
        user.save(update_fields=update_fields)
        library = Library.objects.order_by("pk").first()
        if library:
            membership, _ = Membership.objects.get_or_create(
                user=user,
                library=library,
                defaults={
                    "role": Membership.ROLE_ADMIN if user.is_staff else Membership.ROLE_MEMBER
                },
            )
            if user.is_staff and membership.role != Membership.ROLE_ADMIN:
                membership.role = Membership.ROLE_ADMIN
                membership.save(update_fields=["role"])
        return user
