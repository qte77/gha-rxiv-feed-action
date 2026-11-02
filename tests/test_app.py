"""Dispatch tests for src/app.py.

Tests `main()` only — the per-server logic is covered by fetcher tests.
Patches `_run_arxiv` / `_run_biorxiv` so the test never touches HTTP.
"""

from unittest.mock import patch

import pytest

from src.app import main


def test_main_dispatches_to_arxiv(monkeypatch):
    """SERVER=arxiv routes to _run_arxiv only."""
    monkeypatch.setenv("SERVER", "arxiv")
    monkeypatch.setenv("TOPICS", "cat:cs.AI")
    monkeypatch.setenv("OUT_DIR", "./data/arxiv-test")

    with (
        patch("src.app._run_arxiv", create=True) as mock_arxiv,
        patch("src.app._run_biorxiv", create=True) as mock_bio,
    ):
        main()

    mock_arxiv.assert_called_once()
    mock_bio.assert_not_called()


def test_main_dispatches_to_biorxiv(monkeypatch):
    """SERVER=biorxiv routes to _run_biorxiv only."""
    monkeypatch.setenv("SERVER", "biorxiv")
    monkeypatch.setenv("OUT_DIR", "./data/biorxiv-test")

    with (
        patch("src.app._run_arxiv", create=True) as mock_arxiv,
        patch("src.app._run_biorxiv", create=True) as mock_bio,
    ):
        main()

    mock_bio.assert_called_once()
    mock_arxiv.assert_not_called()


def test_main_raises_on_invalid_env(monkeypatch):
    """validate_env is called inside main; bad SERVER raises ValueError."""
    monkeypatch.setenv("SERVER", "chemrxiv")

    with (
        patch("src.app._run_arxiv", create=True),
        patch("src.app._run_biorxiv", create=True),
        pytest.raises(ValueError, match="SERVER"),
    ):
        main()


def test_arxiv_paginate_returns_empty_on_probe_failure():
    """Probe failure must not crash the run; returns {} so caller no-ops."""
    from src.app import _arxiv_paginate

    with patch("src.app.get_api_response", side_effect=RuntimeError("boom")):
        result = _arxiv_paginate(
            base_url="https://export.arxiv.org/api/query?",
            search_query="cat:cs.AI",
            page_size=100,
            max_pages=5,
            allowed={"cs.AI"},
            effective_max_age=7,
        )

    assert result == {}


def test_run_biorxiv_stops_gracefully_on_api_error(tmp_path):
    """A RuntimeError mid-pagination keeps already-fetched rows and does not crash."""
    import json

    from src.app import _run_biorxiv

    first_page = json.dumps(
        {
            "messages": [{"status": "ok", "total": 200, "count": 100, "cursor": 0}],
            "collection": [
                {
                    "doi": "10.1101/2024.01.15.1234",
                    "version": "1",
                    "category": "neuroscience",
                    "title": "Kept Paper",
                    "authors": "Smith J",
                    "abstract": "A.",
                    "date": "2024-01-15",
                }
            ],
        }
    ).encode()

    with patch(
        "src.app.get_api_response", side_effect=[first_page, RuntimeError("boom")]
    ) as mock_get:
        _run_biorxiv(
            server="biorxiv",
            out_dir=str(tmp_path),
            days=7,
            categories=set(),
            date_from="2024-01-15",
            date_to="2024-01-21",
        )

    assert mock_get.call_count == 2
    written = (tmp_path / "2024" / "3.csv").read_text(encoding="UTF8")
    assert "10.1101/2024.01.15.1234" in written
