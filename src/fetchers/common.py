"""Shared fetcher utilities: HTTP client, URL validator, dedup + CSV I/O.

Per-server fetchers (biorxiv.py, arxiv.py) import from this module. The
``dedup_cols`` keyword on the dedup/IO functions makes them schema-agnostic:
biorxiv passes ``(2, 3)`` (DOI, Version); arxiv will pass ``(3, 4)`` (ID,
Version). Defaults match the biorxiv schema for backwards compatibility.
"""

import csv
import os
import time
from os import makedirs
from os.path import dirname, exists
from typing import TextIO
from urllib.parse import urlparse

import requests

# Hosts the action is permitted to fetch from. Extend this set when adding a
# new fetcher (e.g. chemrxiv, socarxiv).
_ALLOWED_HOSTS = frozenset(
    {
        "api.biorxiv.org",
        "export.arxiv.org",
        "api.semanticscholar.org",
        "api.osf.io",
    }
)


def scrub_newlines(value: object) -> str:
    r"""Collapse ``\n``/``\r`` in a cell to single spaces for CSV cleanliness.

    csv.writer quotes embedded newlines correctly per RFC 4180, but viewers
    that aren't CSV-aware (``cat``, ``wc -l``, GitHub raw blob, plain text
    editors) treat each newline as a row boundary and fragment the display.
    Applied to free-text columns (title, abstract) in both fetchers.
    """
    return str(value).translate({ord("\n"): " ", ord("\r"): " "})


def _validate_url(url: str) -> None:
    """Reject non-HTTPS URLs and hosts outside the API allowlist.

    Stricter than a scheme-prefix check: parses the URL and rejects
    userinfo (URL-confusion attacks), fragments (construction bugs),
    non-443 ports (SSRF guard), and hosts not in ``_ALLOWED_HOSTS``.
    """
    parts = urlparse(url)
    if parts.scheme != "https":
        raise ValueError(f"Only HTTPS URLs are allowed, got: {url[:80]}")
    if parts.username or parts.password:
        raise ValueError(f"Userinfo not allowed in URL: {url[:80]}")
    if parts.fragment:
        raise ValueError(f"Fragment not allowed in URL: {url[:80]}")
    if parts.port not in (None, 443):
        raise ValueError(f"Non-443 port not allowed: {url[:80]}")
    if parts.hostname not in _ALLOWED_HOSTS:
        raise ValueError(f"Host not in allowlist: {parts.hostname}")


def get_api_response(url: str, max_retries: int = 3, backoff_base: float = 2.0) -> bytes:
    """Fetch URL with retry/backoff. Raises RuntimeError after max_retries."""
    _validate_url(url)
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep(backoff_base**attempt)
            else:
                raise RuntimeError(f"API failed after {max_retries} attempts: {url}") from None
    raise RuntimeError(f"API not attempted (max_retries={max_retries}): {url}")


def _load_existing_ids(out_file: str, dedup_cols: tuple[int, int] = (2, 3)) -> set[tuple[str, str]]:
    """Load set of (id, version) tuples from existing CSV for dedup.

    ``dedup_cols`` is a 2-tuple of column indices into each CSV row that
    together form the dedup key. Default ``(2, 3)`` matches biorxiv's
    ``[Date, ISOWeek, DOI, Version, ...]`` schema. Arxiv passes ``(3, 4)``
    for ``[Published, ISOWeek, Updated, ID, Version, ...]``.
    """
    existing: set[tuple[str, str]] = set()
    id_col, ver_col = dedup_cols
    min_len = max(id_col, ver_col) + 1
    if exists(out_file):
        with open(out_file, newline="", encoding="UTF8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= min_len:
                    existing.add((row[id_col], str(row[ver_col])))
    return existing


def load_all_existing_ids(
    data_dir: str, dedup_cols: tuple[int, int] = (2, 3)
) -> set[tuple[str, str]]:
    """Load all dedup keys from CSVs in data_dir/YYYY/ subdirs."""
    existing: set[tuple[str, str]] = set()
    if not exists(data_dir):
        return existing
    for entry in os.listdir(data_dir):
        subdir = os.path.join(data_dir, entry)
        if not os.path.isdir(subdir) or not entry.isdigit():
            continue
        for fname in os.listdir(subdir):
            if fname.endswith(".csv"):
                existing.update(_load_existing_ids(os.path.join(subdir, fname), dedup_cols))
    return existing


def filter_new_rows(
    rows: list[list], existing_ids: set[tuple[str, str]], dedup_cols: tuple[int, int] = (2, 3)
) -> list[list]:
    """Filter out rows whose dedup key is already in ``existing_ids``."""
    id_col, ver_col = dedup_cols
    return [row for row in rows if (row[id_col], str(row[ver_col])) not in existing_ids]


def _csv_quote(value: object) -> str:
    """RFC-4180 quote a CSV cell, also quoting on any whitespace.

    Standard ``csv.writer(QUOTE_MINIMAL)`` only quotes when a cell holds
    the delimiter, the quotechar, or a newline. Cells containing internal
    whitespace (``"scientific communication and education"``,
    ``"He smiled and left"``) round-trip fine but read ambiguously to
    humans scanning the raw file. This helper additionally quotes any
    cell whose ``str()`` contains a whitespace character, doubling
    internal ``"`` per the spec.
    """
    s = str(value)
    needs_quote = '"' in s or "," in s or "\n" in s or "\r" in s or any(c.isspace() for c in s)
    if needs_quote:
        return '"' + s.replace('"', '""') + '"'
    return s


def _write_csv_row(f: TextIO, row: list) -> None:
    r"""Write one row using :func:`_csv_quote` per cell, ``\n`` terminator."""
    f.write(",".join(_csv_quote(c) for c in row))
    f.write("\n")


def upgrade_csv_header(out_file: str, new_header: list) -> bool:
    """Rewrite ``out_file`` header to ``new_header`` when safely append-only.

    The existing header must equal ``new_header[:N]`` where N is the
    existing column count. Pads each data row with empty cells for the
    added trailing columns.

    Safety rule: upgrade is only allowed when columns are *appended* —
    never when an existing column would be semantically renamed (e.g.
    legacy arXiv ``Weekday`` at col 1 vs current ``ISOWeek``). No-op
    (returns ``False``) on any mismatch, when the file is missing, or
    when ``new_header`` is not strictly wider.
    """
    if not exists(out_file):
        return False
    with open(out_file, newline="", encoding="UTF8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return False
    old_header = rows[0]
    new_header_list = list(new_header)
    if len(new_header_list) <= len(old_header):
        return False
    if old_header != new_header_list[: len(old_header)]:
        return False
    pad = [""] * (len(new_header_list) - len(old_header))
    with open(out_file, "w", newline="", encoding="UTF8") as f:
        _write_csv_row(f, new_header_list)
        for row in rows[1:]:
            _write_csv_row(f, row + pad)
    return True


def write_file(
    content: list[list],
    file_name: str,
    out_dir: str = ".",
    header: list[str] | None = None,
    dedup_cols: tuple[int, int] = (2, 3),
) -> None:
    """Write rows to a CSV file, creating or upgrading the header as needed.

    Dedupes against existing rows on the ``dedup_cols`` key pair. When a
    wider ``header`` is passed and the file already has a narrower one,
    the file is rewritten with the wider header and old rows padded — so a
    schema growth (#116: Abstract/Authors) takes effect on appended-to
    CSVs, not just newly created ones.
    """
    out_file = f"{out_dir}/{file_name}.csv"
    if not exists(out_file):
        makedirs(dirname(out_file) if dirname(out_file) else out_dir, exist_ok=True)
        with open(out_file, mode="w+", newline="", encoding="UTF8") as f:
            if header:
                _write_csv_row(f, header)
    elif header:
        upgrade_csv_header(out_file, header)
    existing = _load_existing_ids(out_file, dedup_cols)
    id_col, ver_col = dedup_cols
    new_rows = [row for row in content if (row[id_col], str(row[ver_col])) not in existing]
    if new_rows:
        with open(out_file, mode="a+", newline="", encoding="UTF8") as f:
            for row in new_rows:
                _write_csv_row(f, row)
