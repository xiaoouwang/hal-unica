# hal-unica

Open-science snapshot for **[Université Côte d’Azur](https://univ-cotedazur.fr/)** on [HAL](https://hal.science/UNIV-COTEDAZUR).

## Live site

- Statistics: https://xiaoouwang.github.io/hal-unica/
- Nakala / Recherche Data Gouv focus: https://xiaoouwang.github.io/hal-unica/related-datasets.html
- **All repositories** (dataset → publications): https://xiaoouwang.github.io/hal-unica/all-repositories.html
- **Software & source code**: https://xiaoouwang.github.io/hal-unica/software.html
- **Documentation + downloads**: https://xiaoouwang.github.io/hal-unica/documentation.html

## What is documented

Beyond the charts, the repo stores the full correspondence tables:

| Artifact | Meaning |
|---|---|
| [`data/census/dataset_to_publications.csv`](data/census/dataset_to_publications.csv) | **Dataset DOI → related HAL publication(s)** |
| [`data/census/doi_to_repository.csv`](data/census/doi_to_repository.csv) | Each related **DOI → repository** |
| [`data/census/doi_hal_repository_map.csv`](data/census/doi_hal_repository_map.csv) | **HAL notice ↔ dataset DOI ↔ repository** |
| [`data/census/software_deposits.csv`](data/census/software_deposits.csv) | SOFTWARE deposits + code repos + SWHIDs |
| [`data/census/doi_resolutions.jsonl`](data/census/doi_resolutions.jsonl) | Full DataCite resolution per DOI |
| [`data/census/publications_related_data.jsonl`](data/census/publications_related_data.jsonl) | Per-publication relatedData + resolutions |
| [`data/census/summary.json`](data/census/summary.json) | Aggregates |
| [`data/census/run_manifest.json`](data/census/run_manifest.json) | Run metadata |
| [`data/census/METHODOLOGY.md`](data/census/METHODOLOGY.md) | Method write-up |
| [`logs/census.log`](logs/census.log) / [`data/census/run.log`](data/census/run.log) | Chronological run log |

Same files are published under [`docs/data/census/`](docs/data/census/) for GitHub Pages downloads.

## Snapshot (2026-09-21)

### HAL collection

| Metric | Value |
|---:|---:|
| Documents (latest version) | **99 136** |
| With DOI | **41 374** (~42%) |

### Full relatedData census (all repositories)

| Metric | Value |
|---:|---:|
| HAL notices with `relatedData` | **129** |
| Related tokens | **202** |
| Unique DOIs resolved | **181** |

Top repositories (by related DOI): **Recherche Data Gouv** 75 · **Zenodo** 52 · **SEANOE** 15 · **Theia** 8 · **NAKALA** 7 · …

### Software

| Metric | Value |
|---:|---:|
| HAL `SOFTWARE` deposits | **78** |
| With Software Heritage SWHID | **63** |
| With code repository URL | **57** |
| With related publication | **31** |

### Nakala / RDG focus page

Publications with `relatedData` landing on Recherche Data Gouv (incl. Data INRAE) or NAKALA: see the dedicated page (44 + 7).

## Method (short)

1. Harvest UniCA HAL metadata (`UNIV-COTEDAZUR`).
2. **Census**: list all `relatedData_s:*`, parse tokens, resolve every DOI with DataCite, label repository from landing host / publisher / prefix.
3. Optional focus filter for Nakala / RDG only (`find-data-repos`).

```bash
pip install -e .
hal-unica harvest -o data/unica_hal_metadata.jsonl
hal-unica census                 # all repositories + CSV/JSONL/logs
hal-unica find-data-repos        # Nakala/RDG focus
hal-unica build-site             # writes docs/ including census pages
```

## GitHub Pages

Deployed from `docs/` via GitHub Actions (`.github/workflows/pages.yml`).
