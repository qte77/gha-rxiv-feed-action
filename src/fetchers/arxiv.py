"""arXiv fetcher: Atom XML parsing, URL/date helpers, category filtering.

HTTP fetching + retry lives in ``fetchers.common.get_api_response``.
CSV write/dedup with ``dedup_cols=(3, 4)`` lives in ``fetchers.common``.
This module is pure parsing — no network, no I/O at import time.
"""

from datetime import datetime
from typing import Any

from feedparser import FeedParserDict, parse  # type: ignore[import-untyped]

from src.fetchers.common import scrub_newlines


def encode_feedparser_dict(d: Any) -> Any:  # noqa: ANN401 - heterogeneous feedparser input
    """Strip feedparser objects to plain Python dicts via iterative descent.

    Iterative (not recursive) so the function does not trip ruff C901
    under ``mccabe.max-complexity = 10``.
    """
    if isinstance(d, FeedParserDict | dict):
        return {k: encode_feedparser_dict(d[k]) for k in d}
    if isinstance(d, list):
        return [encode_feedparser_dict(x) for x in d]
    return d


def parse_arxiv_url(url: str) -> tuple[str, str, int]:
    """Extract (idv, rawid, version) from an arxiv abs URL.

    Example: ``http://arxiv.org/abs/1512.08756v2`` →
    ``("1512.08756v2", "1512.08756", 2)``.
    """
    ix = url.rfind("/")
    if ix < 0:
        raise ValueError(f"bad url: {url}")
    idv = url[ix + 1 :]
    parts = idv.split("v")
    if len(parts) != 2:
        raise ValueError(f"malformed arxiv id (expected 'rawidvN'): {idv}")
    rawid, version_str = parts
    try:
        return idv, rawid, int(version_str)
    except ValueError:
        raise ValueError(f"malformed arxiv id (expected 'rawidvN'): {idv}") from None


def build_date_query(date_from: str | None = None, date_to: str | None = None) -> str:
    """Build arxiv submittedDate range query fragment.

    Returns empty string when ``date_from`` is None. Raises ``ValueError``
    for non-``YYYY-MM-DD`` inputs.
    """
    if not date_from:
        return ""

    def _parse(d: str) -> datetime:
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {d}. Expected YYYY-MM-DD.") from None

    start = _parse(date_from)
    end = _parse(date_to) if date_to else datetime.now(tz=None)
    return f"+AND+submittedDate:[{start:%Y%m%d}0000+TO+{end:%Y%m%d}2359]"


def build_search_query(topics: str, date_query: str) -> str:
    """Combine a topic query with a date-range fragment.

    arXiv binds AND tighter than OR, so the topics are grouped first; otherwise
    ``A+OR+B+AND+date`` bounds only ``B`` and returns papers of any date for ``A``.
    """
    if not date_query:
        return topics
    return f"({topics}){date_query}"


def extract_categories(tags: list | None) -> list[str]:
    """Extract arxiv category terms from a feedparser tags list."""
    if not tags:
        return []
    return [t["term"] for t in tags if "term" in t]


def extract_authors(authors: list | None) -> str:
    """Join author names from a feedparser authors list into a `;`-separated string."""
    if not authors:
        return ""
    return ";".join(a["name"] for a in authors if isinstance(a, dict) and a.get("name"))


def get_parsed_output(
    response: bytes,
    allowed_categories: set | None = None,
    max_age_days: int | None = None,
) -> dict:
    """Parse arXiv Atom XML response into rows grouped by (year, ISO week).

    Row schema:
    ``[Published, ISOWeek, Updated, ID, Version, Title, Categories, Authors, Abstract]``.
    Dedup key is ``(ID, Version)`` at indices ``(3, 4)``.
    """
    out: dict = {}
    parsed = parse(response)
    now = datetime.now(tz=None)

    for entry in parsed.entries:
        j = encode_feedparser_dict(entry)

        try:
            tags = j["tags"]
        except (KeyError, TypeError):
            tags = []
        categories = extract_categories(tags)
        if allowed_categories and not any(c in allowed_categories for c in categories):
            continue

        _, rawid, version = parse_arxiv_url(j["id"])
        pub_date_utc = datetime.strptime(j["published"], "%Y-%m-%dT%H:%M:%SZ")

        if max_age_days is not None and (now - pub_date_utc).days > max_age_days:
            continue

        title = scrub_newlines(j["title"])

        try:
            raw_authors = j["authors"]
        except (KeyError, TypeError):
            raw_authors = None
        authors = extract_authors(raw_authors)
        try:
            raw_summary = j["summary"]
        except (KeyError, TypeError):
            raw_summary = ""
        abstract = scrub_newlines(raw_summary)

        iso = pub_date_utc.isocalendar()
        key = (iso.year, iso.week)
        out.setdefault(key, []).append(
            [
                j["published"],
                iso.week,
                j["updated"],
                rawid,
                version,
                title,
                ";".join(categories),
                authors,
                abstract,
            ]
        )
    return out


def get_total_results(response: bytes) -> int:
    """Read opensearch:totalResults from arXiv API response."""
    parsed = parse(response)
    try:
        return int(parsed.feed.opensearch_totalresults)
    except (AttributeError, ValueError, TypeError):
        return 0
