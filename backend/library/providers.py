import os
from typing import Any

import httpx
from django.core.exceptions import ValidationError

from .services import normalize_isbn, optional_page_count


def normalized_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        return normalize_isbn(value)
    except ValidationError:
        return ""


def search_books(query: str) -> list[dict[str, Any]]:
    query = query.strip()[:200]
    if len(query) < 2:
        raise ValidationError("Informe pelo menos dois caracteres.")
    raw_isbn = query[5:].strip() if query.lower().startswith("isbn:") else query
    isbn_query = normalized_identifier(raw_isbn)
    if isbn_query:
        query = "isbn:" + isbn_query
    failures = 0
    try:
        response = httpx.get(
            "https://openlibrary.org/search.json",
            params={
                "q": query,
                "limit": 12,
                **(
                    {"fields": "key,title,author_name,isbn,cover_i,first_publish_year"}
                    if isbn_query
                    else {}
                ),
            },
            headers={"User-Agent": "Julib/0.1 (personal-library; marcoandre@gmail.com)"},
            timeout=8,
        )
        response.raise_for_status()
        result = []
        for item in response.json().get("docs", []):
            if isbn_query and not any(
                normalized_identifier(value) == isbn_query for value in item.get("isbn", [])
            ):
                continue
            cover_id = item.get("cover_i")
            result.append(
                {
                    "title": item.get("title", ""),
                    "authors": item.get("author_name", ["Autoria desconhecida"]),
                    "isbn": isbn_query or "",
                    "year": str(item.get("first_publish_year", "")),
                    "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                    if cover_id
                    else "",
                    "source": "openlibrary",
                    "source_id": item.get("key", ""),
                }
            )
        if result:
            return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        failures += 1
    if isbn_query:
        try:
            response = httpx.get(
                "https://brasilapi.com.br/api/isbn/v1/" + isbn_query,
                params={"providers": "cbl,mercado-editorial"},
                headers={"User-Agent": "Julib/0.1 (personal-library; marcoandre@gmail.com)"},
                timeout=8,
            )
            if response.status_code != 404:
                response.raise_for_status()
                data = response.json()
                if normalized_identifier(data.get("isbn", "")) == isbn_query and data.get("title"):
                    return [
                        {
                            "title": data["title"],
                            "authors": data.get("authors") or ["Autoria desconhecida"],
                            "isbn": isbn_query,
                            "publisher": data.get("publisher") or "",
                            "year": str(data.get("year") or ""),
                            "page_count": optional_page_count(data.get("page_count")),
                            "cover_url": "",
                            "source": "brasilapi",
                            "source_id": isbn_query,
                        }
                    ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            failures += 1
    try:
        response = httpx.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": query,
                "maxResults": 12,
                **(
                    {"key": os.environ["GOOGLE_BOOKS_API_KEY"]}
                    if os.environ.get("GOOGLE_BOOKS_API_KEY")
                    else {}
                ),
            },
            timeout=8,
        )
        response.raise_for_status()
        items = []
        for item in response.json().get("items", []):
            info = item.get("volumeInfo", {})
            identifiers = info.get("industryIdentifiers", [])
            isbn = next(
                (
                    normalized_identifier(i.get("identifier", ""))
                    for i in identifiers
                    if i.get("type") in {"ISBN_13", "ISBN_10"}
                    and normalized_identifier(i.get("identifier", ""))
                ),
                "",
            )
            if isbn_query and not any(
                normalized_identifier(i.get("identifier", "")) == isbn_query for i in identifiers
            ):
                continue
            if isbn_query:
                isbn = isbn_query
            items.append(
                {
                    "title": info.get("title", ""),
                    "authors": info.get("authors", ["Autoria desconhecida"]),
                    "isbn": isbn,
                    "publisher": info.get("publisher", ""),
                    "year": info.get("publishedDate", "")[:4],
                    "language": info.get("language", ""),
                    "page_count": optional_page_count(info.get("pageCount")),
                    "cover_url": info.get("imageLinks", {})
                    .get("thumbnail", "")
                    .replace("http:", "https:"),
                    "source": "google",
                    "source_id": item["id"],
                }
            )
        if items:
            return items
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        failures += 1
    if failures:
        raise ValidationError(
            "A busca externa está indisponível. Tente novamente ou cadastre manualmente."
        )
    return []
