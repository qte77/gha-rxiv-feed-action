# gha-rxiv-feed-action

> gha-rxiv-feed-action is a GitHub Action that logs a weekly CSV feed of new
> [arXiv](https://arxiv.org/), [bioRxiv](https://www.biorxiv.org/), and
> [medRxiv](https://www.medrxiv.org/) papers for selected categories, for
> downstream paper-evaluation pipelines.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.4-blue.svg)](CHANGELOG.md)
[![CodeQL](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/codeql.yml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/codeql.yml)
[![CodeFactor](https://www.codefactor.io/repository/github/qte77/gha-rxiv-feed-action/badge)](https://www.codefactor.io/repository/github/qte77/gha-rxiv-feed-action)
[![Tests](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/test.yml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/test.yml)
[![Ruff](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/ruff.yml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/ruff.yml)
[![Update rxiv feed](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/update-rxiv-feed.yaml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/update-rxiv-feed.yaml)
[![Dependabot](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/dependabot/dependabot-updates)

## What

- Fetches new papers from the selected `SERVER` (arXiv by default; bioRxiv or medRxiv on request)
- Filters by arXiv `TOPICS` or bioRxiv/medRxiv `CATEGORIES`
- Writes one CSV per ISO week to `./data/<server>/<year>/<isoweek>.csv`, deduped by `(ID|DOI, Version)`
- Carries title, authors, and abstract on every row; optional Semantic Scholar citation counts for arXiv
- Backfills any historic window via `DATE_FROM`/`DATE_TO`
- Opens a PR with the updated data and auto-merges it via squash
- Cron cadence is set by the calling workflow

## How

Default: fetch the last week of arXiv submissions in CS/AI categories.

```yaml
- uses: qte77/gha-rxiv-feed-action@v0.2.2
  with:
    TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

See [`docs/usage.md`](docs/usage.md) for bioRxiv/medRxiv, multi-server
matrices, backfill dispatches, the full inputs table, and versioning;
[`docs/data.md`](docs/data.md) for the API sources and CSV schemas.

## Why

Existing arXiv-digest bots post keyword matches as issues for humans to
read, and cover arXiv only. This action instead persists a normalized,
deduped weekly CSV across arXiv, bioRxiv, and medRxiv, so a separate
evaluation step can consume one schema. See
[`docs/landscape.md`](docs/landscape.md) and
[`docs/userstory.md`](docs/userstory.md).

## Refs

- [`docs/usage.md`](docs/usage.md) — examples, inputs, versioning
- [`docs/data.md`](docs/data.md) — API sources and CSV schemas
- [`docs/architecture.md`](docs/architecture.md) — data flow and invariants
- [`docs/categories.md`](docs/categories.md) — per-server taxonomy reference
- [`docs/landscape.md`](docs/landscape.md) — competitive scan of similar feed bots
- [`docs/roadmap.md`](docs/roadmap.md) — narrative summary; issues are the source of truth
- [`docs/userstory.md`](docs/userstory.md) — who this serves
- [`CHANGELOG.md`](CHANGELOG.md) — changes

## License

Apache-2.0 — see [LICENSE](LICENSE).
