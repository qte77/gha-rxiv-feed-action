"""Tests for scripts/weekly_svg.sh (bash + awk SVG renderer)."""

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "weekly_svg.sh"
FIXTURES = Path(__file__).parent / "fixtures" / "weekly_svg" / "biorxiv"


def _render(data_dir: Path, out: Path, *args: str) -> str:
    subprocess.run(["bash", str(SCRIPT), str(data_dir), str(out), *args], check=True)  # noqa: S603, S607
    return out.read_text(encoding="UTF8")


def _bar_titles(svg: str) -> list[str]:
    root = ET.fromstring(svg)  # noqa: S314 - trusted local output
    ns = "{http://www.w3.org/2000/svg}"
    return [t.text for r in root.iter(f"{ns}rect") if (t := r.find(f"{ns}title")) is not None]


def test_counts_csv_records_per_iso_week_in_chronological_order(tmp_path):
    svg = _render(FIXTURES, tmp_path / "weekly.svg")

    # 2026/2.csv has 3 records over 4 data lines (one quoted embedded newline);
    # 2026/10.csv is header-only; weeks sort numerically, not lexically.
    assert _bar_titles(svg) == [
        "2025-W52: 1 papers",
        "2026-W01: 2 papers",
        "2026-W02: 3 papers",
        "2026-W10: 0 papers",
    ]


def test_limits_to_last_n_weeks(tmp_path):
    svg = _render(FIXTURES, tmp_path / "weekly.svg", "2")

    assert _bar_titles(svg) == ["2026-W02: 3 papers", "2026-W10: 0 papers"]


def test_svg_is_theme_aware_and_deterministic(tmp_path):
    first = _render(FIXTURES, tmp_path / "a.svg")
    second = _render(FIXTURES, tmp_path / "b.svg")

    assert first == second
    assert "@media (prefers-color-scheme: dark)" in first
    assert re.search(r"<title>biorxiv: papers per ISO week</title>", first)


def test_empty_data_dir_renders_placeholder(tmp_path):
    (tmp_path / "data").mkdir()
    svg = _render(tmp_path / "data", tmp_path / "weekly.svg")

    assert _bar_titles(svg) == []
    assert "No data yet" in svg
