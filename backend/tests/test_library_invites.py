import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, RequestFactory
from django.utils import timezone

from library.auth import GoogleAdapter
from library.models import Library, LibraryInvite, Membership, User

pytestmark = pytest.mark.django_db


def create_invite(client, library):
    return client.post(
        "/api/v1/invites",
        data="{}",
        content_type="application/json",
        HTTP_X_LIBRARY_ID=str(library.pk),
    )


def verify_google(user):
    SocialAccount.objects.create(user=user, provider="google", uid=f"google-{user.pk}")
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)


def existing_invited_sociallogin(user):
    now = timezone.now()
    library = Library.objects.create(name="Biblioteca convidada")
    invite = LibraryInvite.objects.create(
        library=library,
        token_hash="a" * 64,
        created_at=now - timezone.timedelta(days=1),
        expires_at=now + timezone.timedelta(days=6),
        accepted_at=now,
        accepted_by=user,
    )
    Membership.objects.create(user=user, library=library, invitation=invite)
    verify_google(user)
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(provider="google", uid=f"google-{user.pk}"),
    )
    sociallogin.email_addresses = [type("Email", (), {"verified": True, "email": user.email})()]
    return sociallogin


def test_library_admin_creates_link_that_is_only_returned_once(client, member):
    library = Library.objects.create(name="Família")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)

    created = create_invite(client, library)

    assert created.status_code == 200
    link = created.json()["invite_url"]
    assert urlsplit(link).path == "/convites/aceitar"
    assert len(urlsplit(link).fragment) >= 32
    assert "token" not in created.json()

    listed = client.get("/api/v1/invites", HTTP_X_LIBRARY_ID=str(library.pk))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert urlsplit(link).fragment not in json.dumps(listed.json())
    assert "invite_url" not in json.dumps(listed.json())


def test_library_member_cannot_list_or_create_invites(client):
    user = User.objects.create_user(username="member", email="ju@example.com")
    library = Library.objects.create(name="Família")
    Membership.objects.create(user=user, library=library, role=Membership.ROLE_MEMBER)
    client.force_login(user)

    listed = client.get("/api/v1/invites", HTTP_X_LIBRARY_ID=str(library.pk))
    created = create_invite(client, library)

    assert listed.status_code == 403
    assert created.status_code == 403


def test_link_acceptance_grants_only_target_membership_to_unlisted_user(client, member):
    library = Library.objects.create(name="Convidante")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    invite_url = create_invite(client, library).json()["invite_url"]
    token = urlsplit(invite_url).fragment

    invitee = User.objects.create_user(username="convidado", email="convidado@example.com")
    verify_google(invitee)
    invitee_client = type(client)()
    prepared = invitee_client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    assert prepared.status_code == 200
    assert prepared.json()["library_name"] == "Convidante"
    assert "token" not in prepared.json()

    invitee_client.force_login(invitee)
    prepared_again = invitee_client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    assert prepared_again.status_code == 200

    accepted = invitee_client.post(
        "/api/v1/invites/accept", data="{}", content_type="application/json"
    )

    assert accepted.status_code == 200
    membership = Membership.objects.get(user=invitee, library=library)
    assert membership.role == Membership.ROLE_MEMBER
    assert membership.invitation_id is not None
    assert Membership.objects.filter(user=invitee).count() == 1

    session = invitee_client.get("/api/v1/session")
    assert session.status_code == 200
    assert [item["id"] for item in session.json()["libraries"]] == [library.pk]
    assert session.json()["technical"] is False
    assert session.json()["can_create_libraries"] is False

    User.objects.filter(pk=invitee.pk).update(can_create_libraries=True)
    denied_create = invitee_client.post(
        "/api/v1/libraries",
        data=json.dumps({"name": "Biblioteca indevida"}),
        content_type="application/json",
    )
    other_library = Library.objects.create(name="Outra")
    denied_other_library = invitee_client.get(
        "/api/v1/books", HTTP_X_LIBRARY_ID=str(other_library.pk)
    )
    assert denied_create.status_code == 403
    assert denied_other_library.status_code == 403
    assert not Membership.objects.filter(user=invitee, library=other_library).exists()


def test_already_member_does_not_consume_link_or_duplicate_membership(client, member):
    library = Library.objects.create(name="Convidante")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    invited_user = User.objects.create_user(username="ju", email="ju@example.com")
    verify_google(invited_user)
    existing = Membership.objects.create(
        user=invited_user, library=library, role=Membership.ROLE_MEMBER
    )
    token = urlsplit(create_invite(client, library).json()["invite_url"]).fragment
    invitee_client = type(client)()
    invitee_client.force_login(invited_user)
    invitee_client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )

    accepted = invitee_client.post(
        "/api/v1/invites/accept", data="{}", content_type="application/json"
    )

    assert accepted.status_code == 200
    assert accepted.json()["already_member"] is True
    assert Membership.objects.get(pk=existing.pk).invitation_id is None
    assert Membership.objects.filter(user=invited_user, library=library).count() == 1


def test_accepting_invite_preserves_all_existing_memberships(member):
    existing_library = Library.objects.create(name="Biblioteca existente")
    target_library = Library.objects.create(name="Biblioteca convidante")
    Membership.objects.create(user=member, library=existing_library, role=Membership.ROLE_MEMBER)
    inviter = User.objects.create_user(username="ju", email="ju@example.com")
    Membership.objects.create(user=inviter, library=target_library, role=Membership.ROLE_ADMIN)
    admin_client = Client()
    admin_client.force_login(inviter)
    token = urlsplit(create_invite(admin_client, target_library).json()["invite_url"]).fragment
    verify_google(member)
    invitee_client = Client()
    invitee_client.force_login(member)
    invitee_client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )

    accepted = invitee_client.post(
        "/api/v1/invites/accept", data="{}", content_type="application/json"
    )
    session = invitee_client.get("/api/v1/session")

    assert accepted.status_code == 200
    assert {item["id"] for item in session.json()["libraries"]} == {
        existing_library.pk,
        target_library.pk,
    }
    assert (
        Membership.objects.get(user=member, library=existing_library).role == Membership.ROLE_MEMBER
    )


def test_revoked_and_expired_links_cannot_be_prepared(client, member):
    library = Library.objects.create(name="Convidante")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    invite_url = create_invite(client, library).json()["invite_url"]
    token = urlsplit(invite_url).fragment
    invite = library.invites.get()

    invite.expires_at = timezone.now()
    invite.save(update_fields=["expires_at"])
    expired = client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    assert expired.status_code == 410

    invite.expires_at = timezone.now() + timezone.timedelta(days=1)
    invite.revoked_at = timezone.now()
    invite.save(update_fields=["expires_at", "revoked_at"])
    revoked = client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    assert revoked.status_code == 410


def test_unlisted_google_login_requires_valid_invite_context(client, member):
    user = User(username="invitee", email="outside@example.com")
    sociallogin = SocialLogin(user=user, account=SocialAccount(provider="google", uid="external"))
    sociallogin.email_addresses = [type("Email", (), {"verified": True, "email": user.email})()]
    request = RequestFactory().get("/accounts/google/login/")
    request.session = client.session
    adapter = GoogleAdapter()

    assert adapter.is_open_for_signup(request, sociallogin) is False
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(request, sociallogin)
    library = Library.objects.create(name="Convidante")
    Membership.objects.create(user=member, library=library, role="admin")
    create_invite(client, library)
    request.session["julib_pending_library_invite"] = library.invites.get().token_hash

    assert adapter.is_open_for_signup(request, sociallogin) is True
    adapter.pre_social_login(request, sociallogin)


def test_invited_member_can_log_in_after_invite_was_consumed(client):
    user = User.objects.create_user(username="invitee", email="outside@example.com")
    sociallogin = existing_invited_sociallogin(user)
    request = RequestFactory().get("/accounts/google/login/")
    request.session = client.session
    adapter = GoogleAdapter()

    assert adapter.is_open_for_signup(request, sociallogin) is True
    adapter.pre_social_login(request, sociallogin)


def test_removing_invited_membership_revokes_google_login(client):
    user = User.objects.create_user(username="invitee", email="outside@example.com")
    sociallogin = existing_invited_sociallogin(user)
    Membership.objects.filter(user=user).delete()
    request = RequestFactory().get("/accounts/google/login/")
    request.session = client.session
    adapter = GoogleAdapter()

    assert adapter.is_open_for_signup(request, sociallogin) is False
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(request, sociallogin)


def test_invite_preparation_requires_csrf_token(client, member):
    library = Library.objects.create(name="Convidante")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    token = urlsplit(create_invite(client, library).json()["invite_url"]).fragment
    strict_client = Client(enforce_csrf_checks=True)
    csrf_response = strict_client.get("/api/v1/csrf")

    missing = strict_client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    prepared = strict_client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_response.json()["csrf"],
    )

    assert missing.status_code == 403
    assert prepared.status_code == 200


def test_last_administrator_cannot_leave_or_be_removed(client, member):
    library = Library.objects.create(name="Único admin")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)

    response = client.delete("/api/v1/members/me", HTTP_X_LIBRARY_ID=str(library.pk))

    assert response.status_code == 409
    assert Membership.objects.filter(user=member, library=library).exists()


def test_invitation_provenance_cannot_cross_library_boundaries(client, member):
    library = Library.objects.create(name="Convidante")
    other = Library.objects.create(name="Outra biblioteca")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    invite_url = create_invite(client, library).json()["invite_url"]
    token = urlsplit(invite_url).fragment
    client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    invite = library.invites.get()
    outsider = User.objects.create_user(username="cross-library", email="cross@example.com")

    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(user=outsider, library=other, invitation=invite)


@pytest.mark.django_db(transaction=True)
def test_concurrent_admin_removals_cannot_remove_both_administrators():
    library = Library.objects.create(name="Administradores concorrentes")
    first = User.objects.create_user(username="first-admin", email="marco@example.com")
    second = User.objects.create_user(username="second-admin", email="ju@example.com")
    Membership.objects.create(user=first, library=library, role=Membership.ROLE_ADMIN)
    Membership.objects.create(user=second, library=library, role=Membership.ROLE_ADMIN)
    clients = [Client(), Client()]
    clients[0].force_login(first)
    clients[1].force_login(second)

    def remove_other(index: int):
        close_old_connections()
        user_id = second.pk if index == 0 else first.pk
        response = clients[index].delete(
            f"/api/v1/members/{user_id}", HTTP_X_LIBRARY_ID=str(library.pk)
        )
        close_old_connections()
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(remove_other, (0, 1)))

    assert sorted(statuses) == [200, 403]
    assert Membership.objects.filter(library=library, role=Membership.ROLE_ADMIN).count() == 1


def test_oauth_signup_rejects_invite_revoked_after_authorization(client, member):
    library = Library.objects.create(name="OAuth convite revogado")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    token = urlsplit(create_invite(client, library).json()["invite_url"]).fragment
    client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    invite = library.invites.get()
    request = RequestFactory().get("/accounts/google/login/")
    request.session = client.session
    user = User(username="oauth-revoked", email="outside@example.com")
    sociallogin = SocialLogin(user=user, account=SocialAccount(provider="google", uid="revoked"))
    sociallogin.email_addresses = [type("Email", (), {"verified": True, "email": user.email})()]
    adapter = GoogleAdapter()
    adapter.pre_social_login(request, sociallogin)
    invite.revoked_at = timezone.now()
    invite.save(update_fields=["revoked_at"])

    with pytest.raises(ImmediateHttpResponse):
        adapter.save_user(request, sociallogin)

    assert not User.objects.filter(email="outside@example.com").exists()
    assert not Membership.objects.filter(user__email="outside@example.com").exists()


def test_oauth_signup_rejects_invite_expired_after_authorization(client, member):
    library = Library.objects.create(name="OAuth convite expirado")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    token = urlsplit(create_invite(client, library).json()["invite_url"]).fragment
    client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    invite = library.invites.get()
    request = RequestFactory().get("/accounts/google/login/")
    request.session = client.session
    user = User(username="oauth-expired", email="outside-expired@example.com")
    sociallogin = SocialLogin(user=user, account=SocialAccount(provider="google", uid="expired"))
    sociallogin.email_addresses = [type("Email", (), {"verified": True, "email": user.email})()]
    adapter = GoogleAdapter()
    adapter.pre_social_login(request, sociallogin)
    now = timezone.now()
    invite.created_at = now - timezone.timedelta(days=8)
    invite.expires_at = now - timezone.timedelta(days=1)
    invite.save(update_fields=["created_at", "expires_at"])

    with pytest.raises(ImmediateHttpResponse):
        adapter.save_user(request, sociallogin)

    assert not User.objects.filter(email="outside-expired@example.com").exists()
    assert not Membership.objects.filter(user__email="outside-expired@example.com").exists()


def test_oauth_signup_requires_acceptance_for_invite_membership(client, member):
    library = Library.objects.create(name="OAuth convite válido")
    Membership.objects.create(user=member, library=library, role=Membership.ROLE_ADMIN)
    token = urlsplit(create_invite(client, library).json()["invite_url"]).fragment
    invitee_client = Client()
    invitee_client.post(
        "/api/v1/invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )
    session = invitee_client.session
    request = RequestFactory().get("/accounts/google/login/")
    request.session = session
    user = User(username="oauth-invitee", email="oauth-invitee@example.com")
    sociallogin = SocialLogin(user=user, account=SocialAccount(provider="google", uid="invitee"))
    sociallogin.email_addresses = [type("Email", (), {"verified": True, "email": user.email})()]
    adapter = GoogleAdapter()

    adapter.pre_social_login(request, sociallogin)
    created = adapter.save_user(request, sociallogin)
    session.save()
    invitee_client.cookies["sessionid"] = session.session_key
    invitee_client.force_login(created)

    assert created.is_staff is False
    assert created.can_create_libraries is False
    assert not Membership.objects.filter(user=created).exists()
    accepted = invitee_client.post(
        "/api/v1/invites/accept", data="{}", content_type="application/json"
    )

    assert accepted.status_code == 200
    assert accepted.json()["library_id"] == library.pk
    assert Membership.objects.filter(user=created, library=library, role="member").exists()


@pytest.mark.django_db(transaction=True)
def test_simultaneous_invite_acceptance_consumes_invite_once():
    library = Library.objects.create(name="Aceite concorrente")
    inviter = User.objects.create_user(username="inviter", email="ju@example.com")
    Membership.objects.create(user=inviter, library=library, role=Membership.ROLE_ADMIN)
    admin_client = Client()
    admin_client.force_login(inviter)
    token = urlsplit(create_invite(admin_client, library).json()["invite_url"]).fragment
    invitee_clients = []
    invitees = []
    for index in range(2):
        invitee = User.objects.create_user(
            username=f"invitee-{index}", email=f"invitee-{index}@example.com"
        )
        verify_google(invitee)
        invitee_client = Client()
        invitee_client.post(
            "/api/v1/invites/prepare",
            data=json.dumps({"token": token}),
            content_type="application/json",
        )
        invitee_client.force_login(invitee)
        invitees.append(invitee)
        invitee_clients.append(invitee_client)

    def accept(index: int):
        close_old_connections()
        result = invitee_clients[index].post(
            "/api/v1/invites/accept", data="{}", content_type="application/json"
        )
        close_old_connections()
        return result.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(accept, (0, 1)))

    assert sorted(statuses) == [200, 410]
    assert Membership.objects.filter(library=library, invitation__isnull=False).count() == 1
    assert library.invites.get().accepted_by_id in {invitee.pk for invitee in invitees}
