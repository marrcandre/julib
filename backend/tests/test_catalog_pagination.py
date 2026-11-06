import pytest

from library.models import Book, Library, Membership

pytestmark = pytest.mark.django_db


def test_catalog_accepts_bounded_page_sizes_and_clamps_last_page(client, member):
    lib = Library.objects.create(name="Casa")
    Membership.objects.create(library=lib, user=member)
    books = [
        Book.objects.create(library=lib, title=f"Livro {i}", authors=["Autor"]) for i in range(7)
    ]
    response = client.get("/api/v1/books", {"page_size": 3, "page": 2, "order": "oldest"}).json()
    assert response["page_size"] == 3
    assert response["page"] == 2
    assert [b["id"] for b in response["items"]] == [b.pk for b in books[3:6]]
    last = client.get("/api/v1/books", {"page_size": 3, "page": 99, "order": "oldest"}).json()
    assert last["page"] == 3 and len(last["items"]) == 1 and last["total"] == 7
    for size in [0, 101, -1]:
        assert client.get("/api/v1/books", {"page_size": size}).status_code == 422
    empty = client.get("/api/v1/books", {"q": "inexistente", "page_size": 100, "page": 99}).json()
    assert empty["items"] == [] and empty["page"] == 1 and empty["total"] == 0
    assert client.get("/api/v1/books").json()["page_size"] == 24
