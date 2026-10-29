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


@pytest.mark.parametrize(
    ("server", "expected_header"),
    [("arxiv", "Published,ISOWeek,"), ("biorxiv", "Date,ISOWeek,"), ("medrxiv", "Date,ISOWeek,")],
)
def test_main_seed_only_writes_stub_and_skips_fetch(monkeypatch, tmp_path, server, expected_header):
    """SEED_ONLY=true seeds this week's header-only CSV and never fetches."""
    monkeypatch.setenv("SERVER", server)
    monkeypatch.setenv("TOPICS", "cat:cs.AI")
    monkeypatch.setenv("OUT_DIR", str(tmp_path))
    monkeypatch.setenv("SEED_ONLY", "true")

    with (
        patch("src.app._run_arxiv", create=True) as mock_arxiv,
        patch("src.app._run_biorxiv", create=True) as mock_bio,
    ):
        main()

    mock_arxiv.assert_not_called()
    mock_bio.assert_not_called()
    (stub,) = tmp_path.glob("*/*.csv")
    lines = stub.read_text(encoding="UTF8").splitlines()
    assert len(lines) == 1
    assert lines[0].startswith(expected_header)


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
