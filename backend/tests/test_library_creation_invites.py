import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client, RequestFactory
from django.utils import timezone

from library import invites
from library.auth import GoogleAdapter
from library.models import Library, LibraryCreationInvite, LibraryInvite, Membership, User

pytestmark = pytest.mark.django_db


def create_creation_invite(client, email=None):
    return client.post(
        "/api/v1/library-creation-invites",
        data=json.dumps({} if email is None else {"email": email}),
        content_type="application/json",
    )


def verify_google(user):
    SocialAccount.objects.create(user=user, provider="google", uid=f"google-{user.pk}")
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)


def prepare_creation_invite(client, token):
    return client.post(
        "/api/v1/library-creation-invites/prepare",
        data=json.dumps({"token": token}),
        content_type="application/json",
    )


def consume_creation_invite(client, name="Nova biblioteca"):
    return client.post(
        "/api/v1/libraries/from-invite",
        data=json.dumps({"name": name}),
        content_type="application/json",
    )


def test_technical_owner_creates_single_use_creation_link(client, member):
    before = timezone.now()

    created = create_creation_invite(client)

    assert created.status_code == 200
    link = created.json()["invite_url"]
    assert urlsplit(link).path == "/convites/criar"
    assert len(urlsplit(link).fragment) >= 32
    assert "token" not in created.json()
    invite = LibraryCreationInvite.objects.get()
    assert invite.token_hash != urlsplit(link).fragment
    assert invite.expires_at - invite.created_at == timezone.timedelta(days=7)
    assert invite.created_at >= before

    listed = client.get("/api/v1/library-creation-invites")

    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "pending"
    assert urlsplit(link).fragment not in json.dumps(listed.json())


def test_only_technical_owner_can_manage_creation_invites(client, member):
    invitee = User.objects.create_user(username="ju", email="ju@example.com")
    client.force_login(invitee)

    assert create_creation_invite(client).status_code == 403
    assert client.get("/api/v1/library-creation-invites").status_code == 403


def test_valid_creation_invite_creates_library_and_admin_membership_without_global_permission(
    client, member
):
    owner = member
    outsider = User.objects.create_user(username="convidada", email="fora@example.com")
    verify_google(outsider)
    owner_client = Client()
    owner_client.force_login(owner)
    token = urlsplit(create_creation_invite(owner_client).json()["invite_url"]).fragment
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    invitee_client.force_login(outsider)

    created = consume_creation_invite(invitee_client, "Biblioteca de Ana")

    assert created.status_code == 200
    library = Library.objects.get(name="Biblioteca de Ana")
    membership = Membership.objects.get(user=outsider, library=library)
    assert membership.role == Membership.ROLE_ADMIN
    outsider.refresh_from_db()
    assert outsider.can_create_libraries is False
    assert outsider.is_staff is False
    assert outsider.is_superuser is False
    assert (
        invitee_client.post(
            "/api/v1/libraries",
            data=json.dumps({"name": "Criação sem convite"}),
            content_type="application/json",
        ).status_code
        == 403
    )
    replay_client = Client()
    assert prepare_creation_invite(replay_client, token).status_code == 410
    listed = owner_client.get("/api/v1/library-creation-invites")
    assert listed.json()[0]["status"] == "accepted"
    assert listed.json()[0]["created_library"]["id"] == library.pk


def test_creation_invite_email_binding_requires_matching_verified_google_address(client, member):
    token = urlsplit(
        create_creation_invite(client, "destino@example.com").json()["invite_url"]
    ).fragment
    invitee = User.objects.create_user(username="wrong-email", email="other@example.com")
    verify_google(invitee)
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    invitee_client.force_login(invitee)

    response = consume_creation_invite(invitee_client)

    assert response.status_code == 403
    assert not Library.objects.filter(name="Nova biblioteca").exists()


def test_creation_invite_email_binding_accepts_matching_verified_google_address(client, member):
    token = urlsplit(
        create_creation_invite(client, "  Destino@Example.com ").json()["invite_url"]
    ).fragment
    invitee = User.objects.create_user(username="matching-email", email="destino@example.com")
    verify_google(invitee)
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).json()["email"] == "destino@example.com"
    invitee_client.force_login(invitee)

    response = consume_creation_invite(invitee_client)

    assert response.status_code == 200
    assert Membership.objects.get(user=invitee).role == Membership.ROLE_ADMIN


def test_creation_invite_requires_verified_google_identity(client, member):
    token = urlsplit(create_creation_invite(client).json()["invite_url"]).fragment
    invitee = User.objects.create_user(username="unverified", email="unverified@example.com")
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    invitee_client.force_login(invitee)

    response = consume_creation_invite(invitee_client)

    assert response.status_code == 403
    assert not Library.objects.filter(name="Nova biblioteca").exists()


def test_existing_user_keeps_other_memberships_and_can_invite_into_created_library(client, member):
    owner_client = Client()
    owner_client.force_login(member)
    token = urlsplit(create_creation_invite(owner_client).json()["invite_url"]).fragment
    existing_user = User.objects.create_user(username="existing", email="existing@example.com")
    verify_google(existing_user)
    existing_library = Library.objects.create(name="Biblioteca existente")
    prior_invite = LibraryInvite.objects.create(
        library=existing_library,
        token_hash="d" * 64,
        created_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=7),
        accepted_at=timezone.now(),
        accepted_by=existing_user,
    )
    old_membership = Membership.objects.create(
        user=existing_user,
        library=existing_library,
        role=Membership.ROLE_MEMBER,
        invitation=prior_invite,
    )
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    invitee_client.force_login(existing_user)

    created = consume_creation_invite(invitee_client, "Outra biblioteca")

    assert created.status_code == 200
    created_library = Library.objects.get(name="Outra biblioteca")
    old_membership.refresh_from_db()
    assert old_membership.role == Membership.ROLE_MEMBER
    session = invitee_client.get("/api/v1/session").json()
    assert {item["id"] for item in session["libraries"]} == {
        existing_library.pk,
        created_library.pk,
    }
    member_invite = invitee_client.post(
        "/api/v1/invites",
        data="{}",
        content_type="application/json",
        HTTP_X_LIBRARY_ID=str(created_library.pk),
    )
    assert member_invite.status_code == 200
    assert LibraryInvite.objects.filter(library=created_library).count() == 1


def test_creation_invite_can_be_revoked_and_cannot_be_prepared_or_consumed_afterward(
    client, member
):
    token = urlsplit(create_creation_invite(client).json()["invite_url"]).fragment
    invite = LibraryCreationInvite.objects.get()
    invitee = User.objects.create_user(username="revoked", email="revoked@example.com")
    verify_google(invitee)
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    invitee_client.force_login(invitee)

    revoked = client.delete(f"/api/v1/library-creation-invites/{invite.pk}")
    attempted = consume_creation_invite(invitee_client)

    assert revoked.status_code == 200
    assert attempted.status_code == 410
    assert Library.objects.count() == 0


def test_creation_invite_oauth_callback_rejects_revocation_after_oauth_started(client, member):
    token = urlsplit(create_creation_invite(client).json()["invite_url"]).fragment
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    request = RequestFactory().get("/accounts/google/login/")
    request.session = invitee_client.session
    user = User(username="oauth-create", email="oauth-create@example.com")
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(provider="google", uid="oauth-create"),
    )
    sociallogin.email_addresses = [type("Email", (), {"verified": True, "email": user.email})()]
    adapter = GoogleAdapter()
    adapter.pre_social_login(request, sociallogin)
    invite = LibraryCreationInvite.objects.get()
    client.delete(f"/api/v1/library-creation-invites/{invite.pk}")

    with pytest.raises(ImmediateHttpResponse):
        adapter.save_user(request, sociallogin)

    assert not User.objects.filter(email=user.email).exists()
    assert Library.objects.count() == 0


def test_new_google_account_can_finish_oauth_then_consume_creation_invite(client, member):
    token = urlsplit(create_creation_invite(client).json()["invite_url"]).fragment
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    request = RequestFactory().get("/accounts/google/login/")
    request.session = invitee_client.session
    user = User(username="new-google", email="new-google@example.com")
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(provider="google", uid="new-google"),
    )
    sociallogin.email_addresses = [
        type("Email", (), {"verified": True, "email": user.email, "primary": True})()
    ]
    adapter = GoogleAdapter()
    adapter.pre_social_login(request, sociallogin)

    created_user = adapter.save_user(request, sociallogin)

    assert created_user.is_staff is False
    assert created_user.is_superuser is False
    assert created_user.can_create_libraries is False
    assert not Membership.objects.filter(user=created_user).exists()
    invitee_client.force_login(created_user)
    response = consume_creation_invite(invitee_client, "Nova própria")

    assert response.status_code == 200
    assert Membership.objects.get(user=created_user).role == Membership.ROLE_ADMIN


def test_creation_invite_consume_revalidates_revocation_after_oauth_callback(client, member):
    token = urlsplit(create_creation_invite(client).json()["invite_url"]).fragment
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    request = RequestFactory().get("/accounts/google/login/")
    request.session = invitee_client.session
    user = User(username="oauth-after-callback", email="oauth-after@example.com")
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(provider="google", uid="oauth-after-callback"),
    )
    sociallogin.email_addresses = [type("Email", (), {"verified": True, "email": user.email})()]
    adapter = GoogleAdapter()
    adapter.pre_social_login(request, sociallogin)
    created_user = adapter.save_user(request, sociallogin)
    invitee_client.force_login(created_user)
    invite = LibraryCreationInvite.objects.get()
    assert client.delete(f"/api/v1/library-creation-invites/{invite.pk}").status_code == 200

    response = consume_creation_invite(invitee_client)

    assert response.status_code == 410
    assert not Library.objects.exists()
    invite.refresh_from_db()
    assert invite.revoked_at is not None
    assert invite.accepted_at is None


def test_library_and_invite_remain_unconsumed_when_membership_creation_fails(client, member):
    token = urlsplit(create_creation_invite(client).json()["invite_url"]).fragment
    invite = LibraryCreationInvite.objects.get()
    invitee = User.objects.create_user(username="rollback", email="rollback@example.com")
    verify_google(invitee)
    invitee_client = Client()
    assert prepare_creation_invite(invitee_client, token).status_code == 200
    invitee_client.force_login(invitee)

    with patch.object(Membership.objects, "create", side_effect=IntegrityError("test failure")):
        response = consume_creation_invite(invitee_client, "Must rollback")

    assert response.status_code == 409
    assert not Library.objects.filter(name="Must rollback").exists()
    invite.refresh_from_db()
    assert invite.accepted_at is None
    assert invite.created_library_id is None


class _TestSession(dict):
    modified = False


def _creation_request(invite):
    return type(
        "Request",
        (),
        {"session": _TestSession({invites.PENDING_CREATION_INVITE_SESSION_KEY: invite.token_hash})},
    )()


def _backend_pid():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        return cursor.fetchone()[0]


def _wait_until_postgres_lock_waits(pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
            row = cursor.fetchone()
        if row and row[0] == "Lock":
            return
        time.sleep(0.01)
    raise AssertionError("A segunda operação não aguardou o bloqueio PostgreSQL do convite.")


@pytest.mark.django_db(transaction=True)
def test_revocation_lock_winning_first_rejects_waiting_consumption(client, member):
    assert connection.vendor == "postgresql"
    invite = LibraryCreationInvite.objects.create(
        token_hash="a" * 64,
        created_by=member,
        created_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    invitee = User.objects.create_user(username="wait-consume", email="wait@example.com")
    verify_google(invitee)
    lock_acquired = Event()
    release_revocation = Event()
    consumer_pid = []

    def revoke_first():
        close_old_connections()
        try:
            with transaction.atomic():
                LibraryCreationInvite.objects.select_for_update().get(pk=invite.pk)
                invites.revoke_creation_invite(invite.pk, member)
                lock_acquired.set()
                assert release_revocation.wait(10)
        finally:
            close_old_connections()

    def consume_second():
        close_old_connections()
        try:
            consumer_pid.append(_backend_pid())
            assert lock_acquired.wait(5)
            return invites.consume_creation_invite(_creation_request(invite), invitee, "Não criar")
        except invites.InviteError as exc:
            return exc.status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        revocation = pool.submit(revoke_first)
        assert lock_acquired.wait(5)
        consumption = pool.submit(consume_second)
        while not consumer_pid:
            time.sleep(0.01)
        try:
            _wait_until_postgres_lock_waits(consumer_pid[0])
        finally:
            release_revocation.set()
        revocation.result(timeout=10)
        assert consumption.result(timeout=10) == 410

    invite.refresh_from_db()
    assert invite.revoked_at is not None
    assert invite.accepted_at is None
    assert Library.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_consumption_lock_winning_first_makes_waiting_revocation_fail(client, member):
    assert connection.vendor == "postgresql"
    invite = LibraryCreationInvite.objects.create(
        token_hash="b" * 64,
        created_by=member,
        created_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    invitee = User.objects.create_user(username="consume-first", email="consume@example.com")
    verify_google(invitee)
    consumed = Event()
    release_consumption = Event()
    revoker_pid = []

    def consume_first():
        close_old_connections()
        try:
            with transaction.atomic():
                LibraryCreationInvite.objects.select_for_update().get(pk=invite.pk)
                result = invites.consume_creation_invite(
                    _creation_request(invite), invitee, "Biblioteca consumida"
                )
                consumed.set()
                assert release_consumption.wait(10)
                return result
        finally:
            close_old_connections()

    def revoke_second():
        close_old_connections()
        try:
            revoker_pid.append(_backend_pid())
            assert consumed.wait(5)
            invites.revoke_creation_invite(invite.pk, member)
            return 200
        except invites.InviteError as exc:
            return exc.status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        consumption = pool.submit(consume_first)
        assert consumed.wait(5)
        revocation = pool.submit(revoke_second)
        while not revoker_pid:
            time.sleep(0.01)
        try:
            _wait_until_postgres_lock_waits(revoker_pid[0])
        finally:
            release_consumption.set()
        result = consumption.result(timeout=10)
        assert result[0].name == "Biblioteca consumida"
        assert revocation.result(timeout=10) == 409

    invite.refresh_from_db()
    assert invite.accepted_at is not None
    assert invite.revoked_at is None
    assert Library.objects.filter(creation_invite=invite).count() == 1
    assert Membership.objects.filter(library=invite.created_library, user=invitee).count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_consumers_create_only_one_library_and_admin_membership(member):
    assert connection.vendor == "postgresql"
    invite = LibraryCreationInvite.objects.create(
        token_hash="c" * 64,
        created_by=member,
        created_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    invitee = User.objects.create_user(username="two-consumers", email="two@example.com")
    verify_google(invitee)
    first_finished = Event()
    release_first = Event()
    second_pid = []

    def consume_and_hold(name):
        close_old_connections()
        try:
            with transaction.atomic():
                LibraryCreationInvite.objects.select_for_update().get(pk=invite.pk)
                result = invites.consume_creation_invite(_creation_request(invite), invitee, name)
                if name == "Primeira":
                    first_finished.set()
                    assert release_first.wait(10)
                return result[0].name
        except invites.InviteError as exc:
            return exc.status_code
        finally:
            close_old_connections()

    def consume_second():
        close_old_connections()
        try:
            second_pid.append(_backend_pid())
            assert first_finished.wait(5)
            with transaction.atomic():
                LibraryCreationInvite.objects.select_for_update().get(pk=invite.pk)
                result = invites.consume_creation_invite(
                    _creation_request(invite), invitee, "Segunda"
                )
                return result[0].name
        except invites.InviteError as exc:
            return exc.status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(consume_and_hold, "Primeira")
        assert first_finished.wait(5)
        second = pool.submit(consume_second)
        while not second_pid:
            time.sleep(0.01)
        try:
            _wait_until_postgres_lock_waits(second_pid[0])
        finally:
            release_first.set()
        assert first.result(timeout=10) == "Primeira"
        assert second.result(timeout=10) == 410

    invite.refresh_from_db()
    assert Library.objects.count() == 1
    assert Membership.objects.filter(library=invite.created_library, user=invitee).count() == 1
