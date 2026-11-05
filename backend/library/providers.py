import os
from typing import Any

import httpx
from django.core.exceptions import ValidationError

from .services import optional_page_count


def search_books(query: str) -> list[dict[str, Any]]:
    query = query.strip()[:200]
    if len(query) < 2:
        raise ValidationError("Informe pelo menos dois caracteres.")
    failures = 0
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
            isbn = next((i["identifier"] for i in identifiers if i["type"] == "ISBN_13"), "")
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
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        failures += 1
    try:
        response = httpx.get(
            "https://openlibrary.org/search.json",
            params={"q": query, "limit": 12},
            headers={"User-Agent": "Julib/0.1 (personal-library; marcoandre@gmail.com)"},
            timeout=8,
        )
        response.raise_for_status()
        result = []
        for item in response.json().get("docs", []):
            cover_id = item.get("cover_i")
            result.append(
                {
                    "title": item.get("title", ""),
                    "authors": item.get("author_name", ["Autoria desconhecida"]),
                    "isbn": "",
                    "year": str(item.get("first_publish_year", "")),
                    "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                    if cover_id
                    else "",
                    "source": "openlibrary",
                    "source_id": item.get("key", ""),
                }
            )
        return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        failures += 1
    if failures:
        raise ValidationError(
            "A busca externa está indisponível. Tente novamente ou cadastre manualmente."
        )
    return []
