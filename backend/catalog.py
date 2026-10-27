"""Shared catalog input and orchestration for the HTML page and JSON endpoint.

Routes handle HTTP; database/catalog.py handles SQL; this module connects them.
No writes, permission changes or new search semantics are introduced here.
"""

from dataclasses import dataclass
from typing import Mapping

from backend.i18n import LANGUAGES
from database.catalog import search_companies, search_courses

SEARCH_MODES = ("topic", "company", "profession", "result")


@dataclass(frozen=True)
class CatalogFilters:
    query: str = ""
    mode: str = "topic"
    language: str | None = None
    topic: str = ""

    @classmethod
    def from_args(cls, args: Mapping[str, str], *, fallback_to_topic=False):
        """Normalize URLs once, preserving the existing invalid-mode behavior.

        The HTML page falls back to Topic. The API keeps an unknown mode so the
        query layer returns [] (the original API contract).
        """
        mode = args.get("by", "topic")
        if fallback_to_topic and mode not in SEARCH_MODES:
            mode = "topic"
        language = args.get("lang")
        return cls(
            query=args.get("q", "").strip(),
            mode=mode,
            language=language if language in LANGUAGES else None,
            topic=args.get("topic", "").strip(),
        )


def catalog_results(filters: CatalogFilters):
    """Company mode intentionally ignores course-only language/topic filters."""
    if filters.mode == "company":
        return [
            dict(company, type="company")
            for company in search_companies(filters.query, "company")
        ]
    return search_courses(filters.query, filters.mode, filters.language, filters.topic)
