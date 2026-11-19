"""Book discovery and bounded, exact-edition enrichment without database writes."""

import copy
import hashlib
import json
import os
import re
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from django.core.cache import cache
from django.core.exceptions import ValidationError

from .book_http import bounded_get
from .isbn_ranges import isbn_region as _isbn_region
from .metadata import (
    DESCRIPTION_MAX_LENGTH,
    SUBTITLE_MAX_LENGTH,
    normalize_subjects,
)
from .services import normalize_isbn, optional_page_count

HEADERS = {"User-Agent": "Julib/0.1 (personal-library; marcoandre@gmail.com)"}
FIELDS = ("title", "authors", "publisher", "year", "language", "page_count", "edition")
METADATA_FIELDS = (*FIELDS, "subtitle", "description", "subjects")
PROVIDER_PRIORITIES = {
    "brazil": ("cbl", "mercado-editorial", "openlibrary", "google"),
    "international": ("openlibrary", "google", "cbl", "mercado-editorial"),
}
FIELD_PRIORITIES = {
    field: {region: priorities for region, priorities in PROVIDER_PRIORITIES.items()}
    for field in (*METADATA_FIELDS, "cover_url")
}
FIELD_LIMITS = {"subtitle": SUBTITLE_MAX_LENGTH, "description": DESCRIPTION_MAX_LENGTH}
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


def isbn_region(value: Any) -> str:
    return _isbn_region(value) if isinstance(value, str) else ""


class _DescriptionText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
        elif not self._skip_depth and tag in {"p", "div", "br", "li"}:
            self.parts.append("\n\n" if tag in {"p", "div", "li"} else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and tag in {"p", "div", "li"}:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def bounded_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if len(value) <= limit else ""


def plain_description(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value")
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = _DescriptionText()
    try:
        parser.feed(value)
        parser.close()
    except ValueError:
        return ""
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return bounded_text(text, FIELD_LIMITS["description"])


class Lookup:
    def __init__(self) -> None:
        self.deadline = time.monotonic() + 18
        self.failures = 0
        self.providers_queried: list[str] = []
        self.provider_failures: dict[str, int] = {}
        self.provider_outcomes: dict[str, str] = {}
        self.isbn_mismatches: set[str] = set()

    def _provider(self, url: str, params: dict[str, Any]) -> str:
        if "googleapis.com" in url:
            name = "google"
        elif "brasilapi.com.br" in url:
            name = str(params.get("providers") or "")
        elif "openlibrary.org" in url:
            name = "openlibrary"
        else:
            name = ""
        if name and name not in self.providers_queried:
            self.providers_queried.append(name)
        return name

    def json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        provider = self._provider(url, params)
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
            if provider:
                self.provider_failures[provider] = self.provider_failures.get(provider, 0) + 1
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
            if provider:
                self.provider_failures[provider] = self.provider_failures.get(provider, 0) + 1
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
            "subtitle": bounded_text(data.get("subtitle"), FIELD_LIMITS["subtitle"]),
            "description": plain_description(data.get("description")),
            "subjects": normalize_subjects(data.get("subjects")),
            "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg?default=false"
            if cover_id
            else "",
        },
        "openlibrary",
        str(data.get("key") or ""),
        provenance_details={
            "description": {"record_type": "edition"},
        },
    )


def candidate(
    data: dict[str, Any],
    source: str,
    identifier: str,
    origin: str | None = None,
    provenance_details: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data = {**data, "source": source, "source_id": identifier}
    data["provenance"] = {
        field: {
            "source": origin or source,
            "source_id": identifier,
            **({"url": data[field]} if field == "cover_url" else {}),
            **(provenance_details or {}).get(field, {}),
        }
        for field in (*METADATA_FIELDS, "cover_url")
        if data.get(field)
    }
    return data


def _provider_for(candidate_data: dict[str, Any], field: str) -> str:
    provenance = candidate_data.get("provenance")
    origin = provenance.get(field) if isinstance(provenance, dict) else None
    if isinstance(origin, dict) and isinstance(origin.get("source"), str):
        return origin["source"]
    source = candidate_data.get("source")
    return source if isinstance(source, str) else ""


def _provider_value(field: str, value: Any) -> Any:
    if field == "subtitle":
        return bounded_text(value, FIELD_LIMITS["subtitle"])
    if field == "description":
        return plain_description(value)
    if field == "subjects":
        return normalize_subjects(value)
    if field == "authors":
        return [name.strip() for name in value if isinstance(name, str) and name.strip()]
    if field == "page_count":
        return optional_page_count(value)
    if isinstance(value, str):
        return value.strip()
    return value


def resolve_candidates(
    candidates: list[dict[str, Any]], isbn: str, fields: set[str]
) -> dict[str, tuple[Any, dict[str, Any]]]:
    """Choose the highest-priority usable candidate independently for each field."""
    region = isbn_region(isbn)
    if not region:
        return {}
    resolved: dict[str, tuple[Any, dict[str, Any]]] = {}
    for field in fields:
        priorities = FIELD_PRIORITIES.get(field, {}).get(region, ())
        for provider in priorities:
            for item in candidates:
                if _provider_for(item, field) != provider:
                    continue
                value = _provider_value(field, item.get(field))
                if value in (None, "", []):
                    continue
                provenance = item.get("provenance", {})
                origin = provenance.get(field) if isinstance(provenance, dict) else None
                if isinstance(origin, dict):
                    resolved[field] = (value, copy.deepcopy(origin))
                else:
                    resolved[field] = (
                        value,
                        {"source": provider, "source_id": str(item.get("source_id", ""))},
                    )
                break
            if field in resolved:
                break
    return resolved


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
            if identifiers and hasattr(lookup, "isbn_mismatches"):
                lookup.isbn_mismatches.add("google")
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
                    "subtitle": bounded_text(info.get("subtitle"), FIELD_LIMITS["subtitle"]),
                    "authors": strings(info.get("authors")) or ["Autoria desconhecida"],
                    "isbn": isbn or next(iter(sorted(identifiers)), ""),
                    "publisher": info.get("publisher") or "",
                    "year": str(info.get("publishedDate") or "")[:4],
                    "language": info.get("language") or "",
                    "page_count": optional_page_count(info.get("pageCount")),
                    "description": plain_description(info.get("description")),
                    "subjects": normalize_subjects(info.get("categories")),
                    "cover_url": cover.replace("http:", "https:", 1),
                },
                "google",
                str(item["id"]),
            )
        )
    return results


def brazil(lookup: Lookup, isbn: str, provider: str) -> dict[str, Any]:
    data = lookup.json("https://brasilapi.com.br/api/isbn/v1/" + isbn, {"providers": provider})
    returned_isbn = normalized_identifier(data.get("isbn"))
    if returned_isbn and returned_isbn != isbn and hasattr(lookup, "isbn_mismatches"):
        lookup.isbn_mismatches.add(provider)
    if returned_isbn != isbn or not data.get("title"):
        return {}
    return candidate(
        {
            "title": data["title"],
            "subtitle": bounded_text(data.get("subtitle"), FIELD_LIMITS["subtitle"]),
            "authors": strings(data.get("authors")) or ["Autoria desconhecida"],
            "isbn": isbn,
            "publisher": data.get("publisher") or "",
            "year": str(data.get("year") or ""),
            "page_count": optional_page_count(data.get("page_count")),
            "description": plain_description(data.get("synopsis") or data.get("description")),
            "subjects": normalize_subjects(data.get("subjects")),
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

    for field in METADATA_FIELDS:
        if not result.get(field) and extra.get(field):
            result[field] = extra[field]
            result["provenance"][field] = extra["provenance"][field]
    if not result.get("description") and isbn in identifiers:
        for work in objects(detail.get("works")):
            key = work.get("key")
            if not isinstance(key, str) or not re.fullmatch(r"/works/OL[0-9]+W", key):
                continue
            work_data = lookup.json("https://openlibrary.org" + key + ".json", {})
            description = plain_description(work_data.get("description"))
            if description:
                result["description"] = description
                result["provenance"]["description"] = {
                    "source": "openlibrary",
                    "source_id": key,
                    "record_type": "work",
                }
                break
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
            *METADATA_FIELDS,
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
    region = isbn_region(isbn)
    if not region:
        return result
    sources = {
        "cbl": lambda: brazil(lookup, isbn, "cbl"),
        "mercado-editorial": lambda: brazil(lookup, isbn, "mercado-editorial"),
        "openlibrary": lambda: openlibrary(lookup, isbn),
        "google": lambda: next(iter(google(lookup, "isbn:" + isbn, isbn)), {}),
    }
    requested_fields = {field for field in METADATA_FIELDS if missing(result.get(field))}
    candidates: list[dict[str, Any]] = []
    queried: set[str] = set()

    def fetch(source: str) -> dict[str, Any]:
        queried.add(source)
        extra = sources[source]()
        if hasattr(lookup, "provider_outcomes"):
            if extra:
                lookup.provider_outcomes[source] = "match"
            elif source in getattr(lookup, "isbn_mismatches", set()):
                lookup.provider_outcomes[source] = "isbn_mismatch"
            elif source in getattr(lookup, "provider_failures", {}):
                lookup.provider_outcomes[source] = "failure"
            else:
                lookup.provider_outcomes[source] = "no_match"
        if extra:
            candidates.append(extra)
            if not result.get("source"):
                result.update(source=extra["source"], source_id=extra["source_id"])
        return extra

    while requested_fields:
        needed: list[str] = []
        for field in METADATA_FIELDS:
            if field not in requested_fields:
                continue
            priorities = FIELD_PRIORITIES[field][region]
            selected = resolve_candidates(candidates, isbn, {field}).get(field)
            selected_source = selected[1]["source"] if selected else ""
            selected_rank = (
                priorities.index(selected_source) if selected_source in priorities else None
            )
            required = priorities[: selected_rank + 1] if selected_rank is not None else priorities
            needed.extend(source for source in required if source not in queried)
        next_source = next((source for source in needed if source in sources), None)
        if next_source is None:
            break
        fetch(next_source)

    resolved = resolve_candidates(candidates, isbn, requested_fields)
    for field, (value, origin) in resolved.items():
        if field == "cover_url":
            continue
        result[field] = value
        alternatives: list[str] = []
        for extra in candidates:
            alternative_source = _provider_for(extra, field)
            alternative_value = _provider_value(field, extra.get(field))
            if (
                not alternative_value
                or alternative_source == origin.get("source")
                or alternative_value == value
            ):
                continue
            rendered = (
                "; ".join(alternative_value)
                if isinstance(alternative_value, list)
                else str(alternative_value)
            )
            alternative = f"{alternative_source}: {rendered[:300]}"
            if alternative not in alternatives and len(alternatives) < 4:
                alternatives.append(alternative)
        if alternatives:
            origin["alternatives"] = alternatives
        result.setdefault("provenance", {})[field] = origin

    if not result.get("cover_url"):
        for source in FIELD_PRIORITIES["cover_url"][region]:
            if source not in queried:
                fetch(source)
            extra = next(
                (
                    item
                    for item in candidates
                    if _provider_for(item, "cover_url") == source and item.get("cover_url")
                ),
                {},
            )
            if not extra:
                continue
            image = lookup.image(extra["cover_url"])
            if image:
                origin = extra.get("provenance", {}).get("cover_url", {})
                result["cover_url"] = image
                result.setdefault("provenance", {})["cover_url"] = {**origin, "url": image}
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
