from concurrent.futures import ThreadPoolExecutor
from datetime import date
import pytest
from django.db import close_old_connections
from django.test import Client
from library.models import Library, Membership, Location, Person, Loan, User, Book
from library import services
from library.circulation import lend
from django.core.exceptions import ValidationError

@pytest.mark.django_db(transaction=True)
def test_simultaneous_loans_only_one_open():
    lib = Library.objects.create(name='Casa')
    book = services.create_book(lib, {'title':'Livro','authors':['Autor']})
    copy = services.add_copy(lib, book.pk)
    person = Person.objects.create(library=lib, name='Ana', phone='123')
    def attempt():
        close_old_connections()
        try:
            lend(lib, copy.pk, person.pk, date.today())
            return True
        except ValidationError:
            return False
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _:attempt(),range(2))) == [False, True]
    assert Loan.objects.filter(state='open').count() == 1

@pytest.mark.django_db
def test_foreign_relations_and_share_never_leak(client,member):
    lib=Library.objects.create(name='Casa'); Membership.objects.create(user=member,library=lib)
    other=Library.objects.create(name='Segredo'); loc=Location.objects.create(library=other,name='Cofre')
    result=client.post('/api/v1/locations',{'name':'Novo','parent_id':loc.pk},content_type='application/json')
    assert result.status_code == 400
    assert result.headers['Cache-Control'] == 'no-store, private'
    assert client.post('/api/v1/people',{'name':'Ana','phone':'  '},content_type='application/json').status_code == 400

@pytest.mark.django_db
def test_oauth_adapter_requires_verified_google_email():
    from types import SimpleNamespace
    from allauth.core.exceptions import ImmediateHttpResponse
    from library.auth import GoogleAdapter
    adapter = GoogleAdapter()
    login = SimpleNamespace(account=SimpleNamespace(provider='google'), user=User(email='ju@example.com'), email_addresses=[SimpleNamespace(email='ju@example.com',verified=False)])
    with pytest.raises(ImmediateHttpResponse): adapter.pre_social_login(None,login)
    login.email_addresses[0].verified=True
    adapter.pre_social_login(None,login)

@pytest.mark.django_db
def test_authenticated_write_needs_csrf(member):
    client=Client(enforce_csrf_checks=True); client.force_login(member)
    assert client.post('/api/v1/locations',{'name':'Casa'},content_type='application/json').status_code == 403
