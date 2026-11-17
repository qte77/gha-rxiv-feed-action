#!/usr/bin/env bash
# Squash-merge the data PR the action just opened, without bypassing branch rules.
#
# Usage: REPO=owner/name merge_data_pr.sh PR_NUMBER COMMIT_TITLE
#
# A merge right after the PR opens is refused (HTTP 405) when the base branch
# requires status checks that have not reported yet. So: enable auto-merge
# (squash) when the repo allows it, otherwise merge directly once the PR is
# mergeable. Either way, wait until the PR is merged, so a serialized matrix
# (max-parallel: 1) starts its next PR from the updated base. A PR that falls
# behind a base requiring up-to-date branches is updated. On a closed or
# conflicting PR, or after MERGE_TIMEOUT seconds (default 900), exit 1 and leave
# the PR open; auto-merge, if enabled, still merges it later.
set -euo pipefail

pr="${1:?usage: merge_data_pr.sh PR_NUMBER COMMIT_TITLE}"
title="${2:?usage: merge_data_pr.sh PR_NUMBER COMMIT_TITLE}"
repo="${REPO:?REPO (owner/name) is required}"
timeout="${MERGE_TIMEOUT:-900}"
interval="${POLL_INTERVAL:-15}"

auto=false
if gh pr merge "$pr" --repo "$repo" --auto --squash --subject "$title"; then
  auto=true
else
  echo "Auto-merge unavailable; merging PR #$pr directly once it is mergeable."
fi

deadline=$((SECONDS + timeout))
while :; do
  status=$(gh pr view "$pr" --repo "$repo" --json state,mergeStateStatus \
    --jq '.state + " " + .mergeStateStatus') || status="UNKNOWN UNKNOWN"
  state="${status%% *}"
  merge_state="${status#* }"
  case "$state" in
    MERGED) echo "PR #$pr merged."; exit 0 ;;
    CLOSED) echo "::error::PR #$pr was closed without merging."; exit 1 ;;
  esac
  case "$merge_state" in
    DIRTY) echo "::error::PR #$pr conflicts with its base branch; left open."; exit 1 ;;
    BEHIND) gh api -X PUT "repos/$repo/pulls/$pr/update-branch" > /dev/null || true ;;
    CLEAN | UNSTABLE | HAS_HOOKS)
      if [ "$auto" = false ]; then
        gh api -X PUT "repos/$repo/pulls/$pr/merge" \
          -f merge_method=squash -f commit_title="$title" > /dev/null || true
      fi ;;
  esac
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "::error::PR #$pr not merged after ${timeout}s; left open."
    exit 1
  fi
  sleep "$interval"
done
