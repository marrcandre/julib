"""Book discovery and bounded, exact-edition enrichment without database writes."""

import copy
import hashlib
import json
import os
import re
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from django.core.cache import cache
from django.core.exceptions import ValidationError

from .book_http import bounded_get
from .services import normalize_isbn, optional_page_count

HEADERS = {"User-Agent": "Julib/0.1 (personal-library; marcoandre@gmail.com)"}
FIELDS = ("title", "authors", "publisher", "year", "language", "page_count", "edition")
IMAGE_HOSTS = {
    "books.google.com",
    "books.googleusercontent.com",
    "covers.openlibrary.org",
    "res.cloudinary.com",
    "storage.googleapis.com",
    "api.mercadoeditorial.org",
    "images.mercadoeditorial.org",
    "cdn.mercadoeditorial.org",
    "images-na.ssl-images-amazon.com",
    "images-eu.ssl-images-amazon.com",
}


def normalized_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        return normalize_isbn(value)
    except ValidationError:
        return ""


class Lookup:
    def __init__(self) -> None:
        self.deadline = time.monotonic() + 18
        self.failures = 0

    def json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        key = (
            "books:v2:"
            + hashlib.sha256(json.dumps([url, params], sort_keys=True).encode()).hexdigest()
        )
        saved = cache.get(key)
        if isinstance(saved, dict):
            return copy.deepcopy(saved)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.failures += 1
            return {}
        if "googleapis.com" in url and os.environ.get("GOOGLE_BOOKS_API_KEY"):
            params = {**params, "key": os.environ["GOOGLE_BOOKS_API_KEY"]}
        try:
            response = bounded_get(
                url,
                params=params,
                headers=HEADERS,
                timeout=min(4, remaining),
                deadline=self.deadline,
                max_bytes=1024 * 1024,
            )
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            value = response.json()
            if not isinstance(value, dict):
                return {}
            if (
                value.get("items")
                or value.get("docs")
                or value.get("title")
                or any(k.startswith("ISBN:") for k in value)
            ):
                cache.set(key, value, 300)
            return value
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            self.failures += 1
            return {}

    def image(self, value: Any) -> str:
        url = safe_image_url(value)
        if not url:
            return ""
        key = "book-image:v3:" + hashlib.sha256(url.encode()).hexdigest()
        saved = cache.get(key)
        if isinstance(saved, str) and safe_image_url(saved):
            return saved
        for _ in range(3):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                return ""
            try:
                response = bounded_get(
                    url,
                    headers=HEADERS,
                    timeout=min(4, remaining),
                    deadline=self.deadline,
                    max_bytes=5 * 1024 * 1024,
                    follow_redirects=False,
                )
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = safe_image_url(urljoin(url, response.headers.get("location", "")))
                    if not url:
                        return ""
                    continue
                if (
                    response.status_code == 200
                    and response.headers.get("content-type", "").lower().startswith("image/")
                    and 64 <= len(response.content) <= 5 * 1024 * 1024
                ):
                    cache.set(key, url, 300)
                    return url
            except (httpx.HTTPError, ValueError):
                return ""
            return ""
        return ""


def safe_image_url(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    url = value.replace("http:", "https:", 1)
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not (
                parsed.hostname in IMAGE_HOSTS
                or (
                    (parsed.hostname == "archive.org" and parsed.path.startswith("/download/"))
                    or (
                        re.fullmatch(r"ia[0-9]+\.(?:us|eu)\.archive\.org", parsed.hostname or "")
                        and (
                            parsed.path.startswith("/download/")
                            or parsed.path == "/view_archive.php"
                        )
                    )
                )
            )
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
        ):
            return ""
    except ValueError:
        return ""
    return (
        str(httpx.URL(url).copy_set_param("default", "false"))
        if parsed.hostname == "covers.openlibrary.org"
        else url
    )


def objects(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def strings(value: Any) -> list[str]:
    return (
        [v.strip() for v in value if isinstance(v, str) and v.strip()]
        if isinstance(value, list)
        else []
    )


def edition_data(data: dict[str, Any]) -> dict[str, Any]:
    """Read a single edition, never aggregate work-level bibliographic fields."""
    identifiers = [
        normalized_identifier(value)
        for value in strings(data.get("isbn_13")) + strings(data.get("isbn_10"))
    ]
    languages = []
    codes = {
        "por": "pt",
        "eng": "en",
        "spa": "es",
        "fre": "fr",
        "fra": "fr",
        "ger": "de",
        "deu": "de",
        "ita": "it",
        "jpn": "ja",
    }
    for item in objects(data.get("languages")):
        key = item.get("key")
        if isinstance(key, str) and re.fullmatch(r"/languages/[a-z]{3}", key):
            code = key.rsplit("/", 1)[-1]
            languages.append(codes.get(code, code))
    date = re.search(r"\b\d{4}\b", str(data.get("publish_date") or ""))
    covers = data.get("covers")
    cover_id = (
        next((c for c in covers if type(c) is int and c > 0), None)
        if isinstance(covers, list)
        else None
    )
    return candidate(
        {
            "title": data.get("title") if isinstance(data.get("title"), str) else "",
            "authors": ["Autoria desconhecida"],
            "isbn": next((value for value in identifiers if value), ""),
            "publisher": "; ".join(strings(data.get("publishers"))),
            "year": date.group() if date else "",
            "page_count": optional_page_count(data.get("number_of_pages")),
            "language": "; ".join(dict.fromkeys(languages)),
            "edition": data.get("edition_name")
            if isinstance(data.get("edition_name"), str)
            else "",
            "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg?default=false"
            if cover_id
            else "",
        },
        "openlibrary",
        str(data.get("key") or ""),
    )


def candidate(
    data: dict[str, Any], source: str, identifier: str, origin: str | None = None
) -> dict[str, Any]:
    data = {**data, "source": source, "source_id": identifier}
    data["provenance"] = {
        field: {
            "source": origin or source,
            "source_id": identifier,
            **({"url": data[field]} if field == "cover_url" else {}),
        }
        for field in (*FIELDS, "cover_url")
        if data.get(field)
    }
    return data


def google(lookup: Lookup, query: str, isbn: str) -> list[dict[str, Any]]:
    response = lookup.json(
        "https://www.googleapis.com/books/v1/volumes", {"q": query, "maxResults": 12}
    )
    results = []
    for item in objects(response.get("items")):
        if not isinstance(item, dict) or not isinstance(item.get("volumeInfo"), dict):
            continue
        info = item["volumeInfo"]
        identifiers = {
            normalized_identifier(i.get("identifier"))
            for i in objects(info.get("industryIdentifiers"))
            if isinstance(i, dict)
        } - {""}
        if isbn and isbn not in identifiers:
            continue
        if not info.get("title") or not item.get("id"):
            continue
        images = info.get("imageLinks") or {}
        if not isinstance(images, dict):
            images = {}
        cover = next(
            (
                images[k]
                for k in ("large", "medium", "small", "thumbnail", "smallThumbnail")
                if isinstance(images.get(k), str)
            ),
            "",
        )
        results.append(
            candidate(
                {
                    "title": info["title"],
                    "authors": strings(info.get("authors")) or ["Autoria desconhecida"],
                    "isbn": isbn or next(iter(sorted(identifiers)), ""),
                    "publisher": info.get("publisher") or "",
                    "year": str(info.get("publishedDate") or "")[:4],
                    "language": info.get("language") or "",
                    "page_count": optional_page_count(info.get("pageCount")),
                    "cover_url": cover.replace("http:", "https:", 1),
                },
                "google",
                str(item["id"]),
            )
        )
    return results


def brazil(lookup: Lookup, isbn: str, provider: str) -> dict[str, Any]:
    data = lookup.json("https://brasilapi.com.br/api/isbn/v1/" + isbn, {"providers": provider})
    if normalized_identifier(data.get("isbn")) != isbn or not data.get("title"):
        return {}
    return candidate(
        {
            "title": data["title"],
            "authors": strings(data.get("authors")) or ["Autoria desconhecida"],
            "isbn": isbn,
            "publisher": data.get("publisher") or "",
            "year": str(data.get("year") or ""),
            "page_count": optional_page_count(data.get("page_count")),
            "cover_url": data.get("cover_url") or "",
        },
        "brasilapi",
        isbn,
        data.get("provider") if data.get("provider") in {"cbl", "mercado-editorial"} else provider,
    )


def openlibrary(lookup: Lookup, isbn: str) -> dict[str, Any]:
    response = lookup.json(
        "https://openlibrary.org/api/books",
        {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
    )
    data = response.get(f"ISBN:{isbn}")
    if not isinstance(data, dict):
        data = {}
    detail_response = lookup.json(
        "https://openlibrary.org/api/books",
        {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "details"},
    )
    entry = detail_response.get(f"ISBN:{isbn}")
    detail = entry.get("details", {}) if isinstance(entry, dict) else {}
    if not isinstance(detail, dict):
        detail = {}
    identifiers = {
        normalized_identifier(value)
        for value in strings(detail.get("isbn_13")) + strings(detail.get("isbn_10"))
    }
    extra = edition_data(detail) if isbn in identifiers else {}
    if not data.get("title"):
        return extra if extra.get("title") else {}
    cover = data.get("cover") or {}
    publishers = objects(data.get("publishers"))
    date = re.search(r"\b\d{4}\b", str(data.get("publish_date") or ""))
    result = candidate(
        {
            "title": data["title"],
            "authors": [
                x["name"]
                for x in objects(data.get("authors"))
                if isinstance(x, dict) and isinstance(x.get("name"), str)
            ]
            or ["Autoria desconhecida"],
            "isbn": isbn,
            "publisher": next(
                (
                    x["name"]
                    for x in publishers
                    if isinstance(x, dict) and isinstance(x.get("name"), str)
                ),
                "",
            ),
            "year": date.group() if date else "",
            "page_count": optional_page_count(data.get("number_of_pages")),
            "cover_url": (cover.get("large") or cover.get("medium") or cover.get("small") or "")
            if isinstance(cover, dict)
            else "",
        },
        "openlibrary",
        str(data.get("key") or f"ISBN:{isbn}"),
    )

    for field in FIELDS:
        if not result.get(field) and extra.get(field):
            result[field] = extra[field]
            result["provenance"][field] = extra["provenance"][field]
    if not result.get("cover_url") and extra.get("cover_url"):
        result["cover_url"] = extra["cover_url"]
        result["provenance"]["cover_url"] = extra["provenance"]["cover_url"]
    return result


def missing(value: Any) -> bool:
    return not value or value == ["Autoria desconhecida"]


def complete(data: dict[str, Any]) -> bool:
    return all(
        not missing(data.get(field))
        for field in (
            "title",
            "authors",
            "publisher",
            "year",
            "language",
            "page_count",
            "edition",
            "cover_url",
        )
    )


def fill(result: dict[str, Any], extra: dict[str, Any], lookup: Lookup) -> None:
    origins = result.setdefault("provenance", {})
    for field in FIELDS:
        if missing(result.get(field)) and not missing(extra.get(field)):
            result[field] = extra[field]
            origins[field] = extra.get("provenance", {}).get(field, {})
        elif (
            not missing(result.get(field))
            and not missing(extra.get(field))
            and result[field] != extra[field]
        ):
            origin = origins.setdefault(
                field,
                {
                    "source": result.get("source", "manual"),
                    "source_id": result.get("source_id", ""),
                },
            )
            source = (
                extra.get("provenance", {}).get(field, {}).get("source", extra.get("source", ""))
            )
            value = "; ".join(extra[field]) if isinstance(extra[field], list) else str(extra[field])
            alternative = f"{source}: {value[:300]}"
            alternatives = origin.setdefault("alternatives", [])
            if alternative not in alternatives and len(alternatives) < 4:
                alternatives.append(alternative)
    if not result.get("cover_url") and extra.get("cover_url"):
        image = lookup.image(extra["cover_url"])
        if image:
            result["cover_url"] = image
            origins["cover_url"] = {
                **extra.get("provenance", {}).get("cover_url", {}),
                "url": image,
            }


def enrich_book(base: dict[str, Any], lookup: Lookup | None = None) -> dict[str, Any]:
    """Only server-fetched API images are probed, never URLs from the caller."""
    lookup = lookup or Lookup()
    result = copy.deepcopy(base)
    isbn = normalized_identifier(result.get("isbn"))
    if not isbn:
        return result
    result["isbn"] = isbn
    origins = result.setdefault("provenance", {})
    own_cover = result.get("cover_url") and (
        origins.get("cover_url", {}).get("source") == "manual"
        or result.get("cover_id")
        or (
            urlsplit(result["cover_url"]).hostname == "res.cloudinary.com"
            and not origins.get("cover_url")
        )
    )
    if not own_cover:
        result["cover_url"] = ""
        origins.pop("cover_url", None)
    sources = [
        lambda: brazil(lookup, isbn, "cbl"),
        lambda: brazil(lookup, isbn, "mercado-editorial"),
        lambda: openlibrary(lookup, isbn),
        lambda: next(iter(google(lookup, "isbn:" + isbn, isbn)), {}),
    ]
    for get in sources:
        extra = get()
        if extra:
            if not result.get("source"):
                result.update(source=extra["source"], source_id=extra["source_id"])
            fill(result, extra, lookup)
        if complete(result):
            break
    return result


def search_books(query: str) -> list[dict[str, Any]]:
    query = query.strip()[:200]
    if len(query) < 2:
        raise ValidationError("Informe pelo menos dois caracteres.")
    raw_isbn = query[5:].strip() if query.lower().startswith("isbn:") else query
    isbn = normalized_identifier(raw_isbn)
    lookup = Lookup()
    if isbn:
        result = enrich_book({"isbn": isbn}, lookup)
        if result.get("title"):
            return [result]
    else:
        response = lookup.json(
            "https://openlibrary.org/search.json",
            {
                "q": query,
                "limit": 12,
                "lang": "pt",
                "fields": "key,title,author_name,author_key,cover_i,editions,editions.key",
            },
        )
        # Reserve Google's discovery request before fetching edition details.
        google_results = google(lookup, query, "")
        results = []
        detail_requests = 0
        for item in objects(response.get("docs")):
            if not isinstance(item.get("title"), str) or not item["title"]:
                continue
            editions = item.get("editions")
            found = False
            for entry in objects(editions.get("docs") if isinstance(editions, dict) else None):
                key = entry.get("key")
                if (
                    detail_requests >= 4
                    or not isinstance(key, str)
                    or not re.fullmatch(r"/books/OL[0-9]+M", key)
                ):
                    continue
                detail_requests += 1
                detail = lookup.json("https://openlibrary.org" + key + ".json", {})
                if (
                    detail.get("key") != key
                    or not isinstance(detail.get("title"), str)
                    or not detail["title"]
                ):
                    continue
                result = edition_data(detail)
                # Work authors are only a fallback; an edition may credit different authors.
                author_keys = [
                    author["key"]
                    for author in objects(detail.get("authors"))
                    if isinstance(author.get("key"), str)
                    and re.fullmatch(r"/authors/OL[0-9]+A", author["key"])
                ]
                work_authors = item.get("author_key")
                if (
                    author_keys
                    and isinstance(work_authors, list)
                    and set(author_keys)
                    != {f"/authors/{k}" for k in work_authors if isinstance(k, str)}
                ):
                    result["authors"] = ["Autoria desconhecida"]
                else:
                    result["authors"] = strings(item.get("author_name")) or ["Autoria desconhecida"]
                result["provenance"]["authors"] = {
                    "source": "openlibrary",
                    "source_id": str(item.get("key") or ""),
                }
                results.append(result)
                found = True
            if not found:
                cover_id = item.get("cover_i")
                results.append(
                    candidate(
                        {
                            "title": item["title"],
                            "authors": strings(item.get("author_name")) or ["Autoria desconhecida"],
                            "isbn": "",
                            "year": "",
                            "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg?default=false"
                            if type(cover_id) is int and cover_id > 0
                            else "",
                        },
                        "openlibrary",
                        str(item.get("key") or ""),
                    )
                )
        unique = []
        seen = set()
        for result in results + google_results:
            identity = result.get("isbn") or (result["source"], result["source_id"])
            if identity not in seen:
                unique.append(result)
                seen.add(identity)
        if unique:
            return unique[:24]
    if lookup.failures:
        raise ValidationError(
            "A busca externa está indisponível. Tente novamente ou cadastre manualmente."
        )
    return []
