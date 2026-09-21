# hal-unica

Open-science snapshot for **[Université Côte d’Azur](https://univ-cotedazur.fr/)** on [HAL](https://hal.science/UNIV-COTEDAZUR): harvest statistics and publications that point to datasets in **NAKALA** or **Recherche Data Gouv** (including federated nodes such as Data INRAE).

## Live pages (GitHub Pages)

- Statistics: https://xiaoouwang.github.io/hal-unica/
- Related datasets: https://xiaoouwang.github.io/hal-unica/related-datasets.html

| Page | Contents |
|---|---|
| [`docs/index.html`](docs/index.html) | General statistics |
| [`docs/related-datasets.html`](docs/related-datasets.html) | Publications with a related dataset |

```bash
hal-unica build-site
open docs/index.html
```

## Snapshot (2026-09-21)

### HAL collection `UNIV-COTEDAZUR`

| Metric | Value |
|---:|---:|
| Documents (latest version only) | **99 136** |
| With a DOI | **41 374** (~42%) |
| Top types | ART 44 342 · COMM 25 165 · COUV 7 723 · REPORT 4 557 · THESE 3 765 |

### Data-repository links

Notices that reference Nakala / Recherche Data Gouv (DOI, URL, or HAL `relatedData`), refined with DataCite. **Data INRAE is counted as Recherche Data Gouv** (federated node).

| Repository | Notices |
|---|---:|
| Recherche Data Gouv | 51 |
| NAKALA | 11 |
| INRA/INRAE DOI → HAL notice (not a data vault) | ~21 |

### Publications with a related dataset

**51** publications declare HAL `relatedData` landing on a real data repository:

| Repository | Publications |
|---|---:|
| Recherche Data Gouv | 44 |
| NAKALA | 7 |

JSON: [`docs/data/related-publications.json`](docs/data/related-publications.json)

## Method (short)

1. Harvest metadata from `https://api.archives-ouvertes.fr/search/UNIV-COTEDAZUR/` (cursor pagination, latest version per `halId`).
2. Detect links via DOI prefixes (`10.34847` Nakala, `10.57745` / `10.15454` Recherche Data Gouv ecosystem), URLs, and HAL `relatedData_s`.
3. Resolve DOIs with DataCite → publisher, landing host, repository label.
4. **Related datasets page** keeps only `related_data` evidence with `object_kind = dataset_repo`.

## CLI

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

hal-unica count
hal-unica harvest -o data/unica_hal_metadata.jsonl
hal-unica find-data-repos
hal-unica build-site
```

## Enable GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch `main` → Folder **`/docs`**.

## Licence / data

HAL metadata is open; dataset landings follow each repository’s terms. This project stores derived link metadata only (no PDF harvest).
