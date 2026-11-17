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
    PENDING_CREATION_INVITE_SESSION_KEY,
    PENDING_INVITE_SESSION_KEY,
    PENDING_OAUTH_CREATION_INVITE_SESSION_KEY,
    PENDING_OAUTH_INVITE_SESSION_KEY,
    creation_invite_matches_google_email,
    has_creation_invite_context,
    has_invited_membership,
    valid_pending_creation_invite,
    valid_pending_invite,
    visible_memberships,
)
from .models import Library, LibraryCreationInvite, LibraryInvite, Membership, User


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
        pending_creation = valid_pending_creation_invite(request)
        path = request.path_info
        if path == "/api/v1/invites/accept" and pending is not None:
            return user
        if path == "/api/v1/libraries/from-invite" and has_creation_invite_context(request):
            return user
        if path in {
            "/api/v1/session",
            "/api/v1/libraries",
            "/api/v1/logout",
            "/api/v1/preferences/catalog",
        } and (pending is not None or pending_creation is not None or has_invited_membership(user)):
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
        return (
            self._allowed(sociallogin)
            or self._valid_invite_login(request, sociallogin)
            or self._valid_creation_invite_login(request, sociallogin)
            or self._has_invited_membership_login(sociallogin)
        )

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

    def _valid_creation_invite_login(self, request: HttpRequest | None, sociallogin: Any) -> bool:
        invite = valid_pending_creation_invite(request) if request is not None else None
        return bool(invite and creation_invite_matches_google_email(invite, sociallogin))

    def _has_invited_membership_login(self, sociallogin: Any) -> bool:
        user = sociallogin.user
        return (
            sociallogin.account.provider == "google"
            and isinstance(user, User)
            and user.pk is not None
            and user.is_active
            and has_invited_membership(user)
            and any(
                email.verified and email.email.lower() == user.email.lower()
                for email in sociallogin.email_addresses
            )
        )

    def pre_social_login(self, request: HttpRequest, sociallogin: Any) -> None:
        allowed = self._allowed(sociallogin)
        invite_login = self._valid_invite_login(request, sociallogin)
        creation_invite_login = self._valid_creation_invite_login(request, sociallogin)
        member_login = self._has_invited_membership_login(sociallogin)
        if (
            not (allowed or invite_login or creation_invite_login or member_login)
            or not sociallogin.user.is_active
        ):
            raise ImmediateHttpResponse(HttpResponseForbidden("Conta Google não autorizada."))
        if request is not None and creation_invite_login:
            creation_pending = valid_pending_creation_invite(request)
            if creation_pending is not None:
                request.session[PENDING_OAUTH_CREATION_INVITE_SESSION_KEY] = (
                    creation_pending.token_hash
                )
                request.session.pop(PENDING_OAUTH_INVITE_SESSION_KEY, None)
                request.session.modified = True
        elif request is not None and invite_login:
            library_pending = valid_pending_invite(request)
            if library_pending is not None:
                request.session[PENDING_OAUTH_INVITE_SESSION_KEY] = library_pending.token_hash
                request.session.pop(PENDING_OAUTH_CREATION_INVITE_SESSION_KEY, None)
                request.session.modified = True
        elif request is not None:
            request.session.pop(PENDING_OAUTH_INVITE_SESSION_KEY, None)
            request.session.pop(PENDING_OAUTH_CREATION_INVITE_SESSION_KEY, None)

    def save_user(self, request: HttpRequest, sociallogin: Any, form: Any = None) -> User:
        invite_context_present = PENDING_OAUTH_INVITE_SESSION_KEY in request.session
        invite_context = request.session.get(PENDING_OAUTH_INVITE_SESSION_KEY)
        creation_context_present = PENDING_OAUTH_CREATION_INVITE_SESSION_KEY in request.session
        creation_context = request.session.get(PENDING_OAUTH_CREATION_INVITE_SESSION_KEY)
        pending_creation = (
            valid_pending_creation_invite(request) if creation_context_present else None
        )
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

        if creation_context_present and (
            not isinstance(creation_context, str)
            or pending_creation is None
            or pending_creation.token_hash != creation_context
            or not self._valid_creation_invite_login(request, sociallogin)
        ):
            request.session.pop(PENDING_CREATION_INVITE_SESSION_KEY, None)
            request.session.pop(PENDING_OAUTH_CREATION_INVITE_SESSION_KEY, None)
            request.session.modified = True
            raise ImmediateHttpResponse(
                HttpResponseForbidden("O convite expirou ou foi revogado durante a autenticação.")
            )

        invited_signup = (invite_context_present or creation_context_present) and not self._allowed(
            sociallogin
        )
        if (
            not invite_context_present
            and not creation_context_present
            and not self._allowed(sociallogin)
        ):
            raise ImmediateHttpResponse(HttpResponseForbidden("Conta Google não autorizada."))

        with transaction.atomic():
            library = None
            if invite_context_present and invited_signup:
                assert pending is not None
                library = Library.objects.select_for_update().filter(pk=pending.library_id).first()
                library_invite = (
                    LibraryInvite.objects.select_for_update().filter(pk=pending.pk).first()
                )
                if (
                    library is None
                    or library_invite is None
                    or library_invite.token_hash != invite_context
                    or library_invite.revoked_at is not None
                    or library_invite.accepted_at is not None
                    or library_invite.expires_at <= timezone.now()
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

            if creation_context_present:
                assert pending_creation is not None
                creation_invite = (
                    LibraryCreationInvite.objects.select_for_update()
                    .filter(pk=pending_creation.pk)
                    .first()
                )
                if (
                    creation_invite is None
                    or creation_invite.token_hash != creation_context
                    or creation_invite.revoked_at is not None
                    or creation_invite.accepted_at is not None
                    or creation_invite.created_library_id is not None
                    or creation_invite.expires_at <= timezone.now()
                    or not creation_invite_matches_google_email(creation_invite, sociallogin)
                ):
                    request.session.pop(PENDING_CREATION_INVITE_SESSION_KEY, None)
                    request.session.pop(PENDING_OAUTH_CREATION_INVITE_SESSION_KEY, None)
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
            if not invite_context_present and not creation_context_present:
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
            request.session.pop(PENDING_OAUTH_CREATION_INVITE_SESSION_KEY, None)
            request.session.modified = True
            return user
