from library import providers


def _candidate(source: str, source_id: str, **fields):
    provenance = {
        field: {"source": source, "source_id": source_id}
        for field, value in fields.items()
        if value not in (None, "", [])
    }
    return {**fields, "source": source, "source_id": source_id, "provenance": provenance}


def test_global_provider_priority_is_declared_independently_per_field():
    expected = ("openlibrary", "google", "cbl", "mercado-editorial")
    assert providers.PROVIDER_PRIORITIES == expected
    assert providers.FIELD_PRIORITIES["description"] == expected
    assert providers.FIELD_PRIORITIES["subjects"] == expected


def test_valid_isbn_without_range_classification_is_enriched_and_can_return_no_match(monkeypatch):
    isbn = "9786700000007"
    assert providers.normalized_identifier(isbn) == isbn
    calls = []
    monkeypatch.setattr(
        providers, "openlibrary", lambda lookup, value: calls.append("openlibrary") or {}
    )
    monkeypatch.setattr(
        providers, "google", lambda lookup, query, value: calls.append("google") or []
    )
    monkeypatch.setattr(
        providers,
        "brazil",
        lambda lookup, value, source: calls.append(source) or {},
    )
    result = providers.enrich_book({"isbn": isbn})
    assert calls == ["openlibrary", "google", "cbl", "mercado-editorial"]
    assert result["isbn"] == isbn
    assert not result.get("title")


def test_candidate_resolver_uses_independent_field_priority_and_retains_origin():
    candidates = [
        _candidate("openlibrary", "/books/OL1M", description="Descrição internacional"),
        _candidate("google", "vol-1", subjects=["História"]),
        _candidate("cbl", "9788535914849", description="Sinopse CBL", subjects=["História"]),
    ]

    resolved = providers.resolve_candidates(
        candidates,
        "9788535914849",
        {"description", "subjects"},
    )

    assert resolved == {
        "description": (
            "Descrição internacional",
            {"source": "openlibrary", "source_id": "/books/OL1M"},
        ),
        "subjects": (["História"], {"source": "google", "source_id": "vol-1"}),
    }


def test_resolver_obeys_different_declared_priorities_for_different_fields(monkeypatch):
    monkeypatch.setitem(
        providers.FIELD_PRIORITIES,
        "subjects",
        ("google", "openlibrary", "cbl", "mercado-editorial"),
    )
    candidates = [
        _candidate("openlibrary", "/books/OL1M", description="Descrição OL", subjects=["OL"]),
        _candidate("google", "vol-1", description="Descrição Google", subjects=["Google"]),
    ]

    resolved = providers.resolve_candidates(
        candidates,
        "9780261102217",
        {"description", "subjects"},
    )

    assert resolved["description"][0] == "Descrição OL"
    assert resolved["subjects"][0] == ["Google"]


def test_candidate_resolver_falls_back_per_field_without_replacing_present_values():
    candidates = [
        _candidate("openlibrary", "/books/OL1M", subtitle="Subtítulo OL"),
        _candidate("google", "vol-1", description="Descrição Google"),
    ]

    resolved = providers.resolve_candidates(
        candidates,
        "9780261102217",
        {"subtitle", "description"},
    )

    assert resolved["subtitle"][0] == "Subtítulo OL"
    assert resolved["description"][0] == "Descrição Google"


def test_oversized_candidate_is_rejected_and_field_falls_back_to_next_source():
    candidates = [
        _candidate("cbl", "isbn", description="x" * 20_001),
        _candidate("mercado-editorial", "isbn", description="Descrição válida"),
    ]

    resolved = providers.resolve_candidates(candidates, "9788535914849", {"description"})

    assert resolved["description"][0] == "Descrição válida"
    assert resolved["description"][1]["source"] == "mercado-editorial"


def test_description_is_plain_text_and_over_limit_value_is_rejected():
    assert providers.plain_description("<p>Uma <b>descrição</b></p><p>Segunda</p>") == (
        "Uma descrição\n\nSegunda"
    )
    assert providers.plain_description("x" * 20_000) == "x" * 20_000
    assert providers.plain_description("x" * 20_001) == ""


def test_subjects_are_normalized_deduplicated_and_bounded():
    assert providers.normalize_subjects(["Literatura", "", "Literatura", "  História  "]) == [
        "Literatura",
        "História",
    ]
    assert providers.normalize_subjects(["x" * 201]) == []
    assert providers.normalize_subjects([str(i) for i in range(51)]) == []
    assert len(providers.normalize_subjects([str(i) for i in range(50)])) == 50
    assert providers.normalize_subjects(["x" * 200]) == ["x" * 200]
    assert providers.bounded_text("x" * 500, 500) == "x" * 500
    assert providers.bounded_text("x" * 501, 500) == ""


def test_brasilapi_maps_real_cbl_metadata_without_duplicate_subjects():
    class FakeLookup:
        def json(self, url, params):
            return {
                "isbn": "9788535914849",
                "provider": "cbl",
                "title": "1984",
                "subtitle": None,
                "synopsis": "Sinopse em português.",
                "subjects": ["Literatura", "Literatura", ""],
            }

    result = providers.brazil(FakeLookup(), "9788535914849", "cbl")

    assert result["description"] == "Sinopse em português."
    assert result["subjects"] == ["Literatura"]
    assert result["provenance"]["description"]["source"] == "cbl"


def test_google_maps_html_description_and_categories():
    class FakeLookup:
        def json(self, url, params):
            return {
                "items": [
                    {
                        "id": "vol-1",
                        "volumeInfo": {
                            "title": "1984",
                            "subtitle": "Edição anotada",
                            "description": "<p>Uma <b>distopia</b>.</p>",
                            "categories": ["Fiction", "Fiction", "Literature"],
                            "industryIdentifiers": [{"identifier": "9788535914849"}],
                        },
                    }
                ]
            }

    result = providers.google(FakeLookup(), "isbn:9788535914849", "9788535914849")[0]

    assert result["subtitle"] == "Edição anotada"
    assert result["description"] == "Uma distopia."
    assert result["subjects"] == ["Fiction", "Literature"]


def test_openlibrary_work_description_records_its_work_level_provenance():
    isbn = "9788535914849"

    class FakeLookup:
        def json(self, url, params):
            if params.get("jscmd") == "data":
                return {f"ISBN:{isbn}": {"title": "1984", "authors": [], "publishers": []}}
            if params.get("jscmd") == "details":
                return {
                    f"ISBN:{isbn}": {
                        "details": {
                            "key": "/books/OL1M",
                            "title": "1984",
                            "isbn_13": [isbn],
                            "works": [{"key": "/works/OL1W"}],
                        }
                    }
                }
            return {"description": {"value": "Descrição da obra."}}

    result = providers.openlibrary(FakeLookup(), isbn)

    assert result["description"] == "Descrição da obra."
    assert result["provenance"]["description"] == {
        "source": "openlibrary",
        "source_id": "/works/OL1W",
        "record_type": "work",
    }


def test_openlibrary_ignores_work_description_when_edition_isbn_mismatches():
    isbn = "9788535914849"
    work_calls = []

    class FakeLookup:
        def json(self, url, params):
            if params.get("jscmd") == "data":
                return {f"ISBN:{isbn}": {"title": "1984"}}
            if params.get("jscmd") == "details":
                return {
                    f"ISBN:{isbn}": {
                        "details": {
                            "title": "1984",
                            "isbn_13": ["9780261102217"],
                            "works": [{"key": "/works/OL1W"}],
                        }
                    }
                }
            work_calls.append(url)
            return {"description": "Descrição de outra edição."}

    result = providers.openlibrary(FakeLookup(), isbn)

    assert not result.get("description")
    assert work_calls == []


def test_enrichment_queries_each_needed_provider_once_and_stops_when_fields_resolve(monkeypatch):
    calls = []

    def fake_brazil(lookup, isbn, provider):
        calls.append(provider)
        values = (
            {"subtitle": "Subtítulo CBL", "subjects": ["História"]}
            if provider == "cbl"
            else {"description": "Sinopse Mercado"}
        )
        return providers.candidate(values, "brasilapi", isbn, origin=provider)

    monkeypatch.setattr(providers, "brazil", fake_brazil)
    monkeypatch.setattr(
        providers,
        "openlibrary",
        lambda lookup, isbn: calls.append("openlibrary") or {},
    )
    monkeypatch.setattr(
        providers,
        "google",
        lambda lookup, query, isbn: calls.append("google") or [],
    )

    class FakeLookup:
        def image(self, value):
            return value

    result = providers.enrich_book(
        {
            "isbn": "9788535914849",
            "title": "1984",
            "authors": ["George Orwell"],
            "publisher": "Companhia das Letras",
            "year": "2009",
            "language": "pt",
            "page_count": 416,
            "edition": "1ª ed.",
            "cover_url": "https://res.cloudinary.com/julib/manual.jpg",
            "cover_id": "julib/manual",
            "provenance": {
                "cover_url": {
                    "source": "manual",
                    "source_id": "",
                    "url": "https://res.cloudinary.com/julib/manual.jpg",
                }
            },
        },
        FakeLookup(),
    )

    assert calls == ["openlibrary", "google", "cbl", "mercado-editorial"]
    assert result["subtitle"] == "Subtítulo CBL"
    assert result["description"] == "Sinopse Mercado"
    assert result["subjects"] == ["História"]
    assert result["provenance"]["subtitle"]["source"] == "cbl"
    assert result["provenance"]["description"]["source"] == "mercado-editorial"
    assert result["cover_url"] == "https://res.cloudinary.com/julib/manual.jpg"


def test_enrichment_waits_for_each_fields_higher_priority_source(monkeypatch):
    monkeypatch.setitem(
        providers.FIELD_PRIORITIES,
        "subtitle",
        ("mercado-editorial", "cbl", "openlibrary", "google"),
    )
    calls = []

    def fake_brazil(lookup, isbn, provider):
        calls.append(provider)
        value = "CBL" if provider == "cbl" else "Mercado"
        return providers.candidate(
            {"subtitle": value, "description": value},
            "brasilapi",
            isbn,
            origin=provider,
        )

    monkeypatch.setattr(providers, "brazil", fake_brazil)
    monkeypatch.setattr(providers, "openlibrary", lambda lookup, isbn: {})
    monkeypatch.setattr(providers, "google", lambda lookup, query, isbn: [])

    class FakeLookup:
        def image(self, value):
            return value

    result = providers.enrich_book(
        {
            "isbn": "9788535914849",
            "title": "1984",
            "authors": ["George Orwell"],
            "publisher": "Companhia das Letras",
            "year": "2009",
            "language": "pt",
            "page_count": 416,
            "edition": "1ª ed.",
            "cover_url": "https://res.cloudinary.com/julib/manual.jpg",
            "cover_id": "julib/manual",
            "provenance": {"cover_url": {"source": "manual", "source_id": ""}},
        },
        FakeLookup(),
    )

    assert calls == ["mercado-editorial", "cbl"]
    assert result["subtitle"] == "Mercado"
    assert result["description"] == "CBL"
