"""OSF preprints fetcher (psyArXiv): JSON:API parsing and list-URL building.

OSF-hosted preprint servers share one endpoint (``api.osf.io/v2/preprints/``)
filtered by ``filter[provider]``. Parsing targets the default API version
(2.0), where ``attributes.subjects`` is a list of root-to-leaf hierarchies of
``{id, text}`` and the next page is ``links.next``. Rows use the bioRxiv
schema so dedup on ``(DOI, Version)`` at ``(2, 3)`` applies unchanged.

``Category`` is the ``;``-joined top-level subjects (the full 234-node
psyArXiv taxonomy is too granular for a coarse filter). ``Authors`` is left
empty: names live behind a per-preprint contributors relationship, and an
N+1 lookup per row is deferred.
"""

import json
from datetime import date, timedelta

from src.fetchers.common import scrub_newlines

API_BASE = "https://api.osf.io/v2/preprints/"
PAGE_SIZE = 100  # OSF MAX_PAGE_SIZE
_DOI_URL_PREFIX = "https://doi.org/"


def build_osf_url(provider: str, start_date: str, end_date: str) -> str:
    """Build the first-page list URL for ``provider`` published in the window.

    Both bounds are inclusive dates: ``date_published`` is a datetime, so the
    upper bound is expressed as ``lt`` the day after ``end_date``.
    """
    end_exclusive = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
    return (
        f"{API_BASE}?filter[provider]={provider}"
        f"&filter[date_published][gte]={start_date}"
        f"&filter[date_published][lt]={end_exclusive}"
        f"&page[size]={PAGE_SIZE}"
    )


def _top_level_subjects(subjects: list | None) -> list[str]:
    """Return unique root subject texts in first-seen order."""
    seen: list[str] = []
    for hierarchy in subjects or []:
        if hierarchy and hierarchy[0].get("text") and hierarchy[0]["text"] not in seen:
            seen.append(hierarchy[0]["text"])
    return seen


def _doi_or_guid(item: dict) -> str:
    """Prefer the preprint DOI; fall back to the unversioned OSF GUID."""
    doi = (item.get("links") or {}).get("preprint_doi") or ""
    if doi:
        return doi.removeprefix(_DOI_URL_PREFIX)
    return item["id"].split("_v")[0]


def parse_osf_json(data: bytes, categories: set | None = None) -> tuple[dict, str | None]:
    """Parse one OSF preprints page into ``({(year, week): rows}, next_url)``.

    Row schema: ``[Date, ISOWeek, DOI, Version, Category, Title, Authors, Abstract]``.
    A non-empty ``categories`` keeps entries with any matching top-level
    subject (case-insensitive).
    """
    payload = json.loads(data)
    cat_filter = {c.strip().lower() for c in categories} if categories else None
    out: dict = {}
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        subjects = _top_level_subjects(attrs.get("subjects"))
        if cat_filter and not any(s.lower() in cat_filter for s in subjects):
            continue
        pub_date = (attrs.get("date_published") or attrs["date_created"])[:10]
        iso = date.fromisoformat(pub_date).isocalendar()
        out.setdefault((iso[0], iso[1]), []).append(
            [
                pub_date,
                iso[1],
                _doi_or_guid(item),
                attrs.get("version") or 1,
                ";".join(subjects),
                scrub_newlines(attrs.get("title") or ""),
                "",
                scrub_newlines(attrs.get("description") or ""),
            ]
        )
    return out, (payload.get("links") or {}).get("next")
