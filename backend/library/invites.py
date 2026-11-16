import hashlib
import secrets
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Library, LibraryInvite, Membership, User

PENDING_INVITE_SESSION_KEY = "julib_pending_library_invite"
PENDING_OAUTH_INVITE_SESSION_KEY = "julib_pending_library_invite_oauth"
INVITE_LIFETIME = timedelta(days=7)
TOKEN_BYTES = 32


class InviteError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def valid_pending_invite(request) -> LibraryInvite | None:
    digest = request.session.get(PENDING_INVITE_SESSION_KEY)
    if not isinstance(digest, str) or len(digest) != 64:
        return None
    return (
        LibraryInvite.objects.select_related("library")
        .filter(
            token_hash=digest,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )


def _invite_from_token(token: str) -> LibraryInvite:
    if not isinstance(token, str) or not 20 <= len(token) <= 128:
        raise InviteError("Este link de convite não é válido.", 404)
    invite = (
        LibraryInvite.objects.select_related("library")
        .filter(token_hash=token_digest(token))
        .first()
    )
    if invite is None:
        raise InviteError("Este link de convite não é válido.", 404)
    if invite.revoked_at:
        raise InviteError("Este convite foi revogado.", 410)
    if invite.accepted_at:
        raise InviteError("Este convite já foi utilizado.", 410)
    if invite.expires_at <= timezone.now():
        raise InviteError("Este convite expirou.", 410)
    return invite


def create_link(request, library: Library, user: User) -> tuple[LibraryInvite, str]:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = timezone.now()
    with transaction.atomic():
        locked_library = Library.objects.select_for_update().get(pk=library.pk)
        if not Membership.objects.filter(
            library=locked_library, user=user, role=Membership.ROLE_ADMIN
        ).exists():
            raise InviteError("Somente administradores desta biblioteca podem criar convites.", 403)
        invite = LibraryInvite.objects.create(
            library=locked_library,
            created_by=user,
            token_hash=token_digest(token),
            created_at=now,
            expires_at=now + INVITE_LIFETIME,
        )
    origin = f"{request.scheme}://{request.get_host()}"
    link = f"{origin}/convites/aceitar#{token}"
    return invite, link


def prepare_invite(request, token: str) -> LibraryInvite:
    invite = _invite_from_token(token)
    request.session[PENDING_INVITE_SESSION_KEY] = invite.token_hash
    request.session.modified = True
    return invite


def pending_invite_preview(request) -> LibraryInvite | None:
    return valid_pending_invite(request)


def invite_status(invite: LibraryInvite, now=None) -> str:
    now = now or timezone.now()
    if invite.accepted_at:
        return "accepted"
    if invite.revoked_at:
        return "revoked"
    if invite.expires_at <= now:
        return "expired"
    return "pending"


def is_allowlisted(user: User) -> bool:
    return user.is_active and user.email.lower() in settings.ALLOWED_EMAILS


def has_verified_google_email(user: User) -> bool:
    return (
        SocialAccount.objects.filter(user=user, provider="google").exists()
        and EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()
    )


def has_invited_membership(user: User, library_id: int | None = None) -> bool:
    memberships = Membership.objects.filter(
        user=user,
        invitation__accepted_by=user,
        invitation__accepted_at__isnull=False,
    )
    if library_id is not None:
        memberships = memberships.filter(library_id=library_id)
    return memberships.exists()


def membership_is_authorized_by_invite(user: User, membership: Membership) -> bool:
    invitation = membership.invitation
    return bool(
        invitation and invitation.accepted_by_id == user.pk and invitation.accepted_at is not None
    )


def visible_memberships(user: User, pending: LibraryInvite | None = None):
    memberships = Membership.objects.filter(user=user).select_related("library", "invitation")
    if is_allowlisted(user):
        return memberships
    authorized_ids = Membership.objects.filter(
        user=user,
        invitation__accepted_by=user,
        invitation__accepted_at__isnull=False,
    ).values("pk")
    memberships = memberships.filter(pk__in=authorized_ids)
    if pending is not None:
        memberships = (
            Membership.objects.filter(user=user)
            .filter(
                # Keep only invite-derived memberships plus an existing membership
                # in the library represented by the pending link.
                Q(invitation__accepted_by=user, invitation__accepted_at__isnull=False)
                | Q(library_id=pending.library_id)
            )
            .select_related("library", "invitation")
        )
    return memberships


def accept_pending_invite(request, user: User) -> tuple[LibraryInvite, Membership | None, bool]:
    pending = valid_pending_invite(request)
    if pending is None:
        raise InviteError("Não há convite válido nesta sessão.", 410)

    with transaction.atomic():
        Library.objects.select_for_update().get(pk=pending.library_id)
        invite = LibraryInvite.objects.select_for_update().get(pk=pending.pk)
        # Recheck after acquiring locks so concurrent revocation/acceptance wins.
        if invite.revoked_at:
            raise InviteError("Este convite foi revogado.", 410)
        if invite.accepted_at:
            raise InviteError("Este convite já foi utilizado.", 410)
        if invite.expires_at <= timezone.now():
            raise InviteError("Este convite expirou.", 410)
        if not has_verified_google_email(user):
            raise InviteError("Entre com uma conta Google verificada para continuar.", 403)

        existing = Membership.objects.filter(user=user, library=invite.library).first()
        if existing:
            # Do not consume a link when the person is already a member.
            if is_allowlisted(user) or membership_is_authorized_by_invite(user, existing):
                request.session.pop(PENDING_INVITE_SESSION_KEY, None)
                request.session.modified = True
            return invite, existing, True

        try:
            with transaction.atomic():
                membership = Membership.objects.create(
                    user=user,
                    library=invite.library,
                    role=Membership.ROLE_MEMBER,
                    joined_at=timezone.now(),
                    invitation=invite,
                )
        except IntegrityError:
            # A concurrent membership creation is friendly and does not consume this link.
            existing = Membership.objects.filter(user=user, library=invite.library).first()
            if existing:
                return invite, existing, True
            raise

        invite.accepted_at = timezone.now()
        invite.accepted_by = user
        invite.save(update_fields=["accepted_at", "accepted_by"])
        request.session.pop(PENDING_INVITE_SESSION_KEY, None)
        request.session.modified = True
        return invite, membership, False


def revoke_invite(library: Library, invite_id: int, user: User) -> LibraryInvite:
    with transaction.atomic():
        Library.objects.select_for_update().get(pk=library.pk)
        if not Membership.objects.filter(
            library=library, user=user, role=Membership.ROLE_ADMIN
        ).exists():
            raise InviteError(
                "Somente administradores desta biblioteca podem revogar convites.", 403
            )
        invite = (
            LibraryInvite.objects.select_for_update().filter(pk=invite_id, library=library).first()
        )
        if invite is None:
            raise InviteError("Convite não encontrado nesta biblioteca.", 404)
        if invite.accepted_at:
            raise InviteError("Convites já aceitos não podem ser revogados.", 409)
        if invite.revoked_at is None:
            invite.revoked_at = timezone.now()
            invite.revoked_by = user
            invite.save(update_fields=["revoked_at", "revoked_by"])
        return invite
