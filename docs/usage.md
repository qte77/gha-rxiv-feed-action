# Usage

Full reference for the composite action: examples, inputs, and the
release/versioning policy. The [README](../README.md) keeps only a
minimal example.

## Examples

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

## Inputs

| Name | Required | Default | Description |
| ---- | -------- | ------- | ----------- |
| `SERVER` | No | `arxiv` | API server: `arxiv`, `biorxiv`, or `medrxiv`. |
| `OUT_DIR` | No | `./data/arxiv` | Directory to write CSV output files. Convention: `./data/<server>` so multiple servers can coexist when using a matrix. |
| `TOPICS` | No | `cat:cs.CV+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.AI+OR+cat:cs.NE+OR+cat:cs.RO` | arXiv search_query (URL-encoded, OR-joined). See [`docs/categories.md`](categories.md#arxiv). arXiv only. |
| `INCLUDE_CITATIONS` | No | `false` | Enrich arXiv rows with Semantic Scholar citation counts. arXiv only. |
| `SEMANTIC_SCHOLAR_API_KEY` | No | _(empty)_ | Reserved for higher Semantic Scholar rate limits — **not yet implemented** (currently a no-op; the key is not read or sent). Tracked in [#105](https://github.com/qte77/gha-rxiv-feed-action/issues/105). arXiv only. |
| `MAX_AGE_DAYS` | No | `7` | Skip arXiv papers published more than N days ago. Ignored when `DATE_FROM` is set. arXiv only. |
| `DATE_FROM` | No | _(empty)_ | YYYY-MM-DD lower bound. **arXiv**: bounds `submittedDate` (empty uses `MAX_AGE_DAYS`). **bioRxiv/medRxiv**: overrides the rolling `DAYS` window (empty uses `DAYS`). Useful for backfill dispatches. |
| `DATE_TO` | No | _(empty)_ | YYYY-MM-DD upper bound. Empty = today. Server semantics mirror `DATE_FROM`. |
| `PAGE_SIZE` | No | `1000` | arXiv pagination page size. arXiv only. |
| `MAX_PAGES` | No | `5` | Cap on arXiv pagination pages per run. arXiv only. |
| `DAYS` | No | `1` | Number of days back to fetch. bioRxiv/medRxiv only. |
| `CATEGORIES` | No | _(empty)_ | Comma-separated bioRxiv/medRxiv categories to keep. See [`docs/categories.md`](categories.md). bioRxiv/medRxiv only. |
| `TOKEN` | No | `${{ github.token }}` | GitHub token for pushing changes. |

## Versioning

No floating major tag — pin `@vX.Y.Z` or a commit SHA in `uses:`.

Releases are automated in two steps: run the **Bump version** workflow
(`workflow_dispatch`; pick major/minor/patch) to open a `chore(release)`
PR, then merge it. Merging changes `pyproject.toml`, which triggers **Tag
and Release** to tag `vX.Y.Z` on the `main` merge commit and publish the
GitHub Release from the matching [`CHANGELOG.md`](../CHANGELOG.md) section.
No moving/major tag is created.
