# hal-unica

Open-science monitoring for **[Université Côte d’Azur](https://univ-cotedazur.fr/)** on HAL (`UNIV-COTEDAZUR`).

This repository harvests UniCA HAL notices, resolves linked identifiers (especially dataset DOIs), classifies which landings are real **data repositories** vs publications/preprints, and publishes a static site on GitHub Pages.

Live site: https://xiaoouwang.github.io/hal-unica/

| Page | URL |
|---|---|
| Statistics | https://xiaoouwang.github.io/hal-unica/ |
| Chart embed (iframe) | https://xiaoouwang.github.io/hal-unica/embed-chart.html |
| Nakala / Recherche Data Gouv | https://xiaoouwang.github.io/hal-unica/related-datasets.html |
| **All repositories** (dataset → publications) | https://xiaoouwang.github.io/hal-unica/all-repositories.html |
| **Data papers** (`docSubType_s=DATAPAPER`) | https://xiaoouwang.github.io/hal-unica/data-papers.html |
| **To Be Corrected** (misfiled dataset links) | https://xiaoouwang.github.io/hal-unica/to-be-corrected.html |
| Software & source code | https://xiaoouwang.github.io/hal-unica/software.html |
| Documentation + downloads | https://xiaoouwang.github.io/hal-unica/documentation.html |

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
HAL Search API (UNIV-COTEDAZUR)
        │
        ├─ harvest      → data/unica_hal_metadata.jsonl   (~full collection; optional for homepage stats)
        │
        └─ refresh / census → data/census/
              │         publications_related_data.jsonl
              │         doi_resolutions.jsonl              (DataCite cache)
              │         summary.json, CSVs, METHODOLOGY.md
              │
              ├─ software     → software_deposits.*
              ├─ data-papers  → data_papers.*
              ├─ invert index → dataset_to_publications.*  (dataset_repo only)
              ├─ focus filter → data/unica_data_repo_links.jsonl  (Nakala/RDG)
              └─ build-site   → docs/  (+ sitemap.xml, robots.txt)
```

CLI entrypoint: `hal-unica` (package under `src/hal_unica/`).

---

## Package modules (roles)

| Module | Role |
|---|---|
| `cli.py` | Typer CLI: all `hal-unica` commands |
| `client.py` | HAL Search API client (pagination, retries, throttling) |
| `fields.py` | Default Solr field lists for harvests |
| `timeutil.py` | UTC helpers, watermarks, lookback / `--since` windows |
| `harvest.py` | Full or incremental archive of UniCA HAL metadata (upsert by `halId_s`) |
| `census.py` | Related-identifier census, DOI resolution orchestration, misfiled queue, census artifacts |
| `datacite.py` | DataCite DOI resolve + repository / `object_kind` classification |
| `data_repos.py` | Nakala / RDG focus scan + DOI enrichment helpers |
| `focus_links.py` | Build `unica_data_repo_links.jsonl` from census publications |
| `software.py` | SOFTWARE deposits harvest + **dataset→publications** index builder |
| `data_papers.py` | Data-paper harvest (`DATAPAPER`) + linked-dataset enrichment from census cache |
| `refresh.py` | Daily orchestration: census → software → data papers → index → focus → site |
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
| `hal-unica refresh` | **Default daily path** | Incremental census (lookback) → software → data papers → dataset index → Nakala/RDG focus links → rebuild `docs/` |
| `hal-unica refresh --full` | Sunday / repair gaps | Same pipeline, but re-fetches the full related-data census query (still reuses DOI cache) |
| `hal-unica build-site` | After local data edits | Rebuild Pages HTML from existing `data/` + `data/census/` (no HAL calls) |

```bash
# Weekday-style incremental (2-day lookback)
hal-unica refresh --lookback-days 2

# Full relatedData rebuild (DOI cache kept)
hal-unica refresh --full

# Rebuild site only
hal-unica build-site
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
| `hal-unica find-data-repos` | Find Nakala / Recherche Data Gouv links (focus scan) | Legacy / focused audit |
| `hal-unica resolve-repos` | Re-resolve DOIs in an existing links JSONL via DataCite | Refresh repository labels on focus hits |
| `hal-unica report` | HTML report from focus-link JSONL | Optional offline report |

```bash
# Full metadata archive (optional; large)
hal-unica harvest -o data/unica_hal_metadata.jsonl
hal-unica harvest --lookback-days 2 --from-watermark -o data/unica_hal_metadata.jsonl

# Census only
hal-unica census
hal-unica census --lookback-days 2

# Software / data papers only
hal-unica software
hal-unica data-papers

# Nakala/RDG focus tooling
hal-unica find-data-repos -o data/unica_data_repo_links.jsonl
hal-unica resolve-repos --links data/unica_data_repo_links.jsonl
hal-unica report --links data/unica_data_repo_links.jsonl -o docs/report.html
```

Preview locally: `python -m http.server 8765 -d docs`.

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

| When (UTC) | Paris (CEST / CET) | Mode |
|---|---|---|
| Mon–Sat **04:00 UTC** | **06:00** / **05:00** | Incremental (`--lookback-days 2`) |
| Sunday **04:00 UTC** | **06:00** / **05:00** | Full census (`--full`) |

After a successful refresh **with file changes**, the same workflow deploys GitHub Pages (bot pushes with `GITHUB_TOKEN` do not trigger `pages.yml` alone).

**Caveat:** GitHub scheduled workflows are often delayed (minutes to hours). Manual run: Actions → **Daily incremental refresh** → `incremental` or `full`.

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
| [`data/census/summary.json`](data/census/summary.json) | Full-census aggregates |
| [`data/census/census.meta.json`](data/census/census.meta.json) | Watermark for incremental refresh |
| [`data/census/METHODOLOGY.md`](data/census/METHODOLOGY.md) | Auto-generated method + counts for last census run |
| [`data/unica_data_repo_links.jsonl`](data/unica_data_repo_links.jsonl) | Nakala/RDG focus hits |
| [`docs/`](docs/) | Published site (`docs/data/census/` mirrors census artifacts) |
| [`docs/sitemap.xml`](docs/sitemap.xml) / [`docs/robots.txt`](docs/robots.txt) | SEO crawl hints |

---

## Design decisions worth remembering

1. **Do not treat every related DOI as a dataset.** Journals, arXiv, ResearchGate, publisher platforms are `publication_landing`. Unknown hosts must not default to `dataset_repo`.
2. **Track wrong fields instead of dropping them.** Misfiled Nakala/Zenodo DOIs in `relatedPublication_s` feed the correction queue — unless the same DOI is already in `relatedData_s`.
3. **Upsert + watermark**, never wipe the JSONL on `--since` / lookback harvests.
4. **Sunday full rebuild** is the safety net for missed incrementals.
5. **`retrieved_at` is sticky** so newly discovered datasets stay sortable after later rebuilds.
6. **Timestamps on the site are Europe/Paris** (CET/CEST); machine-readable `datetime` attributes stay UTC.
7. **Daily refresh deploys Pages itself** when it commits, because `GITHUB_TOKEN` pushes do not trigger `pages.yml`.
