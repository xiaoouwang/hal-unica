# hal-unica

Open-science monitoring for **[Université Côte d’Azur](https://univ-cotedazur.fr/)** on HAL (`UNIV-COTEDAZUR`).

This repository harvests UniCA HAL notices, resolves linked identifiers (especially dataset DOIs), classifies which landings are real **data repositories** vs publications/preprints, and publishes a static site on GitHub Pages.

Live site: https://xiaoouwang.github.io/hal-unica/

| Page | URL |
|---|---|
| Statistics | https://xiaoouwang.github.io/hal-unica/ |
| Nakala / Recherche Data Gouv focus | https://xiaoouwang.github.io/hal-unica/related-datasets.html |
| **All repositories** (dataset → publications) | https://xiaoouwang.github.io/hal-unica/all-repositories.html |
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

Every token keeps **provenance** (`source_field`). If a DOI resolves to a data repository but was **not** filed in `relatedData_s`, it appears on **To Be Corrected** and in `misfiled_dataset_links.csv`.

Each resolved DOI gets an `object_kind`:

| `object_kind` | Meaning | Shown on All repositories? |
|---|---|---|
| `dataset_repo` | Landing is a data repository (Zenodo, RDG, SEANOE, NAKALA, …) | **Yes** |
| `publication_landing` | Journal, preprint, ResearchGate, publisher site, … | No (still in full census CSVs) |
| `unresolved` / `other` | Could not classify | No |

Classification lives in `src/hal_unica/datacite.py` (`classify_repository`): known data hosts, known publication hosts, journal DOI prefixes, then **never** assume unknown hosts are datasets.

The **All repositories** page and `dataset_to_publications.*` are **dataset-only** (`object_kind == dataset_repo`). The full census `summary.json` / `doi_to_repository.csv` still list every related DOI (including journals) for audit.

---

## Architecture

```
HAL Search API (UNIV-COTEDAZUR)
        │
        ├─ harvest  → data/unica_hal_metadata.jsonl   (~full collection; optional)
        │
        └─ census   → data/census/
              │         publications_related_data.jsonl  (HAL notices + tokens)
              │         doi_resolutions.jsonl            (DataCite cache)
              │         summary.json, CSVs, METHODOLOGY.md
              │
              ├─ software harvest → software_deposits.*
              ├─ invert index     → dataset_to_publications.*  (dataset_repo only)
              ├─ focus filter     → data/unica_data_repo_links.jsonl  (Nakala/RDG)
              └─ build-site       → docs/  (GitHub Pages)
```

Package entrypoint: `hal-unica` (`src/hal_unica/`).

Key modules:

| Module | Role |
|---|---|
| `harvest.py` | Full/incremental HAL metadata archive (upsert by `halId_s`) |
| `census.py` | Related-identifier census + artifacts + misfiled queue |
| `datacite.py` | DOI resolve + repository / `object_kind` classification |
| `software.py` | SOFTWARE deposits + **dataset→publications** index |
| `focus_links.py` | Nakala / Recherche Data Gouv focus hits |
| `refresh.py` | Daily orchestration: census → software → index → site |
| `site.py` | Static HTML under `docs/` |

---

## Incremental updates (how “old notice edited today” is caught)

HAL exposes `modifiedDate_tdate`. When a depositor edits an **old** notice to add a dataset DOI, HAL bumps that timestamp. The daily job asks for notices with `modifiedDate_tdate` in a recent window, then **merges by `halId_s`**.

```bash
hal-unica refresh --lookback-days 2   # weekday default
hal-unica refresh --full              # Sunday / safety net
```

What `refresh` does **not** do: re-download the ~99k-document metadata corpus.

What it **does**:

1. Pull notices matching the census query that were modified since `max(watermark − 1h, now − lookback)`.
2. Upsert them into `publications_related_data.jsonl`.
3. Resolve **only new** DOIs; reuse `doi_resolutions.jsonl`.
4. Re-harvest SOFTWARE (small).
5. Rebuild `dataset_to_publications.*` and focus links.
6. Rebuild `docs/` and (in CI) commit so Pages redeploys.

Schedule: [`.github/workflows/daily-refresh.yml`](.github/workflows/daily-refresh.yml)

- **Mon–Sat 04:00 UTC** — incremental (`--lookback-days 2`)
- **Sunday 04:00 UTC** — full census rebuild (DOI cache still reused)
- Manual: Actions → “Daily incremental refresh” → `incremental` or `full`

If Actions is down for more than the lookback window, the next **Sunday full** run closes the gap.

### Retrieval dates on All repositories

Each dataset row has:

| Field | Meaning |
|---|---|
| `retrieved_at` | First time this dataset DOI entered **our** index (persisted across rebuilds) |
| `hal_modified_at` | Latest HAL `modifiedDate_tdate` among linked notices |

UI default sort: **Newest retrieved**. New DOIs discovered after an edit to an old notice get a fresh `retrieved_at` and surface at the top. Already-known DOIs keep their original `retrieved_at`; use **Newest HAL update** to see refreshed links on older datasets.

---

## Snapshot (2026-09-22)

Figures move with each refresh; check `data/census/summary.json` and `dataset_to_publications_summary.json` for current numbers.

| Metric | Approx. value |
|---:|---:|
| HAL notices with linked identifiers (census query) | **313** |
| Unique DOIs resolved (all kinds) | **401** |
| Of which `dataset_repo` landings (links) | **264** |
| Unique dataset DOIs on All repositories | **246** |
| Misfiled dataset links (wrong HAL field) | **73** |
| HAL `SOFTWARE` deposits | **78** |

Top **data** repositories (All repositories index): Zenodo · Recherche Data Gouv · SEANOE · Sismer · SEDOO/Theia · NAKALA · …

---

## Artifacts

| Path | Meaning |
|---|---|
| [`data/census/dataset_to_publications.csv`](data/census/dataset_to_publications.csv) | **Dataset DOI → HAL publication(s)** (+ `retrieved_at`, source field) — powers All repositories |
| [`data/census/misfiled_dataset_links.csv`](data/census/misfiled_dataset_links.csv) | Dataset DOIs filed outside `relatedData_s` |
| [`data/census/doi_to_repository.csv`](data/census/doi_to_repository.csv) | Every related DOI → repository / kind (includes journals) |
| [`data/census/doi_hal_repository_map.csv`](data/census/doi_hal_repository_map.csv) | HAL notice ↔ DOI ↔ repository ↔ source field |
| [`data/census/doi_resolutions.jsonl`](data/census/doi_resolutions.jsonl) | DataCite resolution cache |
| [`data/census/publications_related_data.jsonl`](data/census/publications_related_data.jsonl) | Per-notice tokens + resolutions |
| [`data/census/software_deposits.csv`](data/census/software_deposits.csv) | SOFTWARE + code repos + SWHIDs |
| [`data/census/summary.json`](data/census/summary.json) | Full-census aggregates |
| [`data/census/census.meta.json`](data/census/census.meta.json) | Watermark for incremental refresh |
| [`data/census/METHODOLOGY.md`](data/census/METHODOLOGY.md) | Auto-generated method + **counts for last run** |
| [`data/unica_data_repo_links.jsonl`](data/unica_data_repo_links.jsonl) | Nakala/RDG focus hits |
| [`docs/`](docs/) | Published site (same census files under `docs/data/census/`) |

---

## Local commands

```bash
pip install -e .

# Full collection metadata archive (large; optional for the website)
hal-unica harvest -o data/unica_hal_metadata.jsonl
hal-unica harvest --lookback-days 2 --from-watermark -o data/unica_hal_metadata.jsonl

# What powers the website
hal-unica refresh --lookback-days 2
hal-unica refresh --full

# Pieces in isolation
hal-unica census
hal-unica find-data-repos
hal-unica build-site
```

Preview locally: serve `docs/` (e.g. `python -m http.server 8765 -d docs`).

---

## GitHub Pages

Deployed from `docs/` via [`.github/workflows/pages.yml`](.github/workflows/pages.yml). The daily refresh workflow commits updated `data/census/` + `docs/`; Pages picks up the push.

---

## Design decisions worth remembering

1. **Do not treat every related DOI as a dataset.** Journals, arXiv, ResearchGate, publisher platforms are `publication_landing`. Unknown hosts must not default to `dataset_repo`.
2. **Track wrong fields instead of dropping them.** Misfiled Nakala/Zenodo DOIs in `relatedPublication_s` are exactly the correction queue.
3. **Upsert + watermark**, never wipe the JSONL on `--since` / lookback harvests.
4. **Sunday full rebuild** is the safety net for missed incrementals.
5. **`retrieved_at` is sticky** so “newly discovered datasets” remain sortable after later full rebuilds.
