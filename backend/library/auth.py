from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.http import HttpRequest, HttpResponseForbidden
from django.utils import timezone
from ninja.errors import HttpError
from ninja.security import SessionAuth

from .invites import (
    PENDING_INVITE_SESSION_KEY,
    PENDING_OAUTH_INVITE_SESSION_KEY,
    has_invited_membership,
    valid_pending_invite,
    visible_memberships,
)
from .models import Library, LibraryInvite, Membership, User


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
        if user is None:
            return None
        if permitted(user):
            return user
        if not user.is_active:
            raise HttpError(403, "Conta sem autorização.")

        pending = valid_pending_invite(request)
        path = request.path_info
        if path == "/api/v1/invites/accept" and pending is not None:
            return user
        if path in {
            "/api/v1/session",
            "/api/v1/libraries",
            "/api/v1/logout",
            "/api/v1/preferences/catalog",
        } and (pending is not None or has_invited_membership(user)):
            return user

        library_id = request.headers.get("X-Library-ID")
        if library_id and library_id.isdecimal() and int(library_id) > 0:
            if has_invited_membership(user, int(library_id)):
                return user
            if pending is not None and pending.library_id == int(library_id):
                if Membership.objects.filter(user=user, library_id=int(library_id)).exists():
                    return user
        raise HttpError(403, "Conta sem autorização.")


def require_membership(request: HttpRequest) -> Membership:
    if not isinstance(request.user, User) or not request.user.is_active:
        raise HttpError(403, "Conta sem autorização.")
    memberships = visible_memberships(request.user, valid_pending_invite(request)).order_by(
        "library_id"
    )
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
        return self._allowed(sociallogin) or self._valid_invite_login(request, sociallogin)

    def _allowed(self, sociallogin: Any) -> bool:
        return sociallogin.account.provider == "google" and any(
            e.verified and e.email.lower() in settings.ALLOWED_EMAILS
            for e in sociallogin.email_addresses
        )

    def _valid_invite_login(self, request: HttpRequest | None, sociallogin: Any) -> bool:
        return (
            sociallogin.account.provider == "google"
            and request is not None
            and valid_pending_invite(request) is not None
            and any(
                e.verified and e.email.lower() == sociallogin.user.email.lower()
                for e in sociallogin.email_addresses
            )
        )

    def pre_social_login(self, request: HttpRequest, sociallogin: Any) -> None:
        allowed = self._allowed(sociallogin)
        invite_login = self._valid_invite_login(request, sociallogin)
        if not (allowed or invite_login) or not sociallogin.user.is_active:
            raise ImmediateHttpResponse(HttpResponseForbidden("Conta Google não autorizada."))
        if request is not None and invite_login:
            pending = valid_pending_invite(request)
            if pending is not None:
                request.session[PENDING_OAUTH_INVITE_SESSION_KEY] = pending.token_hash
                request.session.modified = True
        elif request is not None:
            request.session.pop(PENDING_OAUTH_INVITE_SESSION_KEY, None)

    def save_user(self, request: HttpRequest, sociallogin: Any, form: Any = None) -> User:
        invite_context_present = PENDING_OAUTH_INVITE_SESSION_KEY in request.session
        invite_context = request.session.get(PENDING_OAUTH_INVITE_SESSION_KEY)
        pending = valid_pending_invite(request) if invite_context_present else None
        if invite_context_present and (
            not isinstance(invite_context, str)
            or pending is None
            or pending.token_hash != invite_context
            or not self._valid_invite_login(request, sociallogin)
        ):
            request.session.pop(PENDING_INVITE_SESSION_KEY, None)
            request.session.pop(PENDING_OAUTH_INVITE_SESSION_KEY, None)
            request.session.modified = True
            raise ImmediateHttpResponse(
                HttpResponseForbidden("O convite expirou ou foi revogado durante a autenticação.")
            )

        invited_signup = invite_context_present and not self._allowed(sociallogin)
        if not invite_context_present and not self._allowed(sociallogin):
            raise ImmediateHttpResponse(HttpResponseForbidden("Conta Google não autorizada."))

        with transaction.atomic():
            library = None
            if invited_signup:
                assert pending is not None
                library = Library.objects.select_for_update().filter(pk=pending.library_id).first()
                invite = LibraryInvite.objects.select_for_update().filter(pk=pending.pk).first()
                if (
                    library is None
                    or invite is None
                    or invite.token_hash != invite_context
                    or invite.revoked_at is not None
                    or invite.accepted_at is not None
                    or invite.expires_at <= timezone.now()
                    or not any(email.verified for email in sociallogin.email_addresses)
                ):
                    request.session.pop(PENDING_INVITE_SESSION_KEY, None)
                    request.session.pop(PENDING_OAUTH_INVITE_SESSION_KEY, None)
                    request.session.modified = True
                    raise ImmediateHttpResponse(
                        HttpResponseForbidden(
                            "O convite expirou ou foi revogado durante a autenticação."
                        )
                    )

            user = super().save_user(request, sociallogin, form)
            user.is_staff = user.email.lower() == settings.ADMIN_EMAIL and not invited_signup
            user.is_superuser = user.is_staff
            update_fields = ["is_staff", "is_superuser"]
            if user.is_staff:
                user.can_create_libraries = True
                update_fields.append("can_create_libraries")
            user.save(update_fields=update_fields)

            # A signup that began with an invite must finish through the explicit
            # invite acceptance endpoint. Never fall back to the first library.
            if not invite_context_present:
                default_library = Library.objects.order_by("pk").first()
                if default_library:
                    membership, _ = Membership.objects.get_or_create(
                        user=user,
                        library=default_library,
                        defaults={
                            "role": (
                                Membership.ROLE_ADMIN if user.is_staff else Membership.ROLE_MEMBER
                            )
                        },
                    )
                    if user.is_staff and membership.role != Membership.ROLE_ADMIN:
                        membership.role = Membership.ROLE_ADMIN
                        membership.save(update_fields=["role"])

            request.session.pop(PENDING_OAUTH_INVITE_SESSION_KEY, None)
            request.session.modified = True
            return user
