"""arXiv-specific tests: Atom parsing, URL parsing, date query, category filter."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.fetchers.arxiv import (
    build_date_query,
    build_search_query,
    extract_authors,
    extract_categories,
    get_parsed_output,
    get_total_results,
    parse_arxiv_url,
)

# --- parse_arxiv_url ---


def test_parse_arxiv_url_happy_path():
    """Standard arxiv URL parses into (idv, rawid, version)."""
    idv, rawid, version = parse_arxiv_url("http://arxiv.org/abs/1512.08756v2")
    assert idv == "1512.08756v2"
    assert rawid == "1512.08756"
    assert version == 2


def test_parse_arxiv_url_rejects_missing_v():
    """ID without version separator raises ValueError naming the malformed input."""
    with pytest.raises(ValueError, match="malformed arxiv id"):
        parse_arxiv_url("http://arxiv.org/abs/1512.08756")


def test_parse_arxiv_url_rejects_no_slash():
    """URL without / raises ValueError with 'bad url' message."""
    with pytest.raises(ValueError, match="bad url"):
        parse_arxiv_url("not-a-url")


def test_parse_arxiv_url_rejects_non_numeric_version():
    """Non-numeric version raises ValueError with helpful message."""
    with pytest.raises(ValueError, match="malformed arxiv id"):
        parse_arxiv_url("http://arxiv.org/abs/1512.08756vabc")


def test_parse_arxiv_url_rejects_multiple_v():
    """ID with multiple 'v' separators raises ValueError with helpful message."""
    with pytest.raises(ValueError, match="malformed arxiv id"):
        parse_arxiv_url("http://arxiv.org/abs/1512.08756v2v3")


# --- build_date_query ---


def test_build_date_query_with_from_and_to():
    """Builds submittedDate range when both dates provided."""
    result = build_date_query(date_from="2024-12-09", date_to="2024-12-15")
    assert "submittedDate:" in result
    assert "202412090000" in result
    assert "202412152359" in result


def test_build_date_query_with_from_only():
    """Uses today as end date when only date_from provided."""
    result = build_date_query(date_from="2024-12-09")
    assert "submittedDate:" in result
    assert "202412090000" in result


def test_build_date_query_returns_empty_when_no_dates():
    """Returns empty string when no dates provided."""
    assert build_date_query() == ""


def test_build_date_query_rejects_invalid_date_format():
    """Raises ValueError for non-YYYY-MM-DD format."""
    with pytest.raises(ValueError, match="date"):
        build_date_query(date_from="12/09/2024")


def test_build_date_query_format_is_arxiv_compatible():
    """Output follows arXiv submittedDate query syntax."""
    result = build_date_query(date_from="2024-12-09", date_to="2024-12-15")
    assert "+AND+submittedDate:[" in result
    assert "+TO+" in result
    assert result.endswith("]")


# --- build_search_query ---


def test_build_search_query_groups_or_topics_before_date_range():
    """The date range must bound every OR'd category, not only the last one.

    arXiv binds AND tighter than OR: ``A+OR+B+AND+date`` means ``A OR (B AND date)``.
    """
    date_query = build_date_query(date_from="2026-03-16", date_to="2026-03-22")
    result = build_search_query("cat:cs.CV+OR+cat:cs.AI", date_query)
    assert result == "(cat:cs.CV+OR+cat:cs.AI)" + date_query


def test_build_search_query_without_dates_is_topics_unchanged():
    assert build_search_query("cat:cs.CV+OR+cat:cs.AI", "") == "cat:cs.CV+OR+cat:cs.AI"


# --- extract_categories ---


def test_extract_categories_from_tags():
    """Extracts category terms from feedparser tags list."""
    tags = [{"term": "cs.CV"}, {"term": "cs.LG"}, {"term": "math.OC"}]
    assert extract_categories(tags) == ["cs.CV", "cs.LG", "math.OC"]


def test_extract_categories_empty_tags():
    """Returns empty list when no tags present."""
    assert extract_categories([]) == []
    assert extract_categories(None) == []


# --- get_parsed_output ---


def _make_entry(arxiv_id, published, tags, authors=None, summary="Mock abstract."):
    """Create a mock feedparser entry."""
    entry = MagicMock()
    entry.keys.return_value = ["id", "published", "updated", "title", "tags", "authors", "summary"]
    entry.__getitem__ = lambda self, key: {
        "id": f"http://arxiv.org/abs/{arxiv_id}v1",
        "published": published,
        "updated": published,
        "title": "Test Paper",
        "tags": tags,
        "authors": authors if authors is not None else [{"name": "Doe, J."}],
        "summary": summary,
    }[key]
    return entry


def test_parsed_output_includes_categories_authors_abstract():
    """Output rows include categories, authors, and abstract columns."""
    entry = _make_entry(
        "2603.00001",
        "2026-03-23T17:00:00Z",
        [{"term": "cs.CV"}, {"term": "cs.LG"}],
        authors=[{"name": "Doe, J."}, {"name": "Roe, R."}],
        summary="A novel approach.",
    )
    mock_parsed = MagicMock()
    mock_parsed.entries = [entry]

    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        result = get_parsed_output(b"mock")

    key = next(iter(result))
    row = result[key][0]
    assert len(row) == 9
    assert "cs.CV" in row[6]
    assert "cs.LG" in row[6]
    assert row[7] == "Doe, J.;Roe, R."
    assert row[8] == "A novel approach."


def test_parsed_output_preserves_title_verbatim_without_wrapping_quotes():
    """The row's Title column is the raw title with newlines collapsed —
    NOT wrapped in literal single quotes, and apostrophes are preserved.
    CSV quoting is handled at write time by _write_csv_row in common.py."""
    entry = _make_entry(
        "2603.00010",
        "2026-03-23T17:00:00Z",
        [{"term": "cs.CV"}],
    )
    entry.__getitem__ = lambda self, key: {
        "id": "http://arxiv.org/abs/2603.00010v1",
        "published": "2026-03-23T17:00:00Z",
        "updated": "2026-03-23T17:00:00Z",
        "title": "O'Brien's algorithm: a survey\nwith newline",
        "tags": [{"term": "cs.CV"}],
        "authors": [{"name": "Doe, J."}],
        "summary": "abs",
    }[key]
    mock_parsed = MagicMock()
    mock_parsed.entries = [entry]

    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        result = get_parsed_output(b"mock")

    row = result[next(iter(result))][0]
    title = row[5]
    assert title == "O'Brien's algorithm: a survey with newline"
    assert not title.startswith("'")
    assert not title.endswith("'")


def test_extract_authors_handles_empty_and_missing():
    """extract_authors returns '' for None/empty and skips entries without name."""
    assert extract_authors(None) == ""
    assert extract_authors([]) == ""
    assert extract_authors([{"name": "A"}, {}, {"name": "B"}]) == "A;B"


def test_parsed_output_strips_newlines_from_abstract():
    """Abstract newlines/CRs are flattened to spaces (CSV cleanliness)."""
    entry = _make_entry(
        "2603.00002",
        "2026-03-23T17:00:00Z",
        [{"term": "cs.CV"}],
        summary="Line one.\nLine two.\r\nLine three.",
    )
    mock_parsed = MagicMock()
    mock_parsed.entries = [entry]

    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        result = get_parsed_output(b"mock")

    row = result[next(iter(result))][0]
    assert "\n" not in row[8]
    assert "\r" not in row[8]
    assert row[8] == "Line one. Line two.  Line three."


def test_parsed_output_filters_by_allowed_categories():
    """Papers without any matching category are excluded."""
    entry_match = _make_entry(
        "2603.00001",
        "2026-03-23T17:00:00Z",
        [{"term": "cs.CV"}, {"term": "math.OC"}],
    )
    entry_no_match = _make_entry(
        "2603.00002",
        "2026-03-23T18:00:00Z",
        [{"term": "math.OC"}, {"term": "stat.ML"}],
    )
    mock_parsed = MagicMock()
    mock_parsed.entries = [entry_match, entry_no_match]

    allowed = {"cs.CV", "cs.LG"}
    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        result = get_parsed_output(b"mock", allowed_categories=allowed)

    total_rows = sum(len(rows) for rows in result.values())
    assert total_rows == 1


def test_parsed_output_filters_old_papers_by_max_age():
    """Papers published more than max_age_days ago are excluded."""
    old_entry = _make_entry("2401.00001", "2024-01-15T17:00:00Z", [{"term": "cs.CV"}])
    recent_date = (datetime.now(tz=None) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent_entry = _make_entry("2603.99999", recent_date, [{"term": "cs.CV"}])
    mock_parsed = MagicMock()
    mock_parsed.entries = [old_entry, recent_entry]

    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        result = get_parsed_output(b"mock", max_age_days=7)

    total_rows = sum(len(rows) for rows in result.values())
    assert total_rows == 1


def test_parsed_output_no_filter_when_none():
    """All papers pass when allowed_categories is None."""
    entry = _make_entry("2603.00001", "2026-03-23T17:00:00Z", [{"term": "math.OC"}])
    mock_parsed = MagicMock()
    mock_parsed.entries = [entry]

    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        result = get_parsed_output(b"mock", allowed_categories=None)

    assert sum(len(rows) for rows in result.values()) == 1


# --- get_total_results ---


def test_get_total_results_reads_opensearch_field():
    """Extracts totalResults from feedparser feed metadata."""
    mock_parsed = MagicMock()
    mock_parsed.feed.opensearch_totalresults = "1500"
    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        total = get_total_results(b"<feed>mock</feed>")
    assert total == 1500


def test_get_total_results_returns_zero_on_missing_field():
    """Returns 0 when opensearch:totalResults is not present."""
    mock_parsed = MagicMock(spec=[])
    mock_parsed.feed = MagicMock(spec=[])
    with patch("src.fetchers.arxiv.parse", return_value=mock_parsed):
        total = get_total_results(b"<feed>empty</feed>")
    assert total == 0
