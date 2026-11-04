"""Conservative cover lookup without changing the book's import identity."""

import os
import re
import unicodedata
from urllib.parse import urlsplit

import httpx
from django.core.exceptions import ValidationError

from .services import normalize_isbn


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", value.lower())


def data(client: httpx.Client, url: str, params: dict[str, str | int]) -> dict:
    if url == "https://www.googleapis.com/books/v1/volumes" and os.environ.get(
        "GOOGLE_BOOKS_API_KEY"
    ):
        params = {**params, "key": os.environ["GOOGLE_BOOKS_API_KEY"]}
    try:
        response = client.get(url, params=params, timeout=8)
        response.raise_for_status()
        result = response.json()
        return result if isinstance(result, dict) else {}
    except (httpx.HTTPError, ValueError):
        return {}


def usable(client: httpx.Client, url: str) -> str:
    url = url.replace("http:", "https:", 1)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "books.google.com",
        "books.googleusercontent.com",
        "covers.openlibrary.org",
    }:
        return ""
    try:
        response = client.get(url, timeout=8, follow_redirects=False)
        if (
            response.status_code == 200
            and response.headers.get("content-type", "").startswith("image/")
            and response.content
        ):
            return url
    except httpx.HTTPError:
        pass
    return ""


def same_book(info: dict, isbn: str, title: str, authors: list[str]) -> bool:
    if isbn:
        for identifier in info.get("industryIdentifiers", []):
            try:
                if normalize_isbn(identifier.get("identifier", "")) == isbn:
                    return True
            except ValidationError:
                continue
        return False
    return normalized(info.get("title", "")) == normalized(title) and bool(
        {normalized(a) for a in authors} & {normalized(a) for a in info.get("authors", [])}
    )


def lookup_cover(client: httpx.Client, isbn: str, title: str, authors: list[str]) -> str:
    query = (
        f"isbn:{isbn}" if isbn else f'intitle:"{title}" inauthor:"{authors[0] if authors else ""}"'
    )
    response = data(
        client, "https://www.googleapis.com/books/v1/volumes", {"q": query[:200], "maxResults": 12}
    )
    candidates = {
        item.get("volumeInfo", {}).get("imageLinks", {}).get("thumbnail", "")
        for item in response.get("items", [])
        if same_book(item.get("volumeInfo", {}), isbn, title, authors)
    } - {""}
    if candidates and (isbn or len(candidates) == 1):
        for url in sorted(candidates):
            if cover := usable(client, url):
                return cover
    if isbn:
        response = data(
            client,
            "https://openlibrary.org/api/books",
            {
                "bibkeys": f"ISBN:{isbn}",
                "format": "json",
                "jscmd": "data",
            },
        )
        cover = response.get(f"ISBN:{isbn}", {}).get("cover", {})
        return usable(client, cover.get("large") or cover.get("medium") or "")
    response = data(
        client,
        "https://openlibrary.org/search.json",
        {
            "title": title,
            "author": authors[0] if authors else "",
            "limit": 10,
            "fields": "title,author_name,cover_i",
        },
    )
    covers = {
        item["cover_i"]
        for item in response.get("docs", [])
        if item.get("cover_i")
        and same_book(
            {"title": item.get("title", ""), "authors": item.get("author_name", [])},
            "",
            title,
            authors,
        )
    }
    if len(covers) == 1:
        return usable(client, f"https://covers.openlibrary.org/b/id/{covers.pop()}-L.jpg")
    return ""
