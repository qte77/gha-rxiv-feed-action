"""Semantic Scholar citation enrichment for arXiv IDs and bioRxiv/medRxiv DOIs."""

import json
import time
from urllib.parse import quote

from src.fetchers.common import get_api_response

API_BASE = "https://api.semanticscholar.org/graph/v1/paper"
FIELDS = "citationCount,referenceCount,influentialCitationCount"
_last_call = 0.0
_ZERO = {"citation_count": 0, "reference_count": 0, "influential_count": 0}


def get_citations(paper_id: str, api_key: str = "") -> dict:
    """Fetch citation counts from Semantic Scholar.

    ``paper_id`` carries the Semantic Scholar prefix, e.g. ``ARXIV:2406.04221``
    or ``DOI:10.1101/2024.01.15.1234``. ``api_key`` (optional) is sent as the
    ``x-api-key`` header. The call goes through ``get_api_response`` so the
    host allowlist applies; one attempt per paper, short timeout.

    Rate limited to 1 RPS. Returns zero-filled dict on any error.
    """
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    url = f"{API_BASE}/{quote(paper_id, safe=':/')}?fields={FIELDS}"
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        data = json.loads(get_api_response(url, max_retries=1, headers=headers, timeout=10))
    except (RuntimeError, ValueError):
        return dict(_ZERO)
    finally:
        _last_call = time.time()
    return {
        "citation_count": data.get("citationCount", 0),
        "reference_count": data.get("referenceCount", 0),
        "influential_count": data.get("influentialCitationCount", 0),
    }


def enrich_row(row: list, citations: dict) -> list:
    """Append citation_count, reference_count, influential_count to a CSV row."""
    return [
        *row,
        citations["citation_count"],
        citations["reference_count"],
        citations["influential_count"],
    ]
