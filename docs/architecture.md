# Architecture

How a single weekly run flows from cron trigger to merged data PR.

## Data flow

```text
   cron (Mon 01:00 UTC)        gh workflow run --ref main -f ...
            │                              │
            └──────────────┬───────────────┘
                           ▼
       .github/workflows/update-rxiv-feed.yaml
       (3-leg matrix: arxiv | biorxiv | medrxiv;
        vars.* override defaults; workflow_dispatch
        inputs.{date_from,date_to,server} per leg)
                           │
                           ▼
                    action.yaml (composite)
                  ┌────────┴────────┐
                  ▼                 ▼
            checkout              setup-uv
                  ▼                 ▼
                  └────────┬────────┘
                           ▼
                       src/app.py
                       main() ─── validate_env() ──── src/validation.py
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       _run_arxiv()              _run_biorxiv()
         │   │                     │   │
         ▼   ▼                     ▼   ▼
   build_date_query        build_date_range
   get_total_results       parse_biorxiv_json
   get_parsed_output       needs_pagination
   (src/fetchers/arxiv.py) prune_existing_csvs
                           (src/fetchers/biorxiv.py)
              │                         │
              └─────────┬───────────────┘
                        ▼
               src/fetchers/common.py
   (get_api_response  scrub_newlines
    _validate_url     load_all_existing_ids
    filter_new_rows   write_file
    upgrade_csv_header _write_csv_row)
                        │
                        ▼
                 ./data/<server>/<year>/<isoweek>.csv
                        │
                        ▼
       action.yaml step: "Commit via PR if changes"
       (git add → blob/tree/commit via gh api →
        branch → pull request → squash-merge → branch delete)
                        │
                        ▼
                    main branch
```

## Component responsibilities

| Module / file | Responsibility |
|---|---|
| `.github/workflows/update-rxiv-feed.yaml` | Cron + dispatch trigger; matrix per server; vars + workflow_dispatch input plumbing. |
| `action.yaml` | Composite action: checkout, uv setup, env-var contract for `src/app.py`, auto-PR commit step. |
| `src/app.py` | Env → dispatch by `SERVER`; per-server runner orchestrates fetch, dedup, write. |
| `src/validation.py` | Validate env at process entry; reject malformed `DAYS`/`DATE_FROM`/`DATE_TO`/`SERVER` before any I/O. |
| `src/fetchers/arxiv.py` | Atom XML parse; arXiv URL/date helpers; category filtering. |
| `src/fetchers/biorxiv.py` | JSON parse; pagination signal; rolling-vs-explicit date range; prune-by-category for existing CSVs. |
| `src/fetchers/common.py` | HTTP retry + URL allowlist; CSV write + dedup + header-upgrade; `scrub_newlines` helper. |
| `src/fetchers/arxiv_citations.py` | Optional Semantic Scholar enrichment for arXiv (`ARXIV:`) and bioRxiv/medRxiv (`DOI:`) rows, via the allowlisted HTTP client. |
| `scripts/enum_medrxiv_categories.py` | One-off: re-derive the canonical medRxiv category list (annual). |
| `scripts/migrate_csv_schema.py` | One-shot: widen existing CSV headers + pad rows when the schema grows. |

## Invariants

- **No network or filesystem at import time.** `import src.app` is
  cheap; all side-effects live inside `main()` or `_run_*`. Same for
  `src/fetchers/*` — pure parsers, network in `common.py` only.
- **Dedup key column indices are stable** across schema growth:
  bioRxiv `(2, 3) = (DOI, Version)`; arXiv `(3, 4) = (ID, Version)`.
  Schema columns are always *appended* — never reordered.
- **Outbound HTTP is allowlisted.** `_ALLOWED_HOSTS` in
  `src/fetchers/common.py` is the choke point; new fetchers extend it.
- **CSV writes are idempotent.** `write_file` dedupes against
  existing rows before append; re-running a window doesn't duplicate.
