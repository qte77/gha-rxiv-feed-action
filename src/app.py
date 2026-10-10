"""Main entry point for the rxiv-feed action.

Dispatches by ``SERVER`` env var to a per-server fetcher. arxiv is the
default. All side-effects (env reads, filesystem, network) live inside
``main()`` or the ``_run_*`` helpers — never at module level — so
``import src.app`` is cheap and test-safe.
"""

import json
from os import getenv

from src.fetchers.arxiv import (
    build_date_query,
    build_search_query,
    get_parsed_output,
    get_total_results,
)
from src.fetchers.arxiv_citations import enrich_row, get_citations
from src.fetchers.biorxiv import (
    build_date_range,
    needs_pagination,
    parse_biorxiv_json,
    prune_existing_csvs,
)
from src.fetchers.common import (
    filter_new_rows,
    get_api_response,
    load_all_existing_ids,
    write_file,
)
from src.validation import validate_env

_BIORXIV_HEADER = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors", "Abstract"]
_ARXIV_HEADER = [
    "Published",
    "ISOWeek",
    "Updated",
    "ID",
    "Version",
    "Title",
    "Categories",
    "Authors",
    "Abstract",
]
_ARXIV_CITATIONS_HEADER = ["Citations", "References", "InfluentialCitations"]


def _run_biorxiv(
    server: str,
    out_dir: str,
    days: int,
    categories: set,
    date_from: str = "",
    date_to: str = "",
) -> None:
    """Fetch bioRxiv / medRxiv weekly stats and write per-week CSVs."""
    pruned = prune_existing_csvs(out_dir, categories)
    if pruned:
        print(f"Pruned {pruned} rows outside CATEGORIES from {out_dir}")
    existing_ids = load_all_existing_ids(out_dir)
    print(f"Loaded {len(existing_ids)} existing paper IDs from {out_dir}")

    base_url = f"https://api.biorxiv.org/details/{server}"
    page_size = 100
    start_date, end_date = build_date_range(
        days, date_from=date_from or None, date_to=date_to or None
    )
    print(f"Fetching {server} from {start_date} to {end_date}")
    cursor = 0
    all_weeks: dict = {}

    while True:
        url = f"{base_url}/{start_date}/{end_date}/{cursor}/json"
        data = get_api_response(url)
        payload = json.loads(data)
        weekly = parse_biorxiv_json(data, categories)
        for week, rows in weekly.items():
            all_weeks.setdefault(week, []).extend(rows)
        if not needs_pagination(payload.get("messages", [])):
            break
        cursor += page_size

    for (year, week), rows in all_weeks.items():
        new_rows = filter_new_rows(rows, existing_ids)
        if new_rows:
            year_dir = f"{out_dir}/{year}"
            write_file(new_rows, str(week), year_dir, _BIORXIV_HEADER)
            existing_ids.update((row[2], str(row[3])) for row in new_rows)
            print(f"Wrote {year}/week {week}: {len(new_rows)} new papers")


def _arxiv_paginate(
    base_url: str,
    search_query: str,
    page_size: int,
    max_pages: int,
    allowed: set,
    effective_max_age: int | None,
) -> dict:
    """Paginate arXiv API, return weekly dict of parsed rows."""
    probe_url = f"{base_url}search_query={search_query}&start=0&max_results=1&sortBy=submittedDate"
    try:
        total = get_total_results(get_api_response(probe_url))
    except RuntimeError as e:
        print(f"arXiv probe failed, skipping run: {e}")
        return {}
    fetch_limit = min(total, max_pages * page_size)
    print(f"arXiv reports {total} total results. Fetching up to {fetch_limit}.")

    out: dict = {}
    start = 0
    while start < fetch_limit:
        page_url = (
            f"{base_url}search_query={search_query}"
            f"&start={start}&max_results={page_size}&sortBy=submittedDate"
        )
        try:
            page = get_api_response(page_url)
        except RuntimeError as e:
            print(f"API error at start={start}, stopping: {e}")
            break
        weekly = get_parsed_output(page, allowed_categories=allowed, max_age_days=effective_max_age)
        if not weekly:
            print(f"No matching papers on page starting at {start}. Stopping.")
            break
        for key, rows in weekly.items():
            out.setdefault(key, []).extend(rows)
        start += page_size
    return out


def _run_arxiv(
    out_dir: str,
    topics: str,
    include_citations: bool,
    max_age_days: int,
    date_from: str,
    date_to: str,
    page_size: int,
    max_pages: int,
) -> None:
    """Fetch arXiv stats by topic, optionally enrich with citation counts."""
    import re

    allowed = set(re.findall(r"cat:([a-zA-Z\-]+\.[A-Z]+)", topics))
    print(f"Allowed categories: {sorted(allowed)}")

    date_query = build_date_query(date_from=date_from or None, date_to=date_to or None)
    effective_max_age = None if date_query else max_age_days
    search_query = build_search_query(topics, date_query)

    existing_ids = load_all_existing_ids(out_dir, dedup_cols=(3, 4))
    print(f"Loaded {len(existing_ids)} existing paper IDs from {out_dir}")

    base_url = "https://export.arxiv.org/api/query?"
    header = _ARXIV_HEADER + (_ARXIV_CITATIONS_HEADER if include_citations else [])

    all_weeks = _arxiv_paginate(
        base_url, search_query, page_size, max_pages, allowed, effective_max_age
    )

    total_new = 0
    for (year, week), rows in all_weeks.items():
        new_rows = filter_new_rows(rows, existing_ids, dedup_cols=(3, 4))
        if not new_rows:
            continue
        if include_citations:
            new_rows = [enrich_row(row, get_citations(row[3])) for row in new_rows]
        year_dir = f"{out_dir}/{year}"
        write_file(new_rows, str(week), year_dir, header, dedup_cols=(3, 4))
        existing_ids.update((row[3], str(row[4])) for row in new_rows)
        total_new += len(new_rows)
        print(f"Wrote {year}/week {week}: {len(new_rows)} new papers")
    print(f"Done. {total_new} new papers written.")


_ENV_KEYS = (
    "OUT_DIR",
    "SERVER",
    "DAYS",
    "CATEGORIES",
    "TOPICS",
    "INCLUDE_CITATIONS",
    "MAX_AGE_DAYS",
    "DATE_FROM",
    "DATE_TO",
    "PAGE_SIZE",
    "MAX_PAGES",
)


def main() -> None:
    """Read env, validate, dispatch to the per-server runner."""
    # Only include set vars in the env dict. validate_env treats absence as
    # "use the default"; empty strings as malformed.
    env = {k: v for k in _ENV_KEYS if (v := getenv(k)) is not None}
    validate_env(env)

    server = env.get("SERVER") or "arxiv"
    out_dir = env.get("OUT_DIR") or "./data/arxiv"

    if server == "arxiv":
        _run_arxiv(
            out_dir=out_dir,
            topics=env.get("TOPICS")
            or "cat:cs.CV+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.AI+OR+cat:cs.NE+OR+cat:cs.RO",
            include_citations=env.get("INCLUDE_CITATIONS", "false").lower() == "true",
            max_age_days=int(env.get("MAX_AGE_DAYS") or "7"),
            date_from=env.get("DATE_FROM", ""),
            date_to=env.get("DATE_TO", ""),
            page_size=int(env.get("PAGE_SIZE") or "1000"),
            max_pages=int(env.get("MAX_PAGES") or "5"),
        )
    else:
        _run_biorxiv(
            server=server,
            out_dir=out_dir,
            days=int(env.get("DAYS") or "1"),
            categories={c.strip() for c in env.get("CATEGORIES", "").split(",") if c.strip()},
            date_from=env.get("DATE_FROM", ""),
            date_to=env.get("DATE_TO", ""),
        )


if __name__ == "__main__":
    main()
