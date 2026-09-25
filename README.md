# hal-unica

Open-science monitoring for **[Université Côte d’Azur](https://univ-cotedazur.fr/)** on HAL (`UNIV-COTEDAZUR`), with sibling snapshots for other universities (currently **[Université Bourgogne Europe](https://www.ube.fr/)** / `UNIV-BOURGOGNE`).

This repository harvests institutional HAL notices, resolves linked identifiers (especially dataset DOIs), classifies which landings are real **data repositories** vs publications/preprints, and publishes a static site on GitHub Pages.

Live site: https://xiaoouwang.github.io/hal-unica/  
UBE snapshot: https://xiaoouwang.github.io/hal-unica/ube/

| Page | UniCA | UBE |
|---|---|---|
| Statistics | [/](https://xiaoouwang.github.io/hal-unica/) | [/ube/](https://xiaoouwang.github.io/hal-unica/ube/) |
| Chart embed (iframe) | [/embed-chart.html](https://xiaoouwang.github.io/hal-unica/embed-chart.html) | [/ube/embed-chart.html](https://xiaoouwang.github.io/hal-unica/ube/embed-chart.html) |
| Nakala / Recherche Data Gouv | [/related-datasets.html](https://xiaoouwang.github.io/hal-unica/related-datasets.html) | [/ube/related-datasets.html](https://xiaoouwang.github.io/hal-unica/ube/related-datasets.html) |
| **All repositories** | [/all-repositories.html](https://xiaoouwang.github.io/hal-unica/all-repositories.html) | [/ube/all-repositories.html](https://xiaoouwang.github.io/hal-unica/ube/all-repositories.html) |
| **DataCite datasets** (affiliation / ROR) | [/datacite-datasets.html](https://xiaoouwang.github.io/hal-unica/datacite-datasets.html) | [/ube/datacite-datasets.html](https://xiaoouwang.github.io/hal-unica/ube/datacite-datasets.html) |
| **Data papers** | [/data-papers.html](https://xiaoouwang.github.io/hal-unica/data-papers.html) | [/ube/data-papers.html](https://xiaoouwang.github.io/hal-unica/ube/data-papers.html) |
| **To Be Corrected** | [/to-be-corrected.html](https://xiaoouwang.github.io/hal-unica/to-be-corrected.html) | [/ube/to-be-corrected.html](https://xiaoouwang.github.io/hal-unica/ube/to-be-corrected.html) |
| Software & source code | [/software.html](https://xiaoouwang.github.io/hal-unica/software.html) | [/ube/software.html](https://xiaoouwang.github.io/hal-unica/ube/software.html) |
| Documentation + downloads | [/documentation.html](https://xiaoouwang.github.io/hal-unica/documentation.html) | [/ube/documentation.html](https://xiaoouwang.github.io/hal-unica/ube/documentation.html) |

Each site shows a logo row labeled **Open Science Snapshots of Other Universities**; clicking a logo opens that university’s snapshot in a new tab.

---

## Mental model (read this first)

HAL notices can declare related identifiers in several fields:

| HAL field | Intended use | What we do |
|---|---|---|
| `relatedData_s` | Related **datasets** | Expected home for dataset DOIs |
| `relatedPublication_s` | Related **publications** | Still scanned — depositors sometimes put Nakala/Zenodo DOIs here by mistake |
| `seeAlso_s` | Miscellaneous links | Scanned for DOIs / repo URLs |

Every token keeps **provenance** (`source_field`). If a DOI resolves to a data repository but was **not** filed in `relatedData_s`, it appears on **To Be Corrected** and in `misfiled_dataset_links.csv` — **unless** the same DOI is already present in `relatedData_s` on that notice (then the extra field is treated as supplementary).

Each resolved DOI gets an `object_kind`:

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
HAL Search API (per collection, e.g. UNIV-COTEDAZUR or UNIV-BOURGOGNE)
        │
        ├─ harvest      → data/<tenant>/harvest.jsonl   (or data/unica_hal_metadata.jsonl)
        │                 ~full collection; homepage document / DOI / doc-type stats
        │
        └─ refresh / census → data/<tenant>/census/   (UniCA: data/census/)
              │         publications_related_data.jsonl
              │         doi_resolutions.jsonl              (DataCite cache)
              │         summary.json, CSVs, METHODOLOGY.md
              │
              ├─ software     → software_deposits.*
              ├─ data-papers  → data_papers.*
              ├─ invert index → dataset_to_publications.*  (dataset_repo only)
              ├─ focus filter → data/<tenant>/links.jsonl  (Nakala/RDG)
              └─ build-site   → docs/ or docs/<site_path>/  (+ sitemap.xml, robots.txt)
```

Tenants are declared in `src/hal_unica/universities.py`. CLI entrypoint: `hal-unica` (package under `src/hal_unica/`).

---

## Package modules (roles)

| Module | Role |
|---|---|
| `cli.py` | Typer CLI: all `hal-unica` commands |
| `client.py` | HAL Search API client (pagination, retries, throttling) |
| `fields.py` | Default Solr field lists for harvests |
| `timeutil.py` | UTC helpers, watermarks, lookback / `--since` windows |
| `harvest.py` | Full or incremental archive of HAL metadata (upsert by `halId_s`) |
| `census.py` | Related-identifier census, DOI resolution orchestration, misfiled queue, census artifacts |
| `datacite.py` | DataCite DOI resolve + repository / `object_kind` classification + DOI search |
| `datacite_census.py` | Institutional DataCite Dataset harvest (ROR / affiliation) + HAL crosswalk |
| `data_repos.py` | Nakala / RDG focus scan + DOI enrichment helpers |
| `focus_links.py` | Build Nakala/RDG focus links JSONL from census publications |
| `software.py` | SOFTWARE deposits harvest + **dataset→publications** index builder |
| `data_papers.py` | Data-paper harvest (`DATAPAPER`) + linked-dataset enrichment from census cache |
| `refresh.py` | Daily orchestration: census → software → data papers → index → focus → DataCite (if configured) → site |
| `universities.py` | Multi-university tenant registry (collection, paths, branding, logo) |
| `site.py` | Static HTML/CSS/JS under `docs/` (stats, lists, chart, SEO, embed) |
| `report.py` | Standalone HTML report for focus-link results (legacy / optional) |

---

## CLI tutorial (`hal-unica`)

Install once:

```bash
pip install -e .
hal-unica --help
```

### Day-to-day (what CI runs)

| Command | When to use | What it does |
|---|---|---|
| `hal-unica refresh` | **Default daily path** (UniCA) | Incremental census → software → data papers → dataset index → Nakala/RDG focus → rebuild `docs/` |
| `hal-unica refresh --university ube` | Same for UBE | Writes under `data/ube/` and `docs/ube/` |
| `hal-unica refresh --full` | Sunday / repair gaps | Full related-data census query (still reuses DOI cache) |
| `hal-unica build-site` / `--university ube` | After local data edits | Rebuild Pages HTML from existing data (no HAL calls unless live count fallback) |

```bash
# Weekday-style incremental (2-day lookback) — both tenants in CI
hal-unica refresh --lookback-days 2
hal-unica refresh --university ube --lookback-days 2

# Full relatedData rebuild (DOI cache kept)
hal-unica refresh --full
hal-unica refresh --university ube --full

# Rebuild site only
hal-unica build-site
hal-unica build-site --university ube
```

What `refresh` does **not** do: re-download the ~99k-document metadata corpus.

What it **does**:

1. Pull notices matching the census query modified since `max(watermark − 1h, now − lookback)`.
2. Upsert them into `publications_related_data.jsonl`.
3. Resolve **only new** DOIs; reuse `doi_resolutions.jsonl`.
4. Re-harvest SOFTWARE and data papers (small full pulls).
5. Rebuild `dataset_to_publications.*` and focus links.
6. Rebuild `docs/` (including `data-papers.html`, chart, SEO files).

### Pieces in isolation

| Command | Role | Typical use |
|---|---|---|
| `hal-unica count` | Print HAL document count for the collection (optional time window) | Quick API sanity check |
| `hal-unica harvest` | Archive latest-version metadata for the whole collection (or a lookback window) into JSONL | Homepage “HAL documents” stats; lab backfills. Large file. |
| `hal-unica census` | Full or incremental related-data census + DataCite + misfiled CSV/JSONL | Debug census without rebuilding the whole site |
| `hal-unica software` | Harvest `docType_s=SOFTWARE` → `software_deposits.*` | Refresh software page inputs only |
| `hal-unica data-papers` | Harvest `docSubType_s=DATAPAPER` → `data_papers.*` (enriches links from census DOI cache) | Refresh data-papers page inputs only |
| `hal-unica datacite-census` | Harvest Dataset DOIs attributed to the university on DataCite (ROR / affiliation names) | Complements HAL: datasets with no HAL link |
| `hal-unica find-data-repos` | Find Nakala / Recherche Data Gouv links (focus scan) | Legacy / focused audit |
| `hal-unica resolve-repos` | Re-resolve DOIs in an existing links JSONL via DataCite | Refresh repository labels on focus hits |
| `hal-unica report` | HTML report from focus-link JSONL | Optional offline report |

```bash
# Full metadata archive (optional but needed for DOI % / doc-type bars; large; gitignored)
hal-unica harvest
hal-unica harvest --university ube

# Incremental harvest upsert
hal-unica harvest --lookback-days 2 --from-watermark
hal-unica harvest --university ube --lookback-days 2 --from-watermark

# Census only (defaults to UniCA paths; pass --collection / dirs for others)
hal-unica census
hal-unica census --lookback-days 2

# Software / data papers only
hal-unica software
hal-unica data-papers

# Institutional DataCite datasets (needs ror_ids / affiliation_names in universities.py)
hal-unica datacite-census
hal-unica datacite-census --university ube
hal-unica build-site
hal-unica build-site --university ube

# Nakala/RDG focus tooling
hal-unica find-data-repos -o data/unica_data_repo_links.jsonl
hal-unica resolve-repos --links data/unica_data_repo_links.jsonl
hal-unica report --links data/unica_data_repo_links.jsonl -o docs/report.html
```

Preview locally: `python -m http.server 8765 -d docs` (UBE under `/ube/`).

---

## Adding another university

Each university is a **tenant**: same pages and pipeline, separate HAL collection, data directory, and Pages subdirectory. Registration lives in [`src/hal_unica/universities.py`](src/hal_unica/universities.py).

### 1. Confirm the HAL collection code

Probe the Search API (must return a non-zero `numFound`):

```bash
hal-unica count --collection UNIV-BOURGOGNE
# or: curl 'https://api.archives-ouvertes.fr/search/UNIV-BOURGOGNE/?q=*:*&rows=0&wt=json'
```

Institutional portals often use `UNIV-…` codes (UniCA = `UNIV-COTEDAZUR`, UBE = `UNIV-BOURGOGNE`). Aurehal instance nicknames (e.g. `univ-bourgogne`) are not always valid collection paths.

### 2. Add a `University` entry

In `universities.py`, copy the `UBE` example and set:

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

Register it in `UNIVERSITIES` (e.g. `UNIVERSITIES[MY_UNI.id] = MY_UNI`).

### 3. Drop the logo asset

Put a PNG/SVG/WebP in `static/universities/<logo>` (e.g. `ube.png`). `build-site` / `refresh` copies it into each site’s `assets/universities/`. Omit `logo` to show the `short_name` as a text chip in the switcher.

### 4. Cold-start the tenant

```bash
# Full related-data census + software + data papers + site
hal-unica refresh --university <id> --full

# Homepage DOI % / document types (large; gitignored like UniCA harvest)
hal-unica harvest --university <id>
hal-unica build-site --university <id>
```

Without the harvest step, the snapshot still works (charts, related datasets, …) but homepage **document / DOI / doc-type** stats fall back to a live HAL count only (`live_count_only`).

### 5. Wire daily CI

In [`.github/workflows/daily-refresh.yml`](.github/workflows/daily-refresh.yml), add a second `hal-unica refresh --university <id> …` next to the existing UniCA and UBE calls, and `git add` the new `data/<tenant>/` paths.

No code change is needed for the logo row: every tenant automatically lists **other** universities under **Open Science Snapshots of Other Universities**, linking to each snapshot’s absolute URL in a new tab.

### Optional: DataCite institutional datasets

UniCA and UBE run a **DataCite-first** census (see [UniCA](https://xiaoouwang.github.io/hal-unica/datacite-datasets.html) · [UBE](https://xiaoouwang.github.io/hal-unica/ube/datacite-datasets.html)):

- Query DataCite for `resourceTypeGeneral:Dataset` whose creators/contributors list the university’s **ROR** and/or **affiliation name** strings (`universities.py`: `ror_ids`, `affiliation_names`).
- Crosswalk DOIs against HAL `dataset_to_publications.jsonl`.
- Surfaces **DataCite-only** datasets (no HAL link) and **HAL-only** datasets (linked on HAL but missing UniCA affiliation metadata on DataCite).

```bash
hal-unica datacite-census          # or: included in `hal-unica refresh` when configured
hal-unica build-site
```

Enable the same for another university by filling `ror_ids` / `affiliation_names` on its `University` entry.

---

## Typical routines (how to combine the scripts)

### A. First-time / cold start (empty census)

```bash
pip install -e .

# UniCA
hal-unica harvest                    # optional but fixes DOI % / doc types
hal-unica refresh --full

# UBE (or any --university <id>)
hal-unica harvest --university ube
hal-unica refresh --university ube --full

python -m http.server 8765 -d docs
```

### B. Normal local day (same as CI)

```bash
hal-unica refresh --lookback-days 2
# → upserts recently modified relatedData notices
# → re-harvests SOFTWARE + data papers
# → rebuilds dataset index, Nakala/RDG focus file, docs/
```

### C. “I only changed site.py / CSS”

```bash
hal-unica build-site
```

No HAL/DataCite calls; rebuilds HTML from existing JSONL/CSV.

### D. “I only care about data papers / software today”

```bash
hal-unica data-papers    # needs existing doi_resolutions.jsonl for link enrichment
hal-unica software
hal-unica build-site
```

### E. Debug a census issue without touching the site

```bash
hal-unica census --lookback-days 2
# inspect data/census/summary.json, misfiled_dataset_links.csv, run.log
hal-unica build-site     # when ready to publish
```

### F. Recommended dependency order

```
harvest (optional) ─┐
                    ├─→ refresh ─┬─→ census artifacts
census (alone)   ───┘           ├─→ software_deposits.*
                                ├─→ data_papers.*
                                ├─→ dataset_to_publications.*
                                ├─→ unica_data_repo_links.jsonl
                                └─→ build-site → docs/
```

In practice **prefer `refresh`** over chaining pieces yourself unless you are debugging.

---

## List pages (shared UX)

**All repositories · Related datasets · Software · Data papers · To Be Corrected** share the same list patterns where relevant:

- **Sort** — newest/oldest retrieved and/or HAL update (plus title / repository / journal)
- **Year** — publication year filter
- **Laboratory** — dropdown + type-ahead (prefix match)
- Rich cards — HAL ids, Paris-local timestamps, labs, linked evidence
- Stat cards — quick count-up animation on load

Data papers also have chips for **All / With linked dataset / Without linked dataset**, plus journal filters.

### Retrieval dates on All repositories

| Field | Meaning |
|---|---|
| `retrieved_at` | First time this dataset DOI entered **our** index (sticky across rebuilds) |
| `hal_modified_at` | Latest HAL `modifiedDate_tdate` among linked notices |

Default sort: **Newest retrieved**. Edits to old HAL notices that introduce a **new** dataset DOI get a fresh `retrieved_at`.

HAL exposes `modifiedDate_tdate`. When a depositor edits an old notice, HAL bumps that timestamp; the daily job merges by `halId_s`.

---

## Daily schedule (GitHub Actions)

Workflow: [`.github/workflows/daily-refresh.yml`](.github/workflows/daily-refresh.yml)

GitHub often delays crons that fire at `:00`. We therefore:

1. Run **off the hour** (`:17`)
2. Add a **catch-up** mid-morning Paris time if the first run was delayed

| Slot | Cron (UTC) | Paris (CEST / CET) | Mode |
|---|---|---|---|
| Primary | `17 4 * * 1-6` | **06:17** / **05:17** | Incremental |
| Primary Sunday | `17 4 * * 0` | **06:17** / **05:17** | Full census |
| Catch-up (daily) | `17 8 * * *` | **10:17** / **09:17** | Incremental |

After a successful refresh **with file changes**, the same workflow deploys GitHub Pages (bot pushes with `GITHUB_TOKEN` do not trigger `pages.yml` alone). Each scheduled run refreshes **UniCA then UBE**.

Delays can still happen under GitHub load; the catch-up slot is there so you usually do not need a manual refresh. Manual run: Actions → **Daily incremental refresh** → `incremental` or `full`.

If Actions is down longer than the lookback window, the next **Sunday full** run closes the gap.

Deploy-on-push for human commits: [`.github/workflows/pages.yml`](.github/workflows/pages.yml).

---

## Snapshot (indicative)

Figures move with each refresh; check `data/census/summary.json`, `dataset_to_publications_summary.json`, `software_summary.json`, and `data_papers_summary.json`.

| Metric | Approx. value |
|---:|---:|
| HAL notices with linked identifiers (census) | **313** |
| Unique DOIs resolved (all kinds) | **401** |
| Of which `dataset_repo` landings (links) | **264** |
| Unique dataset DOIs on All repositories | **246** |
| Pubs with ≥1 dataset-repo landing | **164** |
| Misfiled dataset links (wrong HAL field) | **72** |
| HAL `SOFTWARE` deposits | **78** |
| HAL data papers (`DATAPAPER`) | **54** |

Top **data** repositories (All repositories index): Zenodo · Recherche Data Gouv · SEANOE · Sismer · SEDOO/Theia · NAKALA · …

---

## Artifacts

| Path | Meaning |
|---|---|
| [`data/census/dataset_to_publications.csv`](data/census/dataset_to_publications.csv) | **Dataset DOI → HAL publication(s)** (+ `retrieved_at`) — All repositories |
| [`data/census/misfiled_dataset_links.csv`](data/census/misfiled_dataset_links.csv) | Dataset DOIs filed outside `relatedData_s` (correction queue) |
| [`data/census/doi_to_repository.csv`](data/census/doi_to_repository.csv) | Every related DOI → repository / kind (includes journals) |
| [`data/census/doi_hal_repository_map.csv`](data/census/doi_hal_repository_map.csv) | HAL notice ↔ DOI ↔ repository ↔ source field |
| [`data/census/doi_resolutions.jsonl`](data/census/doi_resolutions.jsonl) | DataCite resolution cache |
| [`data/census/publications_related_data.jsonl`](data/census/publications_related_data.jsonl) | Per-notice tokens + resolutions |
| [`data/census/software_deposits.csv`](data/census/software_deposits.csv) | SOFTWARE + code repos + SWHIDs |
| [`data/census/data_papers.csv`](data/census/data_papers.csv) | Data papers + linked datasets / journals |
| [`data/census/datacite_datasets.csv`](data/census/datacite_datasets.csv) | UniCA DataCite Dataset DOIs (affiliation / ROR) + HAL crosswalk |
| [`data/ube/census/datacite_datasets.csv`](data/ube/census/datacite_datasets.csv) | UBE DataCite Dataset DOIs (affiliation / ROR) + HAL crosswalk |
| [`data/census/summary.json`](data/census/summary.json) | Full-census aggregates |
| [`data/census/census.meta.json`](data/census/census.meta.json) | Watermark for incremental refresh |
| [`data/census/METHODOLOGY.md`](data/census/METHODOLOGY.md) | Auto-generated method + counts for last census run |
| [`data/unica_data_repo_links.jsonl`](data/unica_data_repo_links.jsonl) | Nakala/RDG focus hits |
| [`docs/`](docs/) | Published site (`docs/data/census/` mirrors UniCA census; `docs/ube/` is the UBE snapshot) |
| [`docs/sitemap.xml`](docs/sitemap.xml) / [`docs/robots.txt`](docs/robots.txt) | SEO crawl hints |
| [`src/hal_unica/universities.py`](src/hal_unica/universities.py) | Tenant registry — add universities here |
| [`static/universities/`](static/universities/) | Logo source files copied into each site’s `assets/universities/` |

---

## Design decisions worth remembering

1. **Do not treat every related DOI as a dataset.** Journals, arXiv, ResearchGate, publisher platforms are `publication_landing`. Unknown hosts must not default to `dataset_repo`.
2. **Track wrong fields instead of dropping them.** Misfiled Nakala/Zenodo DOIs in `relatedPublication_s` feed the correction queue — unless the same DOI is already in `relatedData_s`.
3. **Upsert + watermark**, never wipe the JSONL on `--since` / lookback harvests.
4. **Sunday full rebuild** is the safety net for missed incrementals.
5. **`retrieved_at` is sticky** so newly discovered datasets stay sortable after later rebuilds.
6. **Timestamps on the site are Europe/Paris** (CET/CEST); machine-readable `datetime` attributes stay UTC.
7. **Daily refresh deploys Pages itself** when it commits, because `GITHUB_TOKEN` pushes do not trigger `pages.yml`.
