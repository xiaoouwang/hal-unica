# hal-unica

Open-science monitoring for **[Université Côte d’Azur](https://univ-cotedazur.fr/)** on HAL (`UNIV-COTEDAZUR`), with a sibling snapshot for **[Université Bourgogne Europe](https://www.ube.fr/)** (`UNIV-BOURGOGNE`).

The project:

1. Harvests institutional **HAL** notices and related identifiers (especially dataset DOIs)
2. Resolves landings via **DataCite** and classifies real **data repositories** vs publications/preprints
3. Runs a complementary **DataCite affiliation census** (ROR / affiliation names) for datasets that never appear on HAL
4. Publishes static GitHub Pages sites with charts, lists, correction queues, and downloadable CSVs

| | UniCA | UBE |
|---|---|---|
| Live site | https://xiaoouwang.github.io/hal-unica/ | https://xiaoouwang.github.io/hal-unica/ube/ |
| HAL collection | `UNIV-COTEDAZUR` | `UNIV-BOURGOGNE` |
| ROR | [019tgvf94](https://ror.org/019tgvf94) | [00g700j37](https://ror.org/00g700j37) |

| Page | UniCA | UBE |
|---|---|---|
| Statistics | [/](https://xiaoouwang.github.io/hal-unica/) | [/ube/](https://xiaoouwang.github.io/hal-unica/ube/) |
| Chart embed (iframe) | [/embed-chart.html](https://xiaoouwang.github.io/hal-unica/embed-chart.html) | [/ube/embed-chart.html](https://xiaoouwang.github.io/hal-unica/ube/embed-chart.html) |
| Nakala / Recherche Data Gouv | [/related-datasets.html](https://xiaoouwang.github.io/hal-unica/related-datasets.html) | [/ube/related-datasets.html](https://xiaoouwang.github.io/hal-unica/ube/related-datasets.html) |
| **All repositories** (HAL → datasets) | [/all-repositories.html](https://xiaoouwang.github.io/hal-unica/all-repositories.html) | [/ube/all-repositories.html](https://xiaoouwang.github.io/hal-unica/ube/all-repositories.html) |
| **DataCite datasets** (affiliation → datasets) | [/datacite-datasets.html](https://xiaoouwang.github.io/hal-unica/datacite-datasets.html) | [/ube/datacite-datasets.html](https://xiaoouwang.github.io/hal-unica/ube/datacite-datasets.html) |
| **Data papers** | [/data-papers.html](https://xiaoouwang.github.io/hal-unica/data-papers.html) | [/ube/data-papers.html](https://xiaoouwang.github.io/hal-unica/ube/data-papers.html) |
| **To Be Corrected** | [/to-be-corrected.html](https://xiaoouwang.github.io/hal-unica/to-be-corrected.html) | [/ube/to-be-corrected.html](https://xiaoouwang.github.io/hal-unica/ube/to-be-corrected.html) |
| Software & source code | [/software.html](https://xiaoouwang.github.io/hal-unica/software.html) | [/ube/software.html](https://xiaoouwang.github.io/hal-unica/ube/software.html) |
| Documentation + downloads | [/documentation.html](https://xiaoouwang.github.io/hal-unica/documentation.html) | [/ube/documentation.html](https://xiaoouwang.github.io/hal-unica/ube/documentation.html) |

Each site shows a logo row labeled **Open Science Snapshots of Other Universities**; clicking a logo opens that university’s snapshot **in a new tab** (same app features, that university’s data).

---

## Mental model (read this first)

### Two complementary views of “datasets”

| View | Question answered | Blind spot |
|---|---|---|
| **HAL → DataCite** (All repositories, charts, To Be Corrected) | Which dataset DOIs are **declared on HAL notices**? | Datasets never linked from a publication |
| **DataCite → affiliation** (DataCite datasets page) | Which Dataset DOIs are **attributed to the university** on DataCite (ROR / affiliation)? | Incomplete affiliation metadata; multi-affiliation noise |

Use both: the gap (DataCite-only vs HAL-only) is intentional and useful for open-science monitoring.

### HAL related-identifier fields

| HAL field | Intended use | What we do |
|---|---|---|
| `relatedData_s` | Related **datasets** | Expected home for dataset DOIs |
| `relatedPublication_s` | Related **publications** | Still scanned — depositors sometimes put Nakala/Zenodo DOIs here by mistake |
| `seeAlso_s` | Miscellaneous links | Scanned for DOIs / repo URLs |

Every token keeps **provenance** (`source_field`). If a DOI resolves to a data repository but was **not** filed in `relatedData_s`, it appears on **To Be Corrected** and in `misfiled_dataset_links.csv` — **unless** the same DOI is already present in `relatedData_s` on that notice (then the extra field is treated as supplementary).

### `object_kind` (DataCite landing classification)

| `object_kind` | Meaning | Shown on All repositories? |
|---|---|---|
| `dataset_repo` | Landing is a data repository (Zenodo, RDG, SEANOE, NAKALA, …) | **Yes** |
| `publication_landing` | Journal, preprint, ResearchGate, publisher site, … | No (still in full census CSVs) |
| `unresolved` / `other` | Could not classify | No |

Classification lives in `src/hal_unica/datacite.py` (`classify_repository`): known data hosts, known publication hosts, journal DOI prefixes, then **never** assume unknown hosts are datasets.

The **All repositories** page and `dataset_to_publications.*` are **dataset-only** (`object_kind == dataset_repo`). The full census `summary.json` / `doi_to_repository.csv` still list every related DOI (including journals) for audit.

**Data papers** are journal articles with `docType_s=ART` and `docSubType_s=DATAPAPER` (HAL subtype for scholarly descriptions of datasets). They are harvested separately from the related-data census.

---

## Architecture

```
HAL Search API (per collection)
        │
        ├─ harvest           → data/unica_hal_metadata.jsonl  or  data/ube/harvest.jsonl
        │                      (gitignored; homepage DOI % / doc-type bars)
        │
        └─ refresh
              ├─ census      → publications_related_data.jsonl, doi_resolutions.jsonl, CSVs
              ├─ software    → software_deposits.*
              ├─ data-papers → data_papers.*
              ├─ invert      → dataset_to_publications.*     (HAL → datasets)
              ├─ focus       → Nakala/RDG links JSONL
              ├─ datacite-census → datacite_datasets.*       (affiliation → datasets; if ROR configured)
              └─ build-site  → docs/  or  docs/ube/
```

| Tenant | HAL collection | Data dir | Site |
|---|---|---|---|
| `unica` (default) | `UNIV-COTEDAZUR` | `data/census/`, `data/unica_*` | `docs/` |
| `ube` | `UNIV-BOURGOGNE` | `data/ube/` | `docs/ube/` |

Tenants are declared in [`src/hal_unica/universities.py`](src/hal_unica/universities.py). CLI: `hal-unica`.

---

## Package modules (roles)

| Module | Role |
|---|---|
| `cli.py` | Typer CLI: all `hal-unica` commands (`--university` where relevant) |
| `client.py` | HAL Search API client (pagination, retries, connect/read timeouts) |
| `fields.py` | Default Solr field lists for harvests |
| `timeutil.py` | UTC helpers, watermarks, lookback / `--since` windows |
| `harvest.py` | Full or incremental archive of HAL metadata (upsert by `halId_s`) |
| `census.py` | Related-identifier census, DOI resolution, misfiled queue, census artifacts |
| `datacite.py` | DataCite DOI resolve, search pagination, repository / `object_kind` classification |
| `datacite_census.py` | Institutional DataCite Dataset harvest (ROR / affiliation) + HAL crosswalk |
| `data_repos.py` | Nakala / RDG focus scan + DOI enrichment helpers |
| `focus_links.py` | Build Nakala/RDG focus links JSONL from census publications |
| `software.py` | SOFTWARE deposits harvest + **dataset→publications** index builder |
| `data_papers.py` | Data-paper harvest (`DATAPAPER`) + linked-dataset enrichment from census cache |
| `refresh.py` | Daily orchestration (HAL census → … → DataCite census → site) |
| `universities.py` | Multi-university tenant registry (collection, paths, branding, logo, ROR) |
| `site.py` | Static HTML/CSS/JS under `docs/` (stats, lists, chart, SEO, embed) |
| `report.py` | Standalone HTML report for focus-link results (legacy / optional) |

---

## CLI tutorial (`hal-unica`)

```bash
pip install -e .
hal-unica --help
```

### Day-to-day (what CI runs)

| Command | When to use | What it does |
|---|---|---|
| `hal-unica refresh` | **Default daily path** (UniCA) | Incremental HAL census → software → data papers → dataset index → Nakala/RDG focus → **DataCite census** → rebuild `docs/` |
| `hal-unica refresh --university ube` | Same for UBE | Writes under `data/ube/` and `docs/ube/` |
| `hal-unica refresh --full` | Sunday / repair gaps | Full related-data census query (still reuses DOI cache) |
| `hal-unica build-site` / `--university ube` | After local data edits | Rebuild Pages HTML from existing data |

```bash
# Weekday-style incremental (both tenants — same as CI)
hal-unica refresh --lookback-days 2
hal-unica refresh --university ube --lookback-days 2

# Full relatedData rebuild (DOI cache kept)
hal-unica refresh --full
hal-unica refresh --university ube --full

# Rebuild site only
hal-unica build-site
hal-unica build-site --university ube
```

What `refresh` does **not** do: re-download the full metadata harvest JSONL (~tens of thousands of notices; gitignored).

What it **does**:

1. Pull HAL notices matching the census query modified since `max(watermark − 1h, now − lookback)`.
2. Upsert them into `publications_related_data.jsonl`.
3. Resolve **only new** DOIs; reuse `doi_resolutions.jsonl`.
4. Re-harvest SOFTWARE and data papers (small full pulls).
5. Rebuild `dataset_to_publications.*` and Nakala/RDG focus links.
6. If the tenant has `ror_ids` / `affiliation_names`: run **DataCite institutional census**.
7. Rebuild the static site (charts, SEO, all list pages).

### Pieces in isolation

| Command | Role | Typical use |
|---|---|---|
| `hal-unica count` | Print HAL document count | API sanity check |
| `hal-unica harvest` | Full/incremental metadata JSONL (`--university`) | Homepage DOI % / doc types; lab backfill |
| `hal-unica census` | Related-data census + DataCite resolve + misfiled CSVs | Debug without rebuilding the site |
| `hal-unica software` | `docType_s=SOFTWARE` → `software_deposits.*` | Software page only |
| `hal-unica data-papers` | `docSubType_s=DATAPAPER` → `data_papers.*` | Data-papers page only |
| `hal-unica datacite-census` | Affiliation Dataset DOIs on DataCite + HAL crosswalk | DataCite page / gap analysis |
| `hal-unica find-data-repos` | Nakala / RDG focus scan | Legacy / focused audit |
| `hal-unica resolve-repos` | Re-resolve DOIs in a links JSONL | Refresh repository labels |
| `hal-unica report` | HTML report from focus-link JSONL | Optional offline report |

```bash
# Full metadata archive (large; gitignored)
hal-unica harvest
hal-unica harvest --university ube

# Incremental harvest upsert
hal-unica harvest --lookback-days 2 --from-watermark
hal-unica harvest --university ube --lookback-days 2 --from-watermark

# HAL census only
hal-unica census
hal-unica census --lookback-days 2

# Software / data papers
hal-unica software
hal-unica data-papers

# DataCite institutional census
hal-unica datacite-census
hal-unica datacite-census --university ube
hal-unica build-site
hal-unica build-site --university ube
```

Preview locally: `python -m http.server 8765 -d docs` (UBE at `/ube/`).

---

## Adding another university

Each university is a **tenant**: same pages and pipeline, separate HAL collection, data directory, and Pages subdirectory. Registration: [`src/hal_unica/universities.py`](src/hal_unica/universities.py).

### 1. Confirm the HAL collection code

```bash
hal-unica count --collection UNIV-BOURGOGNE
```

Institutional portals often use `UNIV-…` codes. Aurehal instance nicknames (e.g. `univ-bourgogne`) are not always valid Search API paths.

### 2. Add a `University` entry

Copy the `UBE` example and set:

| Field | Meaning |
|---|---|
| `id` | Short slug (`ube`, `xyz`) — used as `--university xyz` |
| `collection` | HAL Search collection code |
| `short_name` / `display_name` / `site_name` | Branding in nav, eyebrows, SEO |
| `tagline` / `org_url` | Meta description + JSON-LD publisher |
| `site_path` | Pages subfolder (`""` = site root, `"ube"` → `docs/ube/`) |
| `logo` | Filename under `static/universities/` (or `None` for a text chip) |
| `census_dir` / `links_path` / `harvest_path` | Local data paths (keep tenants separate) |
| `site_dir` / `stats_fallback` / `log_path` | Output site + CI log |
| `ror_ids` / `affiliation_names` | Optional — enables DataCite institutional census + nav link |

Register it in `UNIVERSITIES`.

### 3. Logo asset

Put a PNG/SVG/WebP in `static/universities/<logo>`. `build-site` / `refresh` copies it into each site’s `assets/universities/`.

### 4. Cold-start

```bash
hal-unica refresh --university <id> --full
hal-unica harvest --university <id>          # homepage DOI % / doc types
hal-unica build-site --university <id>
# If ror_ids / affiliation_names set, refresh already ran datacite-census;
# or: hal-unica datacite-census --university <id>
```

Without the harvest step, charts and related-data pages still work; homepage document/DOI/doc-type stats fall back to a live HAL count (`live_count_only`).

### 5. Wire daily CI

In [`.github/workflows/daily-refresh.yml`](.github/workflows/daily-refresh.yml), add a `Refresh <Name>` step next to UniCA/UBE (with `continue-on-error` + retry pattern), and `git add` the new `data/<tenant>/` paths.

The logo row updates automatically: every tenant lists **other** universities under **Open Science Snapshots of Other Universities**.

### DataCite institutional datasets (UniCA + UBE)

- Query DataCite for `resourceTypeGeneral:Dataset` whose creators/contributors match **ROR** and/or **affiliation name** strings.
- Crosswalk DOIs against HAL `dataset_to_publications.jsonl`.
- Page filters: **All / Also on HAL / DataCite only**.
- Stats also report **HAL-only** (linked on HAL but missing from the affiliation filter — often incomplete DataCite metadata).

| Tenant | ROR | Example affiliation names |
|---|---|---|
| UniCA | `https://ror.org/019tgvf94` | Université Côte d’Azur, Universite Cote d’Azur, … |
| UBE | `https://ror.org/00g700j37` | Université Bourgogne Europe, Université de Bourgogne, University of Burgundy, … |

Avoid very short affiliation strings (e.g. `uB`, `Univ. X`) — they inflate false positives.

---

## Typical routines

### A. First-time / cold start

```bash
pip install -e .
hal-unica harvest && hal-unica refresh --full
hal-unica harvest --university ube && hal-unica refresh --university ube --full
python -m http.server 8765 -d docs
```

### B. Normal local day (same as CI)

```bash
hal-unica refresh --lookback-days 2
hal-unica refresh --university ube --lookback-days 2
```

### C. Site / CSS only

```bash
hal-unica build-site
hal-unica build-site --university ube
```

### D. Data papers / software only

```bash
hal-unica data-papers && hal-unica software && hal-unica build-site
```

### E. DataCite gap analysis only

```bash
hal-unica datacite-census
hal-unica datacite-census --university ube
hal-unica build-site && hal-unica build-site --university ube
```

### F. Dependency order

```
harvest (optional) ─┐
                    ├─→ refresh ─┬─→ HAL census artifacts
census (alone)   ───┘           ├─→ software / data_papers
                                ├─→ dataset_to_publications.*
                                ├─→ focus links
                                ├─→ datacite_datasets.*   (if ROR configured)
                                └─→ build-site → docs/ or docs/ube/
```

Prefer **`refresh`** unless you are debugging one piece.

---

## List pages (shared UX)

**All repositories · Related datasets · DataCite datasets · Software · Data papers · To Be Corrected** share:

- Sort (retrieved / HAL update / year / title / repository where relevant)
- Year and laboratory filters on HAL-backed pages
- Search, chips, count-up stat cards
- Paris-local timestamps (`datetime` attributes stay UTC)

| Page | Extra filters |
|---|---|
| Data papers | All / With linked dataset / Without linked dataset (+ journal) |
| DataCite datasets | All / Also on HAL / DataCite only (+ repository) |

### Retrieval dates on All repositories

| Field | Meaning |
|---|---|
| `retrieved_at` | First time this dataset DOI entered **our** index (sticky across rebuilds) |
| `hal_modified_at` | Latest HAL `modifiedDate_tdate` among linked notices |

Default sort: **Newest retrieved**.

---

## Daily schedule (GitHub Actions)

Workflow: [`.github/workflows/daily-refresh.yml`](.github/workflows/daily-refresh.yml)

| Slot | Cron (UTC) | Paris (CEST / CET) | Mode |
|---|---|---|---|
| Primary | `17 4 * * 1-6` | **06:17** / **05:17** | Incremental |
| Primary Sunday | `17 4 * * 0` | **06:17** / **05:17** | Full census |
| Catch-up (daily) | `17 8 * * *` | **10:17** / **09:17** | Incremental |

CI behaviour:

- Refreshes **UniCA** and **UBE** as **separate steps** (one HAL outage does not skip the other)
- **Automatic retry** once if a tenant fails (common `ConnectTimeout` against HAL/DataCite)
- **Commits whatever succeeded**, then fails the job if any tenant is still broken
- Deploys Pages when `docs/` changed (bot `GITHUB_TOKEN` pushes do not trigger `pages.yml` alone)

Manual run: Actions → **Daily incremental refresh** → `incremental` or `full`.  
Deploy-on-push for human commits: [`.github/workflows/pages.yml`](.github/workflows/pages.yml).

---

## Snapshot (indicative)

Figures move with each refresh. Sources: `summary.json`, `dataset_to_publications_summary.json`, `datacite_datasets_summary.json`, homepage `stats.json`.

### UniCA

| Metric | Approx. |
|---:|---:|
| HAL documents (harvest) | **99 165** (~**42%** with DOI) |
| HAL notices with linked identifiers | **316** |
| Unique DOIs resolved (all kinds) | **404** |
| Unique dataset DOIs (All repositories) | **247** |
| Pubs with ≥1 dataset-repo landing | **165** |
| Misfiled dataset links | **72** |
| SOFTWARE / data papers | **78** / **55** |
| DataCite Dataset DOIs (affiliation) | **1 344** |
| … also on HAL / DataCite-only / HAL-only | **31** / **1 313** / **216** |

Top HAL-linked data repos: Zenodo · Recherche Data Gouv · SEANOE · Sismer · SEDOO/Theia · NAKALA · …

### UBE

| Metric | Approx. |
|---:|---:|
| HAL documents (harvest) | **76 081** (~**37%** with DOI) |
| HAL notices with linked identifiers | **261** |
| Unique DOIs resolved (all kinds) | **301** |
| Unique dataset DOIs (All repositories) | **176** |
| Pubs with ≥1 dataset-repo landing | **147** |
| Misfiled dataset links | **20** |
| SOFTWARE / data papers | **18** / **54** |
| DataCite Dataset DOIs (affiliation) | **717** |
| … also on HAL / DataCite-only / HAL-only | **7** / **710** / **169** |

Top HAL-linked / DataCite repos vary; UBE DataCite is often heavy on Recherche Data Gouv and Zenodo.

---

## Artifacts

### UniCA (`data/census/`, mirrored under `docs/data/census/`)

| Path | Meaning |
|---|---|
| [`dataset_to_publications.csv`](data/census/dataset_to_publications.csv) | Dataset DOI → HAL publication(s) (+ `retrieved_at`) |
| [`misfiled_dataset_links.csv`](data/census/misfiled_dataset_links.csv) | Dataset DOIs filed outside `relatedData_s` |
| [`doi_to_repository.csv`](data/census/doi_to_repository.csv) | Every related DOI → repository / kind |
| [`doi_hal_repository_map.csv`](data/census/doi_hal_repository_map.csv) | HAL notice ↔ DOI ↔ repository ↔ source field |
| [`doi_resolutions.jsonl`](data/census/doi_resolutions.jsonl) | DataCite resolution cache |
| [`publications_related_data.jsonl`](data/census/publications_related_data.jsonl) | Per-notice tokens + resolutions |
| [`software_deposits.csv`](data/census/software_deposits.csv) | SOFTWARE + code repos + SWHIDs |
| [`data_papers.csv`](data/census/data_papers.csv) | Data papers + linked datasets / journals |
| [`datacite_datasets.csv`](data/census/datacite_datasets.csv) | DataCite affiliation Dataset DOIs + HAL crosswalk |
| [`summary.json`](data/census/summary.json) | HAL census aggregates |
| [`METHODOLOGY.md`](data/census/METHODOLOGY.md) | Auto-generated method notes |
| [`../unica_data_repo_links.jsonl`](data/unica_data_repo_links.jsonl) | Nakala/RDG focus hits |

### UBE (`data/ube/census/`, mirrored under `docs/ube/data/census/`)

Same filenames as above under `data/ube/census/`, plus [`datacite_datasets.csv`](data/ube/census/datacite_datasets.csv). Focus links: `data/ube/links.jsonl`.

### Site & config

| Path | Meaning |
|---|---|
| [`docs/`](docs/) | UniCA Pages root |
| [`docs/ube/`](docs/ube/) | UBE snapshot |
| [`docs/sitemap.xml`](docs/sitemap.xml) / [`robots.txt`](docs/robots.txt) | SEO |
| [`src/hal_unica/universities.py`](src/hal_unica/universities.py) | Tenant registry |
| [`static/universities/`](static/universities/) | Logo sources → `assets/universities/` |

Bulk harvests (`data/unica_hal_metadata.jsonl`, `data/ube/harvest.jsonl`) stay **local / gitignored**.

---

## Design decisions worth remembering

1. **Do not treat every related DOI as a dataset.** Journals, arXiv, ResearchGate, publisher platforms are `publication_landing`.
2. **Track wrong fields instead of dropping them.** Misfiled dataset DOIs feed the correction queue — unless already in `relatedData_s`.
3. **HAL and DataCite answer different questions.** Keep both; do not replace HAL monitoring with affiliation search alone.
4. **Upsert + watermark**, never wipe JSONL on lookback harvests.
5. **Sunday full rebuild** is the safety net for missed incrementals.
6. **`retrieved_at` is sticky** across rebuilds.
7. **Timestamps on the site are Europe/Paris**; machine-readable `datetime` stays UTC.
8. **Daily refresh deploys Pages itself** when it commits (`GITHUB_TOKEN` does not trigger `pages.yml`).
9. **CI isolates tenants** and retries transient HAL/DataCite timeouts so one outage does not discard the other’s successful refresh.
