"""Bound external lookups while streaming, including an overall wall-clock deadline."""

import asyncio
import time
from typing import Any

import httpx


class BoundedReadError(httpx.HTTPError):
    pass


async def read_response(
    url: str,
    *,
    params: dict[str, Any] | None,
    headers: dict[str, str],
    timeout: float,
    deadline: float,
    max_bytes: int,
) -> httpx.Response:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BoundedReadError("External lookup timed out")
    try:
        async with asyncio.timeout(remaining):
            # Raw identity streams avoid decompression allocating data beyond the cap.
            async with httpx.AsyncClient(
                headers={**headers, "Accept-Encoding": "identity"},
                timeout=min(timeout, remaining),
                follow_redirects=False,
            ) as client:
                async with client.stream("GET", url, params=params) as response:
                    if response.headers.get("content-encoding", "identity").lower() not in {
                        "identity",
                        "",
                    }:
                        raise BoundedReadError("Unsupported external response encoding")
                    length = response.headers.get("content-length", "")
                    if length.isdigit() and int(length) > max_bytes:
                        raise BoundedReadError("External response exceeded limit")
                    body = bytearray()
                    async for chunk in response.aiter_raw(chunk_size=65536):
                        if len(body) + len(chunk) > max_bytes:
                            raise BoundedReadError("External response exceeded limit")
                        body.extend(chunk)
                    return httpx.Response(
                        response.status_code,
                        headers=response.headers,
                        content=bytes(body),
                        request=response.request,
                    )
    except TimeoutError:
        raise BoundedReadError("External lookup timed out") from None


def bounded_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str],
    timeout: float,
    deadline: float,
    max_bytes: int,
    follow_redirects: bool = False,
) -> httpx.Response:
    if follow_redirects:
        raise BoundedReadError("Redirects must be validated by the caller")
    return asyncio.run(
        read_response(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            deadline=deadline,
            max_bytes=max_bytes,
        )
    )
