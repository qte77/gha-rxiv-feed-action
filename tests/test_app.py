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


def test_main_dispatches_psyarxiv_to_osf_fetcher(monkeypatch):
    """SERVER=psyarxiv routes to _run_osf with the psyarxiv provider."""
    monkeypatch.setenv("SERVER", "psyarxiv")
    monkeypatch.setenv("OUT_DIR", "./data/psyarxiv-test")
    monkeypatch.setenv("CATEGORIES", "Neuroscience")

    with (
        patch("src.app._run_arxiv", create=True) as mock_arxiv,
        patch("src.app._run_biorxiv", create=True) as mock_bio,
        patch("src.app._run_osf", create=True) as mock_osf,
    ):
        main()

    mock_osf.assert_called_once()
    assert mock_osf.call_args.kwargs["provider"] == "psyarxiv"
    assert mock_osf.call_args.kwargs["categories"] == {"Neuroscience"}
    mock_arxiv.assert_not_called()
    mock_bio.assert_not_called()


def test_run_osf_follows_next_links_and_stops_on_api_error(tmp_path):
    """_run_osf paginates via links.next and keeps rows when a later page fails."""
    import json

    from src.app import _run_osf

    page = {
        "data": [
            {
                "id": "abc12_v1",
                "attributes": {
                    "title": "T",
                    "description": "D",
                    "date_published": "2026-10-20T09:30:00.000000",
                    "version": 1,
                    "subjects": [[{"id": "s1", "text": "Neuroscience"}]],
                },
                "links": {"preprint_doi": "https://doi.org/10.31234/osf.io/abc12_v1"},
            }
        ],
        "links": {"next": "https://api.osf.io/v2/preprints/?page=2"},
    }

    with patch(
        "src.app.get_api_response", side_effect=[json.dumps(page).encode(), RuntimeError("boom")]
    ) as mock_get:
        _run_osf(
            provider="psyarxiv",
            out_dir=str(tmp_path),
            days=7,
            categories=set(),
            date_from="2026-10-19",
            date_to="2026-10-25",
        )

    assert mock_get.call_args_list[1].args[0] == "https://api.osf.io/v2/preprints/?page=2"
    written = (tmp_path / "2026" / "43.csv").read_text(encoding="UTF8")
    assert "10.31234/osf.io/abc12_v1" in written
