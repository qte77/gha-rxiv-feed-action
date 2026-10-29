# Roadmap

Lightweight tracking of intent. Issues + the milestone view on GitHub
are the source of truth; this file is the narrative summary — it holds
only what issues can't express: sequencing and long-term architectural
bets.

## Short-term (in flight)

- **arXiv CSV schema alignment** (`Published`→`Date`, `ID`→`DOI`,
  `Categories`→`Category`) to match the canonical bioRxiv/medRxiv
  schema and unblock downstream consumers (paperverse, eval action).
  Breaking → v0.3.0. Urgent (issue #107).
- **Citation enrichment for bioRxiv/medRxiv DOIs** via Semantic Scholar
  `DOI:` lookups — feature parity with arXiv. Also wires the currently
  no-op `SEMANTIC_SCHOLAR_API_KEY` and routes the call through the URL
  allowlist (issue #105).
- **Week-start stub CSV** — publish a header-only CSV on Monday so
  consumers polling the in-progress week get an empty file, not a 404
  (issue #134).
- Backfill arXiv historic weeks 11–19 with the new
  `Authors`+`Abstract` schema — a single `gh workflow run` with
  `date_from`/`date_to` now that #129 and #132 have merged.

## Medium-term

- **OSF-backed fetchers (psyArXiv + SocArxiv)** — both ride the same
  OSF JSON:API substrate (`api.osf.io`), so batch them. ~~psyArXiv
  (issue #70)~~: `src/fetchers/osf.py`, top-level subjects as
  `Category`, `Authors` empty. Open: SocArxiv (issue #99, one
  `_OSF_SERVERS` entry) and an authors/N+1 strategy
  (`docs/categories.md`).
- **chemRxiv fetcher** — *blocked*: the Figshare/ACS public API is
  Cloudflare-fronted and returns a challenge page to CI runners, so it
  can't be fetched or tested unattended. Deferred until an official
  client or a non-gated endpoint exists (issue #69).
- **Backfill orchestration helper** — small script that loops
  `gh workflow run` over a series of monthly windows for very long
  backfills (the arXiv API caps at ~50k results per query).

## Long-term

- **Incremental dedup at the API boundary** — bio/med pagination
  currently fetches every cursor and dedupes client-side; smarter
  cursor stops once `since_doi` is seen would save bandwidth on
  unchanged historic weeks.
- **Schema versioning column** — explicit `SchemaVersion` column on
  each row so downstream consumers can branch on row format instead
  of column-count sniffing.
- **`scripts/migrate_csv_schema.py` re-run hook** — automate the
  one-shot migration when the schema grows again, integrated into
  the release workflow.
