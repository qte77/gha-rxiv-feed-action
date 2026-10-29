# Data and API

Where the rows come from and how they are laid out on disk.

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
