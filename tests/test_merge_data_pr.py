"""Tests for scripts/merge_data_pr.sh (merges the data PR without bypassing branch rules)."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "merge_data_pr.sh"

# A stand-in for the gh CLI: logs every call, answers `pr merge --auto` per
# FAKE_AUTO, and answers `pr view` from a queue of "STATE MERGE_STATE" lines
# (the last line repeats once the queue is down to one).
FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
case "$1 $2" in
  "pr merge") [ "$FAKE_AUTO" = ok ] ;;
  "pr view")
    head -n 1 "$FAKE_STATES"
    if [ "$(wc -l < "$FAKE_STATES")" -gt 1 ]; then sed -i 1d "$FAKE_STATES"; fi ;;
  *) exit 0 ;;
esac
"""


def _run(tmp_path: Path, states: list[str], *, auto: bool, timeout: int = 60):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH, encoding="UTF8")
    gh.chmod(0o755)
    (tmp_path / "states").write_text("\n".join(states) + "\n", encoding="UTF8")
    log = tmp_path / "gh.log"
    log.touch()
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LOG": str(log),
        "FAKE_STATES": str(tmp_path / "states"),
        "FAKE_AUTO": "ok" if auto else "fail",
        "REPO": "owner/repo",
        "MERGE_TIMEOUT": str(timeout),
        "POLL_INTERVAL": "0",
    }
    cmd = ["bash", str(SCRIPT), "7", "chore: update ./data/arxiv"]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)  # noqa: S603
    return result, log.read_text(encoding="UTF8").splitlines()


def test_auto_merge_waits_for_the_merge_without_merging_directly(tmp_path):
    result, calls = _run(tmp_path, ["OPEN BLOCKED", "OPEN BLOCKED", "MERGED UNKNOWN"], auto=True)

    assert result.returncode == 0
    assert calls[0].startswith("pr merge 7 --repo owner/repo --auto --squash")
    assert not any("pulls/7/merge" in c for c in calls)


def test_falls_back_to_a_direct_merge_once_required_checks_pass(tmp_path):
    result, calls = _run(tmp_path, ["OPEN BLOCKED", "OPEN CLEAN", "MERGED UNKNOWN"], auto=False)

    assert result.returncode == 0
    merges = [c for c in calls if "repos/owner/repo/pulls/7/merge" in c]
    assert len(merges) == 1
    assert "merge_method=squash" in merges[0]


def test_updates_a_branch_that_fell_behind_a_strict_base(tmp_path):
    result, calls = _run(tmp_path, ["OPEN BEHIND", "OPEN BLOCKED", "MERGED UNKNOWN"], auto=True)

    assert result.returncode == 0
    assert any("repos/owner/repo/pulls/7/update-branch" in c for c in calls)


def test_fails_when_the_pr_is_closed_or_conflicts(tmp_path):
    closed, _ = _run(tmp_path / "a", ["CLOSED UNKNOWN"], auto=True)
    dirty, _ = _run(tmp_path / "b", ["OPEN DIRTY"], auto=True)

    assert closed.returncode == 1
    assert "closed without merging" in closed.stdout
    assert dirty.returncode == 1
    assert "conflicts" in dirty.stdout


def test_fails_and_leaves_the_pr_open_after_the_timeout(tmp_path):
    result, calls = _run(tmp_path, ["OPEN BLOCKED"], auto=True, timeout=0)

    assert result.returncode == 1
    assert "not merged after 0s" in result.stdout
    assert not any(c.startswith("pr close") for c in calls)
