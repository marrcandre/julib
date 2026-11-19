import importlib.util
import time
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "backup_cloudinary", Path(__file__).resolve().parents[2] / "scripts/backup.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def resource(public_id, *, asset_id=None, version=7, size=5, fmt="jpg"):
    return {
        "public_id": public_id,
        "asset_id": asset_id or f"asset-{public_id}",
        "version": version,
        "bytes": size,
        "format": fmt,
        "secure_url": "https://res.cloudinary.com/test/image/upload/sample.jpg",
    }


def api_response(resources, remaining=500, reset_at=None):
    class Response(dict):
        rate_limit_remaining = remaining
        rate_limit_allowed = 500
        rate_limit_reset_at = reset_at

    return Response(resources=resources)


def test_metadata_queries_371_ids_in_four_batches_each_pass(monkeypatch):
    import cloudinary.api

    ids = tuple(f"julib/1/book-{index}" for index in range(371))
    requested_batches = []

    def resources_by_ids(public_ids, **_):
        requested_batches.append(tuple(public_ids))
        return api_response([resource(public_id) for public_id in public_ids])

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", resources_by_ids)
    before = backup._cloudinary_metadata(ids)
    expected = {public_id: backup._cloudinary_fingerprint(resource(public_id)) for public_id in ids}
    backup._assert_cloudinary_unchanged(expected)

    assert len(requested_batches) == 8
    assert [len(batch) for batch in requested_batches] == [100, 100, 100, 71] * 2
    assert set(before) == set(ids)


@pytest.mark.parametrize(
    "resources, message",
    [
        ([], "ausente"),
        ([resource("julib/1/one"), resource("julib/1/one")], "duplicada"),
        ([resource("julib/1/other")], "inesperada"),
        ([{"public_id": "julib/1/one", "asset_id": "a"}], "verificável"),
    ],
)
def test_metadata_batch_rejects_incomplete_duplicate_unexpected_or_invalid(
    monkeypatch, resources, message
):
    import cloudinary.api

    monkeypatch.setattr(
        cloudinary.api,
        "resources_by_ids",
        lambda *_args, **_kwargs: api_response(resources),
    )
    with pytest.raises((RuntimeError, TypeError), match=message):
        backup._cloudinary_metadata(("julib/1/one",))


@pytest.mark.parametrize(
    "error_type, message",
    [
        ("AuthorizationRequired", "autenticação"),
        ("NotAllowed", "autorização"),
        ("NotFound", "ausente"),
    ],
)
def test_permanent_cloudinary_errors_fail_without_retry(monkeypatch, error_type, message):
    import cloudinary.api
    import cloudinary.exceptions

    calls = []
    exception = getattr(cloudinary.exceptions, error_type)("sensitive-provider-detail")

    def fail(*_args, **_kwargs):
        calls.append(1)
        raise exception

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", fail)
    with pytest.raises(RuntimeError, match=message) as error:
        backup._cloudinary_metadata(("julib/1/one",))
    assert len(calls) == 1
    assert "sensitive-provider-detail" not in str(error.value)


@pytest.mark.parametrize("status", [420, 429])
def test_rate_limit_retries_once_after_advertised_reset(monkeypatch, status):
    import cloudinary.api
    import cloudinary.exceptions

    now = 2_000_000_000
    sleeps = []
    calls = []
    reset = time.gmtime(now + 4)

    ids = tuple(f"julib/1/book-{index}" for index in range(101))

    def resources_by_ids(public_ids, **_):
        calls.append(tuple(public_ids))
        if len(calls) == 1:
            return api_response(
                [resource(public_id) for public_id in public_ids], remaining=1, reset_at=reset
            )
        if len(calls) == 2:
            raise cloudinary.exceptions.RateLimited(f"Error {status} - secret")
        return api_response([resource(public_id) for public_id in public_ids])

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", resources_by_ids)
    monkeypatch.setattr(backup.time, "time", lambda: now)
    monkeypatch.setattr(backup.time, "sleep", sleeps.append)
    budget = {"calls_remaining": 2, "remaining": None, "reset_at": None, "allowed": None}
    result = backup._cloudinary_metadata(ids, rate_budget=budget)

    assert set(result) == set(ids)
    assert len(calls) == 3
    assert sleeps == [4]


def test_rate_limit_reset_beyond_max_wait_fails_closed(monkeypatch):
    import cloudinary.api

    now = 2_000_000_000
    sleeps = []
    calls = []
    monkeypatch.setattr(backup.time, "time", lambda: now)
    monkeypatch.setattr(backup.time, "sleep", sleeps.append)
    ids = tuple(f"julib/1/book-{index}" for index in range(101))

    def resources_by_ids(public_ids, **_):
        calls.append(tuple(public_ids))
        return api_response(
            [resource(public_id) for public_id in public_ids],
            remaining=0,
            reset_at=time.gmtime(now + backup.CLOUDINARY_MAX_RATE_WAIT_SECONDS + 1),
        )

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", resources_by_ids)
    budget = {"calls_remaining": 2, "remaining": None, "reset_at": None, "allowed": None}

    with pytest.raises(RuntimeError, match="limite de espera"):
        backup._cloudinary_metadata(ids, rate_budget=budget)
    assert len(calls) == 1
    assert sleeps == []


def test_combined_rate_wait_budget_fails_before_exceeding_total(monkeypatch):
    now = 2_000_000_000
    sleeps = []
    budget = {
        "remaining": None,
        "reset_at": time.gmtime(now + 4),
        "wait_seconds_remaining": 3,
    }
    monkeypatch.setattr(backup.time, "time", lambda: now)
    monkeypatch.setattr(backup.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="orçamento total"):
        backup._wait_for_cloudinary_reset(budget)
    assert sleeps == []
    assert budget["wait_seconds_remaining"] == 3


def test_rate_limit_uses_retry_after_when_sdk_error_exposes_it(monkeypatch):
    import cloudinary.api
    import cloudinary.exceptions

    now = 2_000_000_000
    calls = []
    sleeps = []
    rate_error = cloudinary.exceptions.RateLimited("rate limited")
    rate_error.headers = {"Retry-After": "7"}

    def resources_by_ids(public_ids, **_):
        calls.append(tuple(public_ids))
        if len(calls) == 1:
            return api_response([resource(public_id) for public_id in public_ids])
        if len(calls) == 2:
            raise rate_error
        return api_response([resource(public_id) for public_id in public_ids])

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", resources_by_ids)
    monkeypatch.setattr(backup.time, "time", lambda: now)
    monkeypatch.setattr(backup.time, "sleep", sleeps.append)
    budget = {"calls_remaining": 2, "remaining": None, "reset_at": None, "allowed": None}
    ids = tuple(f"julib/1/book-{index}" for index in range(101))

    assert set(backup._cloudinary_metadata(ids, rate_budget=budget)) == set(ids)
    assert len(calls) == 3
    assert sleeps == [7.0]


@pytest.mark.parametrize("status", [420, 429])
def test_rate_limit_without_reset_uses_only_bounded_fallback_retries(monkeypatch, status):
    import cloudinary.api
    import cloudinary.exceptions

    calls = []
    sleeps = []

    def rate_limited(*_args, **_kwargs):
        calls.append(1)
        raise cloudinary.exceptions.RateLimited(f"Error {status} - private detail")

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", rate_limited)
    monkeypatch.setattr(backup.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="persistiu") as error:
        backup._cloudinary_metadata(("julib/1/one",))
    assert len(calls) == backup.CLOUDINARY_MAX_ATTEMPTS
    assert sleeps == [1, 2]
    assert "private detail" not in str(error.value)


def test_invalid_admin_api_response_shape_fails_immediately(monkeypatch):
    import cloudinary.api

    calls = []
    monkeypatch.setattr(
        cloudinary.api,
        "resources_by_ids",
        lambda *_args, **_kwargs: calls.append(1) or {"resources": None},
    )
    with pytest.raises(TypeError, match="Resposta inválida"):
        backup._cloudinary_metadata(("julib/1/one",))
    assert len(calls) == 1


def test_invalid_json_response_fails_without_transient_retries(monkeypatch):
    import cloudinary.api
    import cloudinary.exceptions

    calls = []
    monkeypatch.setattr(
        cloudinary.api,
        "resources_by_ids",
        lambda *_args, **_kwargs: (
            calls.append(1)
            or (_ for _ in ()).throw(
                cloudinary.exceptions.GeneralError("Error parsing server response")
            )
        ),
    )
    with pytest.raises(RuntimeError, match="Falha não transitória"):
        backup._cloudinary_metadata(("julib/1/one",))
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["timeout", "network", "server"])
def test_transient_cloudinary_errors_retry_a_bounded_number_of_times(monkeypatch, failure):
    import cloudinary.api
    import cloudinary.exceptions

    calls = []
    sleeps = []

    def resources_by_ids(public_ids, **_):
        calls.append(tuple(public_ids))
        if len(calls) < 3:
            detail = {
                "timeout": "timed out",
                "network": "socket failure",
                "server": "Error 503 - internal detail",
            }[failure]
            raise cloudinary.exceptions.GeneralError(detail)
        return api_response([resource(public_id) for public_id in public_ids])

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", resources_by_ids)
    monkeypatch.setattr(backup.time, "sleep", sleeps.append)
    assert set(backup._cloudinary_metadata(("julib/1/one",))) == {"julib/1/one"}
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_persistent_transient_error_stops_after_maximum_attempts(monkeypatch):
    import cloudinary.api
    import cloudinary.exceptions

    calls = []
    sleeps = []

    def unavailable(*_args, **_kwargs):
        calls.append(1)
        raise cloudinary.exceptions.GeneralError("socket timed out")

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", unavailable)
    monkeypatch.setattr(backup.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="Falha não transitória"):
        backup._cloudinary_metadata(("julib/1/one",))
    assert len(calls) == backup.CLOUDINARY_MAX_ATTEMPTS
    assert sleeps == [1, 2]


@pytest.mark.parametrize(
    "field, changed",
    [
        ("asset_id", "replacement-asset"),
        ("version", 8),
        ("bytes", 6),
        ("format", "png"),
    ],
)
def test_post_download_batch_detects_each_metadata_change(monkeypatch, field, changed):
    import cloudinary.api

    original = resource("julib/1/one")
    current = dict(original, **{field: changed})
    monkeypatch.setattr(
        cloudinary.api,
        "resources_by_ids",
        lambda *_args, **_kwargs: api_response([current]),
    )
    expected = {"julib/1/one": backup._cloudinary_fingerprint(original)}

    with pytest.raises(RuntimeError, match="mudou durante a cópia"):
        backup._assert_cloudinary_unchanged(expected)


def test_missing_media_during_post_download_check_aborts_without_artifact(monkeypatch, tmp_path):
    import cloudinary.api
    import httpx

    calls = []

    def resources_by_ids(public_ids, **_):
        calls.append(tuple(public_ids))
        return api_response([resource("julib/1/one")]) if len(calls) == 1 else api_response([])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def raise_for_status(self):
            return None

        def iter_bytes(self, _):
            yield b"image"

    class Client:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def stream(self, method, url):
            assert method == "GET"
            assert url.startswith("https://res.cloudinary.com/")
            return Response()

    monkeypatch.setattr(cloudinary.api, "resources_by_ids", resources_by_ids)
    monkeypatch.setattr(httpx, "Client", Client)
    _, public = backup.keypair()
    public_path = tmp_path / "public.pem"
    public_path.write_bytes(public)
    output = tmp_path / "backup.enc"

    monkeypatch.setattr(backup, "require_disk_space", lambda *_: None)
    monkeypatch.setattr(backup, "shutil_disk_free", lambda _: 10_000_000)
    monkeypatch.setattr(backup, "dump_database", lambda _url, path, *_: path.write_bytes(b"dump"))
    monkeypatch.setattr(backup, "_media_ids", lambda _: ("julib/1/one",))
    monkeypatch.setenv("BACKUP_DATABASE_URL", "postgresql://reader:secret@localhost/db")
    monkeypatch.setenv("BACKUP_MAX_BYTES", "1048576")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    monkeypatch.setattr(django, "setup", lambda: None)
    import library.media

    monkeypatch.setattr(library.media, "configure", lambda: None)

    with pytest.raises(RuntimeError, match="incompleta"):
        backup.backup(output, public_path, with_media=True)
    assert not output.exists()
    assert not list(tmp_path.glob(".backup.enc.*.tmp"))
