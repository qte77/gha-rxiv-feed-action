# Server categories

Reference list of subject categories per preprint server. Used to choose
sensible defaults for the `TOPICS` (arXiv) or `CATEGORIES` (bioRxiv,
medRxiv) action input.

Status legend:

- **canonical** — full list, verified
- **sampled** — partial; needs full pagination from a longer-lived runner
- **unreachable** — blocked from CI sandbox; re-run elsewhere

## arXiv (canonical)

Source: <https://arxiv.org/category_taxonomy> — query via
`https://export.arxiv.org/api/query?search_query=cat:<group>.<subject>`.

Top-level groups (each has many subjects):

```text
astro-ph    Astrophysics
cond-mat    Condensed Matter
cs          Computer Science
econ        Economics
eess        Electrical Engineering and Systems Science
gr-qc       General Relativity and Quantum Cosmology
hep-ex      High Energy Physics - Experiment
hep-lat     High Energy Physics - Lattice
hep-ph      High Energy Physics - Phenomenology
hep-th      High Energy Physics - Theory
math        Mathematics
math-ph     Mathematical Physics
nlin        Nonlinear Sciences
nucl-ex     Nuclear Experiment
nucl-th     Nuclear Theory
physics     Physics
q-bio       Quantitative Biology
q-fin       Quantitative Finance
quant-ph    Quantum Physics
stat        Statistics
```

The action's default `TOPICS` covers six CS subjects — `cat:cs.CV`,
`cat:cs.LG`, `cat:cs.CL`, `cat:cs.AI`, `cat:cs.NE`, `cat:cs.RO` —
joined with `+OR+`. Tailor `TOPICS` for other domains, e.g.
`cat:q-bio.PE+OR+cat:q-bio.QM` for quantitative biology.

## bioRxiv (canonical, 25)

Source: `https://api.biorxiv.org/details/biorxiv/{date1}/{date2}/{cursor}/json`

```text
animal behavior and cognition
biochemistry
bioengineering
bioinformatics
biophysics
cancer biology
cell biology
developmental biology
ecology
evolutionary biology
genetics
genomics
immunology
microbiology
molecular biology
neuroscience
paleontology
pathology
pharmacology and toxicology
physiology
plant biology
scientific communication and education
synthetic biology
systems biology
zoology
```

## medRxiv (canonical, 51)

Source: `https://api.biorxiv.org/details/medrxiv/{date1}/{date2}/{cursor}/json`

Enumerated via `scripts/enum_medrxiv_categories.py` over the window
2024-01-01 → 2026-05-24 (41,446 papers). Convergence criterion:
500 consecutive pages (~15,000 papers) with no new category. Final
sweep stopped at cursor 16,650; last new category appeared at cursor
1,680. Re-run the script to refresh — categories occasionally added
by medRxiv upstream.

Note: the API returns category strings in lowercase ASCII (letters,
spaces only — no slashes or special characters). Client-side matching
in `src/fetchers/biorxiv.py` is case-insensitive.

```text
addiction medicine
allergy and immunology
anesthesia
cardiovascular medicine
dentistry and oral medicine
dermatology
emergency medicine
endocrinology
epidemiology
forensic medicine
gastroenterology
genetic and genomic medicine
geriatric medicine
health economics
health informatics
health policy
health systems and quality improvement
hematology
hiv aids
infectious diseases
intensive care and critical care medicine
medical education
medical ethics
nephrology
neurology
nursing
nutrition
obstetrics and gynecology
occupational and environmental health
oncology
ophthalmology
orthopedics
otolaryngology
pain medicine
palliative medicine
pathology
pediatrics
pharmacology and therapeutics
primary care research
psychiatry and clinical psychology
public and global health
radiology and imaging
rehabilitation medicine and physical therapy
respiratory medicine
rheumatology
sexual and reproductive health
sports medicine
surgery
toxicology
transplantation
urology
```

## psyArXiv (canonical, 6 top-level; 234 total OSF taxonomy nodes)

Source: `https://api.osf.io/v2/preprint_providers/psyarxiv/taxonomies/`

Top-level (recommended for `CATEGORIES` filter — the full 234-node taxonomy
is too granular for a coarse filter):

```text
Engineering Psychology
Life Sciences
Meta-science
Neuroscience
Psychiatry
Social and Behavioral Sciences
```

The 228 depth-1 children include `Cognitive Neuroscience`, `Clinical
Psychology`, `Behavioral Economics`, `Computational Modeling`, and similar.
Fetch the full list via the source URL above. `SERVER=psyarxiv` matches
`CATEGORIES` against these top-level subjects only.

## chemRxiv (unreachable, pending)

Source: `https://chemrxiv.org/engage/chemrxiv/public-api/v1/items` (categories
embedded in item records)

The chemRxiv public API is fronted by Cloudflare and returns a challenge page
to non-browser clients from the enumeration sandbox. Approaches that work:

- run the fetch from a real browser DevTools session (paste cookies into a
  `curl` invocation)
- run from a CI runner where Cloudflare flags a verified UA
- use the official client library if/when one ships

Tracked in [issue #69](https://github.com/qte77/gha-rxiv-feed-action/issues/69).
