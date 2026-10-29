# gha-rxiv-feed-action

Logs a weekly CSV feed of papers submitted to [arXiv](https://arxiv.org/),
[bioRxiv](https://www.biorxiv.org/), and [medRxiv](https://www.medrxiv.org/)
for selected categories. Cron cadence is set by the calling workflow.

![Version](https://img.shields.io/badge/version-0.2.4-8A2BE2)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Update rxiv feed](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/update-rxiv-feed.yaml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/update-rxiv-feed.yaml)
[![CodeFactor](https://www.codefactor.io/repository/github/qte77/gha-rxiv-feed-action/badge)](https://www.codefactor.io/repository/github/qte77/gha-rxiv-feed-action)
[![CodeQL](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/codeql.yml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/codeql.yml)
[![Dependabot](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/dependabot/dependabot-updates)
[![Ruff](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/ruff.yml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/ruff.yml)
[![Tests](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/test.yml/badge.svg)](https://github.com/qte77/gha-rxiv-feed-action/actions/workflows/test.yml)

## What it does

1. Checks out the calling repository
2. Sets up Python via uv
3. Fetches paper stats from the selected `SERVER` (arXiv by default; bioRxiv or medRxiv on request)
4. Writes results to CSV files in `./data/<server>/`
5. Opens a PR with the updated data (auto-merges via squash)

## Usage

Default: fetch the last week of arXiv submissions in CS/AI categories.

```yaml
- uses: qte77/gha-rxiv-feed-action@v0.2.2
  with:
    TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### arXiv with custom topics + citation enrichment

```yaml
- uses: qte77/gha-rxiv-feed-action@v0.2.2
  with:
    TOPICS: "cat:cs.CV+OR+cat:cs.LG"
    INCLUDE_CITATIONS: "true"
    SEMANTIC_SCHOLAR_API_KEY: ${{ secrets.SEMANTIC_SCHOLAR_KEY }}
    TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### bioRxiv / medRxiv

```yaml
- uses: qte77/gha-rxiv-feed-action@v0.2.2
  with:
    SERVER: "biorxiv"
    OUT_DIR: "./data/biorxiv"
    CATEGORIES: "neuroscience,bioinformatics"
    TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Multi-server matrix

```yaml
strategy:
  max-parallel: 1   # serialize to avoid concurrent auto-PR merges
  matrix:
    include:
      - server: arxiv
        topics: "cat:cs.CV+OR+cat:cs.LG"
      - server: biorxiv
        categories: "bioinformatics,microbiology"
      - server: medrxiv
        categories: "infectious diseases,genetic and genomic medicine"
steps:
  - uses: qte77/gha-rxiv-feed-action@v0.2.2
    with:
      OUT_DIR: "./data/${{ matrix.server }}"
      SERVER: ${{ matrix.server }}
      TOPICS: ${{ matrix.topics }}
      CATEGORIES: ${{ matrix.categories }}
      TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Manual backfill via workflow_dispatch

The reference workflow at `.github/workflows/update-rxiv-feed.yaml`
accepts `date_from`, `date_to`, and `server` inputs so any historic
window can be re-fetched without editing the workflow file:

```bash
gh workflow run update-rxiv-feed.yaml \
  -f date_from=2026-03-09 -f date_to=2026-05-17 -f server=biorxiv
```

Defaults are empty strings, so the scheduled cron behaviour is
preserved exactly. `server` empty = run all three.

## Versioning

No floating major tag — pin `@vX.Y.Z` or a commit SHA in `uses:`.

Releases are automated in two steps: run the **Bump version** workflow
(`workflow_dispatch`; pick major/minor/patch) to open a `chore(release)`
PR, then merge it. Merging changes `pyproject.toml`, which triggers **Tag
and Release** to tag `vX.Y.Z` on the `main` merge commit and publish the
GitHub Release from the matching [`CHANGELOG.md`](CHANGELOG.md) section.
No moving/major tag is created.

## Inputs

| Name | Required | Default | Description |
| ---- | -------- | ------- | ----------- |
| `SERVER` | No | `arxiv` | API server: `arxiv`, `biorxiv`, or `medrxiv`. |
| `OUT_DIR` | No | `./data/arxiv` | Directory to write CSV output files. Convention: `./data/<server>` so multiple servers can coexist when using a matrix. |
| `TOPICS` | No | `cat:cs.CV+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.AI+OR+cat:cs.NE+OR+cat:cs.RO` | arXiv search_query (URL-encoded, OR-joined). See [`docs/categories.md`](docs/categories.md#arxiv). arXiv only. |
| `INCLUDE_CITATIONS` | No | `false` | Enrich arXiv rows with Semantic Scholar citation counts. arXiv only. |
| `SEMANTIC_SCHOLAR_API_KEY` | No | _(empty)_ | Reserved for higher Semantic Scholar rate limits — **not yet implemented** (currently a no-op; the key is not read or sent). Tracked in [#105](https://github.com/qte77/gha-rxiv-feed-action/issues/105). arXiv only. |
| `MAX_AGE_DAYS` | No | `7` | Skip arXiv papers published more than N days ago. Ignored when `DATE_FROM` is set. arXiv only. |
| `DATE_FROM` | No | _(empty)_ | YYYY-MM-DD lower bound. **arXiv**: bounds `submittedDate` (empty uses `MAX_AGE_DAYS`). **bioRxiv/medRxiv**: overrides the rolling `DAYS` window (empty uses `DAYS`). Useful for backfill dispatches. |
| `DATE_TO` | No | _(empty)_ | YYYY-MM-DD upper bound. Empty = today. Server semantics mirror `DATE_FROM`. |
| `PAGE_SIZE` | No | `1000` | arXiv pagination page size. arXiv only. |
| `MAX_PAGES` | No | `5` | Cap on arXiv pagination pages per run. arXiv only. |
| `DAYS` | No | `1` | Number of days back to fetch. bioRxiv/medRxiv only. |
| `CATEGORIES` | No | _(empty)_ | Comma-separated bioRxiv/medRxiv categories to keep. See [`docs/categories.md`](docs/categories.md). bioRxiv/medRxiv only. |
| `SEED_ONLY` | No | `false` | When `true`, skip fetching and only write a header-only CSV for the current ISO week if absent (avoids a 404 for consumers polling the in-progress week). |
| `TOKEN` | No | `${{ github.token }}` | GitHub token for pushing changes. |

## API

Data sourced from:

- arXiv: `https://export.arxiv.org/api/query?search_query={topics}&start={n}&max_results={k}&sortBy=submittedDate` (Atom XML)
- bioRxiv: `https://api.biorxiv.org/details/biorxiv/{date1}/{date2}/{cursor}/json`
- medRxiv: `https://api.biorxiv.org/details/medrxiv/{date1}/{date2}/{cursor}/json`

Outbound requests are locked to an allowlist of API hosts
(`api.biorxiv.org`, `export.arxiv.org`, `api.semanticscholar.org`) and
require HTTPS on port 443; non-allowlisted hosts raise `ValueError` at
the validator boundary. Extend `_ALLOWED_HOSTS` in
`src/fetchers/common.py` when adding a new fetcher.

## Data

`data/<server>/<year>/<isoweek>.csv` — one CSV per ISO week per server.
The action appends new rows on each run and dedupes by
`(DOI, Version)` for bioRxiv/medRxiv or `(ID, Version)` for arXiv.

Current schemas:

- **arXiv** (9 cols): `Published, ISOWeek, Updated, ID, Version, Title, Categories, Authors, Abstract`
- **bioRxiv / medRxiv** (8 cols): `Date, ISOWeek, DOI, Version, Category, Title, Authors, Abstract`

Schema is append-only: new columns ship as minor-version bumps; existing
column indices never shift, so downstream consumers can pin a minimum
producer version. `Authors`/`Abstract` were added in v0.2.2. Pre-existing
CSVs keep their narrower schema; the loader and prune step tolerate
mixed widths and dedup key indices are unchanged across versions.
For a one-shot backfill, dispatch with `DATE_FROM`/`DATE_TO` set to a
wide window — `filter_new_rows` still dedupes, so this fills _gaps_ in
coverage. To rewrite narrow-schema rows in place, clear the data
directory first.

`data/arxiv/` is also pre-populated with 16 historical weekly CSVs
migrated from [`qte77/gha-arxiv-stats-action-legacy`](https://github.com/qte77/gha-arxiv-stats-action-legacy)
(formerly `gha-arxiv-stats-action`; archived after the fold-in) when
this action absorbed its scope (issue #72). The 6 files under
`data/arxiv/2024/` use a legacy 6-column schema
(`Published,Weekday,Updated,ID,Version,Title`); 2026 files use the
7-col schema with `Categories`; new writes use the 9-col schema above.
Dedup key columns are at the same indices across all three.

## Docs

- [`docs/landscape.md`](docs/landscape.md) — competitive scan of similar arxiv-feed bots.
- [`docs/architecture.md`](docs/architecture.md) — data flow + invariants.
- [`docs/categories.md`](docs/categories.md) — per-server taxonomy reference.
- [`docs/roadmap.md`](docs/roadmap.md) — narrative summary; issues are source of truth.
- [`docs/userstory.md`](docs/userstory.md) — who this serves.

## License

Apache-2.0 — see [LICENSE](LICENSE).
