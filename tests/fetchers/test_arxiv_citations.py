"""Semantic Scholar citation enrichment tests."""

import json
from unittest.mock import patch

import pytest

import src.fetchers.arxiv_citations as citations_module
from src.fetchers.arxiv_citations import enrich_row, get_citations
from src.fetchers.common import _validate_url

_PAYLOAD = {"citationCount": 42, "referenceCount": 10, "influentialCitationCount": 5}


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    citations_module._last_call = 0.0


def test_get_citations_success_routes_through_allowlisted_client():
    """Returns counts; the call goes through get_api_response (host allowlist)."""
    with patch(
        "src.fetchers.arxiv_citations.get_api_response",
        return_value=json.dumps(_PAYLOAD).encode(),
    ) as mock_get:
        result = get_citations("ARXIV:2406.04221")

    assert result == {"citation_count": 42, "reference_count": 10, "influential_count": 5}
    url = mock_get.call_args.args[0]
    assert url.startswith("https://api.semanticscholar.org/graph/v1/paper/ARXIV:2406.04221?")
    _validate_url(url)
    assert mock_get.call_args.kwargs["headers"] == {}


def test_get_citations_builds_doi_lookup_and_sends_api_key():
    """bioRxiv/medRxiv DOIs use the DOI: prefix; the API key goes in x-api-key."""
    with patch(
        "src.fetchers.arxiv_citations.get_api_response",
        return_value=json.dumps(_PAYLOAD).encode(),
    ) as mock_get:
        get_citations("DOI:10.1101/2024.01.15.1234", api_key="secret")

    url = mock_get.call_args.args[0]
    assert "/paper/DOI:10.1101/2024.01.15.1234?fields=" in url
    assert mock_get.call_args.kwargs["headers"] == {"x-api-key": "secret"}


@pytest.mark.parametrize("error", [RuntimeError("404"), ValueError("bad host")])
def test_get_citations_zero_fills_on_error(error):
    """Not-found / API failure returns a zero-filled dict (graceful fallback)."""
    with patch("src.fetchers.arxiv_citations.get_api_response", side_effect=error):
        result = get_citations("ARXIV:9999.99999")
    assert result == {"citation_count": 0, "reference_count": 0, "influential_count": 0}


def test_get_citations_does_not_retry_per_paper():
    """One attempt per paper: retries x hundreds of rows would stall the job."""
    with patch(
        "src.fetchers.arxiv_citations.get_api_response",
        return_value=json.dumps(_PAYLOAD).encode(),
    ) as mock_get:
        get_citations("ARXIV:2406.04221")
    assert mock_get.call_args.kwargs["max_retries"] == 1


def test_get_citations_respects_rate_limit():
    """Calls time.sleep between successive requests to respect 1 RPS limit."""
    with (
        patch(
            "src.fetchers.arxiv_citations.get_api_response",
            return_value=json.dumps(_PAYLOAD).encode(),
        ),
        patch("src.fetchers.arxiv_citations.time") as mock_time,
    ):
        mock_time.time.return_value = 0.0
        get_citations("ARXIV:2406.00001")
        mock_time.time.return_value = 0.5
        get_citations("ARXIV:2406.00002")

    mock_time.sleep.assert_called()


def test_enrich_row():
    """Appends citation columns to a CSV row."""
    row = ["2024-06-06T16:20:07Z", 23, "2024-06-07T10:00:00Z", "2406.04221", 1, "'A Title'"]
    citations = {"citation_count": 42, "reference_count": 10, "influential_count": 5}
    result = enrich_row(row, citations)
    assert result == [*row, 42, 10, 5]
    assert len(result) == len(row) + 3
