import pytest

from library.models import Library, Membership, ShareLink
from library.sharing import renew_link

pytestmark = pytest.mark.django_db


def test_session_has_own_stable_id_and_share_status_never_exposes_or_renews_token(client, member):
    library = Library.objects.create(name="Casa")
    Membership.objects.create(user=member, library=library)
    assert client.get("/api/v1/session").json()["user_id"] == member.pk
    other = Library.objects.create(name="Outra")
    renew_link(other)
    assert client.get("/api/v1/share/manage").json() == {"active": False}
    token = renew_link(library)
    before = list(ShareLink.objects.filter(library=library).values_list("digest", "active"))
    assert client.get("/api/v1/share/manage").json() == {"active": True}
    assert list(ShareLink.objects.filter(library=library).values_list("digest", "active")) == before
    assert token not in client.get("/api/v1/share/manage").content.decode()
    client.logout()
    assert client.get("/api/v1/share/manage").status_code == 401
