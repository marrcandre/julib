import asyncio
import time

import httpx
import pytest

from library.book_http import BoundedReadError, bounded_get


class Body(httpx.AsyncByteStream):
    def __init__(self, slow=False):
        self.slow = slow
        self.chunks = 0
        self.closed = False

    async def __aiter__(self):
        for _ in range(10):
            self.chunks += 1
            if self.slow:
                await asyncio.sleep(1)
            yield b"x" * 65536

    async def aclose(self):
        self.closed = True


def transport(monkeypatch, body, headers=None):
    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, stream=body, headers=headers or {})
            ),
            **kwargs,
        ),
    )


def test_oversized_stream_stops_before_full_body_is_downloaded(monkeypatch):
    body = Body()
    transport(monkeypatch, body)
    with pytest.raises(BoundedReadError):
        bounded_get(
            "https://covers.openlibrary.org/image",
            headers={},
            timeout=1,
            deadline=time.monotonic() + 1,
            max_bytes=70000,
        )
    assert body.closed and body.chunks == 2


def test_slow_trickle_is_cancelled_by_overall_deadline(monkeypatch):
    body = Body(slow=True)
    transport(monkeypatch, body)
    start = time.monotonic()
    with pytest.raises(BoundedReadError):
        bounded_get(
            "https://covers.openlibrary.org/image",
            headers={},
            timeout=4,
            deadline=start + 0.04,
            max_bytes=70000,
        )
    assert time.monotonic() - start < 0.4 and body.closed


def test_oversized_content_length_is_rejected_before_read(monkeypatch):
    body = Body()
    transport(monkeypatch, body, {"content-length": "9999999"})
    with pytest.raises(BoundedReadError):
        bounded_get(
            "https://covers.openlibrary.org/image",
            headers={},
            timeout=1,
            deadline=time.monotonic() + 1,
            max_bytes=100,
        )
    assert body.chunks == 0 and body.closed
