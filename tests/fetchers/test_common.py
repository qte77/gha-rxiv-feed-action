"""Shared fetcher tests: HTTP retry, URL validator, dedup/IO with dedup_cols."""

import csv
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.fetchers.common import (
    _validate_url,
    filter_new_rows,
    get_api_response,
    load_all_existing_ids,
    write_file,
)


def _make_response(data: bytes = b"ok"):
    """Create a mock requests.Response with successful raise_for_status."""
    resp = MagicMock()
    resp.content = data
    resp.raise_for_status = MagicMock()
    return resp


# --- HTTP retry ---


def test_get_api_response_retries():
    """Fails 2x with ConnectionError then succeeds — returns data on 3rd call."""
    resp = _make_response(b"ok")
    side_effects = [
        requests.ConnectionError("transient"),
        requests.ConnectionError("transient"),
        resp,
    ]
    with (
        patch("src.fetchers.common.requests.get", side_effect=side_effects) as mock_get,
        patch("src.fetchers.common.time.sleep"),
    ):
        result = get_api_response("https://api.biorxiv.org/test", max_retries=3)
    assert result == b"ok"
    assert mock_get.call_count == 3


def test_get_api_response_raises_after_max():
    """Raises RuntimeError after max retries exhausted."""
    with (
        patch(
            "src.fetchers.common.requests.get",
            side_effect=requests.ConnectionError("fail"),
        ),
        patch("src.fetchers.common.time.sleep"),
        pytest.raises(RuntimeError),
    ):
        get_api_response("https://api.biorxiv.org/test", max_retries=3)


def test_get_api_response_forwards_headers_and_timeout():
    """Optional headers (e.g. an API key) and timeout reach requests.get."""
    with patch("src.fetchers.common.requests.get", return_value=_make_response()) as mock_get:
        get_api_response("https://api.biorxiv.org/test", headers={"x-api-key": "k"}, timeout=10)
    assert mock_get.call_args.kwargs == {"headers": {"x-api-key": "k"}, "timeout": 10}


# --- URL validator ---


@pytest.mark.parametrize(
    "host",
    ["api.biorxiv.org", "export.arxiv.org", "api.semanticscholar.org"],
)
def test_validate_url_accepts_allowlisted_hosts(host: str) -> None:
    """All three allowlisted API hosts pass validation."""
    _validate_url(f"https://{host}/some/path")


@pytest.mark.parametrize(
    "url",
    [
        "http://api.biorxiv.org/x",
        "file:///etc/passwd",
        "gopher://api.biorxiv.org/x",
        "ftp://api.biorxiv.org/x",
    ],
)
def test_validate_url_rejects_non_https(url: str) -> None:
    """Any scheme other than https raises ValueError."""
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_url(url)


def test_validate_url_rejects_userinfo() -> None:
    """URLs with user:pass@host are rejected to prevent URL-confusion attacks."""
    with pytest.raises(ValueError, match=r"[Uu]serinfo"):
        _validate_url("https://user:pass@api.biorxiv.org/x")


def test_validate_url_rejects_fragment() -> None:
    """URLs with a fragment are rejected (defensive against construction bugs)."""
    with pytest.raises(ValueError, match=r"[Ff]ragment"):
        _validate_url("https://api.biorxiv.org/x#frag")


def test_validate_url_rejects_unknown_host() -> None:
    """Hosts outside the API allowlist are rejected."""
    with pytest.raises(ValueError, match=r"[Hh]ost"):
        _validate_url("https://evil.example.com/x")


def test_validate_url_rejects_non_default_port() -> None:
    """Non-443 ports are rejected (block SSRF to internal services)."""
    with pytest.raises(ValueError, match="port"):
        _validate_url("https://api.biorxiv.org:8080/x")


# --- Dedup/IO (biorxiv schema by default) ---


def test_write_file_creates_csv(tmp_path):
    """Creates CSV with header and data rows."""
    header = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors"]
    rows = [
        ["2024-01-15", 3, "10.1101/2024.01.15.1234", "1", "neuroscience", "Test Paper", "Smith J"]
    ]
    year_dir = str(tmp_path / "2024")
    write_file(rows, "3", year_dir, header)
    out_file = tmp_path / "2024" / "3.csv"
    assert out_file.exists()
    content = out_file.read_text(encoding="UTF8")
    assert "Date" in content
    assert "2024-01-15" in content


def test_dedup_filters_existing_rows():
    """filter_new_rows removes rows with known DOI+version (biorxiv default)."""
    existing = {("10.1101/known.1", "1")}
    rows = [
        ["2024-01-15", 3, "10.1101/known.1", "1", "neuro", "Known", "A"],
        ["2024-01-16", 3, "10.1101/new.1", "1", "neuro", "New", "B"],
    ]
    result = filter_new_rows(rows, existing)
    assert len(result) == 1
    assert result[0][2] == "10.1101/new.1"


def test_write_file_no_duplicates(tmp_path):
    """Writing same rows twice doesn't duplicate."""
    header = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors"]
    rows = [["2024-01-15", 3, "10.1101/2024.01.15.1234", "1", "neuro", "Paper", "Smith"]]
    year_dir = str(tmp_path / "2024")
    write_file(rows, "3", year_dir, header)
    write_file(rows, "3", year_dir, header)
    content = (tmp_path / "2024" / "3.csv").read_text(encoding="UTF8")
    lines = [line for line in content.strip().split("\n") if line]
    assert len(lines) == 2


def test_load_all_existing_ids_walks_year_dirs(tmp_path):
    """load_all_existing_ids finds IDs across year subdirectories."""
    (tmp_path / "2024").mkdir()
    with open(tmp_path / "2024" / "3.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date", "ISOWeek", "DOI", "Version", "Cat", "Title", "Authors"])
        w.writerow(["2024-01-15", 3, "10.1101/a", "1", "neuro", "A", "X"])
    (tmp_path / "2025").mkdir()
    with open(tmp_path / "2025" / "1.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date", "ISOWeek", "DOI", "Version", "Cat", "Title", "Authors"])
        w.writerow(["2025-01-06", 1, "10.1101/b", "2", "neuro", "B", "Y"])
    ids = load_all_existing_ids(str(tmp_path))
    assert ("10.1101/a", "1") in ids
    assert ("10.1101/b", "2") in ids
    assert len(ids) == 2


# --- quote-on-whitespace: keep CSVs unambiguous for downstream readers
#     when titles/authors/abstracts contain spaces ---


def test_write_file_quotes_cells_containing_whitespace(tmp_path):
    """Any cell with whitespace gets RFC-4180 double-quoted on write.
    Single-token cells (dates, DOIs, version numbers) stay bare so the
    output is not visually noisy."""
    year_dir = str(tmp_path / "2026")
    header = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors"]
    rows = [
        ["2026-05-21", 21, "10.x/a", "1", "scientific communication", "T One", "Smith"],
        ["2026-05-22", 21, "10.x/b", "1", "neuro", "TwoNoSpace", "Jones"],
    ]
    write_file(rows, "21", year_dir, header)
    raw = (tmp_path / "2026" / "21.csv").read_text(encoding="UTF8")
    lines = raw.strip().split("\n")
    assert lines[0] == "Date,ISOWeek,DOI,Version,Category,Title,Authors"
    assert '"scientific communication"' in lines[1]
    assert '"T One"' in lines[1]
    assert "2026-05-21," in lines[1]
    assert "10.x/a," in lines[1]
    assert "neuro" in lines[2]
    assert '"neuro"' not in lines[2]
    assert "TwoNoSpace" in lines[2]
    assert '"TwoNoSpace"' not in lines[2]


def test_write_file_quotes_cells_with_embedded_double_quote(tmp_path):
    """Embedded `"` is escaped as `""` per RFC 4180, and the cell is quoted."""
    year_dir = str(tmp_path / "2026")
    header = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors"]
    rows = [["2026-05-21", 21, "10.x/a", "1", "cat", 'He said "hi"', "Smith"]]
    write_file(rows, "21", year_dir, header)
    raw = (tmp_path / "2026" / "21.csv").read_text(encoding="UTF8")
    assert '"He said ""hi"""' in raw


# --- header upgrade on append: prevents pre-PR-#116 CSVs from silently
#     losing the Abstract/Authors columns when appended-to ---


def test_write_file_upgrades_header_when_passed_header_is_wider(tmp_path):
    """A pre-existing CSV with a 7-col header gets rewritten to the 8-col
    header when write_file is called with the wider header. Old data
    rows are padded with empty cells for the new trailing column(s)."""
    year_dir = tmp_path / "2026"
    year_dir.mkdir()
    out_file = year_dir / "21.csv"
    old_header = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors"]
    with open(out_file, "w", newline="", encoding="UTF8") as f:
        w = csv.writer(f)
        w.writerow(old_header)
        w.writerow(["2026-05-21", 21, "10.x/a", "1", "neuro", "Old A", "Smith"])
        w.writerow(["2026-05-21", 21, "10.x/b", "1", "neuro", "Old B", "Jones"])

    new_header = [*old_header, "Abstract"]
    new_rows = [["2026-05-22", 21, "10.x/c", "1", "neuro", "New C", "Doe", "abstract C"]]
    write_file(new_rows, "21", str(year_dir), new_header)

    with open(out_file, encoding="UTF8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == new_header
    pad = ""
    assert rows[1] == ["2026-05-21", "21", "10.x/a", "1", "neuro", "Old A", "Smith", pad]
    assert rows[2] == ["2026-05-21", "21", "10.x/b", "1", "neuro", "Old B", "Jones", pad]
    new_data = ["2026-05-22", "21", "10.x/c", "1", "neuro", "New C", "Doe", "abstract C"]
    assert rows[3] == new_data
    assert all(len(r) == 8 for r in rows)


def test_write_file_noop_when_header_already_matches(tmp_path):
    """No file mtime/content change when the existing header matches."""
    year_dir = tmp_path / "2026"
    year_dir.mkdir()
    out_file = year_dir / "21.csv"
    header = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors", "Abstract"]
    with open(out_file, "w", newline="", encoding="UTF8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(["2026-05-21", 21, "10.x/a", "1", "neuro", "A", "Smith", "abs A"])

    before = out_file.read_bytes()
    write_file([], "21", str(year_dir), header)
    assert out_file.read_bytes() == before


def test_write_file_skips_upgrade_when_existing_header_disagrees_with_prefix(tmp_path):
    """Refuses to upgrade when the existing header is NOT a strict prefix
    of the new one — e.g. legacy arXiv 'Weekday' (col 1) vs current
    'ISOWeek'. Renaming a column under the data's feet would silently
    corrupt downstream consumers; the safe default is to leave the
    legacy file alone."""
    year_dir = tmp_path / "2024"
    year_dir.mkdir()
    out_file = year_dir / "3.csv"
    legacy_header = ["Published", "Weekday", "Updated", "ID", "Version", "Title"]
    with open(out_file, "w", newline="", encoding="UTF8") as f:
        w = csv.writer(f)
        w.writerow(legacy_header)
        w.writerow(["2024-01-15", "Mon", "2024-01-15", "2401.00001", "1", "T"])

    current_header = [
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
    write_file([], "3", str(year_dir), current_header)

    with open(out_file, encoding="UTF8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == legacy_header
    assert rows[1] == ["2024-01-15", "Mon", "2024-01-15", "2401.00001", "1", "T"]


def test_write_file_does_not_truncate_header_when_passed_narrower(tmp_path):
    """Defensive: if a caller passes a narrower header than the file
    already has, do not destroy data. No-op on the header."""
    year_dir = tmp_path / "2026"
    year_dir.mkdir()
    out_file = year_dir / "21.csv"
    wide_header = ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors", "Abstract"]
    with open(out_file, "w", newline="", encoding="UTF8") as f:
        w = csv.writer(f)
        w.writerow(wide_header)
        w.writerow(["2026-05-21", 21, "10.x/a", "1", "neuro", "A", "Smith", "abs A"])

    narrower = wide_header[:-1]
    write_file([], "21", str(year_dir), narrower)

    with open(out_file, encoding="UTF8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == wide_header
    assert rows[1][-1] == "abs A"


# --- dedup_cols parametrize: proves schema-agnostic dedup ---


@pytest.mark.parametrize(
    ("dedup_cols", "header", "row_keep", "row_dup"),
    [
        (
            (2, 3),  # biorxiv: (DOI, Version)
            ["Date", "ISOWeek", "DOI", "Version", "Category", "Title", "Authors"],
            ["2024-01-15", 3, "10.1101/a", "1", "neuro", "A", "X"],
            ["2024-01-15", 3, "10.1101/a", "1", "neuro", "Dup", "Y"],
        ),
        (
            (3, 4),  # arxiv: (ID, Version) — Published/ISOWeek/Updated come first
            ["Published", "ISOWeek", "Updated", "ID", "Version", "Title", "Categories"],
            ["2026-03-23T17:00:00Z", 13, "2026-03-23T17:00:00Z", "2603.00001", "1", "'T'", "cs"],
            ["2026-03-23T17:00:00Z", 13, "2026-03-23T17:00:00Z", "2603.00001", "1", "'D'", "cs"],
        ),
    ],
)
def test_dedup_cols_parametrize(tmp_path, dedup_cols, header, row_keep, row_dup):
    """write_file/load_all_existing_ids/filter_new_rows respect dedup_cols.

    Default (2, 3) covers biorxiv (DOI, Version). Arxiv schema uses (3, 4)
    (ID, Version). Both paths must dedupe correctly without sharing keys.
    """
    year_dir = str(tmp_path / "2026")
    write_file([row_keep], "13", year_dir, header, dedup_cols=dedup_cols)
    write_file([row_dup], "13", year_dir, header, dedup_cols=dedup_cols)
    out_file = tmp_path / "2026" / "13.csv"
    with open(out_file) as f:
        rows = list(csv.reader(f))
    assert len(rows) == 2  # header + 1 data row (dup filtered)

    ids = load_all_existing_ids(str(tmp_path), dedup_cols=dedup_cols)
    expected_key = (row_keep[dedup_cols[0]], str(row_keep[dedup_cols[1]]))
    assert expected_key in ids

    new = filter_new_rows(
        [row_keep, ["2026-03-24T00:00:00Z", 13, "u", "fresh", "1", "x", "y"]],
        ids,
        dedup_cols=dedup_cols,
    )
    assert len(new) == 1
