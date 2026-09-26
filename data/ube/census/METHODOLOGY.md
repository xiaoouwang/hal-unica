# Related-data repository census — methodology

Generated: `2026-09-26T09:24:28Z`  
Collection: `UNIV-BOURGOGNE`  
Run window: `2026-09-26T09:24:27Z` → `2026-09-26T09:24:28Z`

## Goal

For every UniCA HAL notice that links a related identifier (ideally as
`relatedData`), record **which identifier was linked**, **which HAL field it
came from**, **which repository it resolves to**, and keep the raw evidence so
misfiled dataset links can be corrected.

## Pipeline

1. **HAL Search API** — `q=(relatedData_s:*) OR (relatedPublication_s:10.*) OR (seeAlso_s:*)` on `/search/UNIV-BOURGOGNE/`
   with Solr cursor pagination (`sort=docid asc`). Optional
   `modifiedDate_tdate` window for incremental refresh; merge by `halId_s`.
2. **Token parse** — values from `relatedData_s`, `relatedPublication_s`, and
   `seeAlso_s` are classified as `doi`, `url`, `hal_id`, or `other`. Each token
   keeps `source_field` / `expected_field` / `field_ok` provenance.
3. **DataCite resolve** — each unique DOI is fetched from
   `https://api.datacite.org/dois/{doi}` (cache: `doi_resolutions.jsonl`).
4. **Repository label + object_kind** — from landing host / publisher / known
   DOI prefix (`dataset_repo` vs `publication_landing` vs unresolved). Unknown
   hosts are **not** assumed to be data repositories. See project `README.md`.
5. **Misfiled flag** — if a DOI resolves to a `dataset_repo`, was filed outside
   `relatedData_s`, **and** the same DOI is not also present in `relatedData_s`
   on that notice, it is listed in `misfiled_dataset_links.csv`. When the DOI
   already appears in `relatedData_s`, an extra mention elsewhere is treated as
   supplementary (not a correction).
6. **Dataset index** (built after census) — `dataset_to_publications.*` keeps
   only `object_kind=dataset_repo`, with sticky `retrieved_at` for the
   All repositories page.

## Artifacts

| File | Contents |
|---|---|
| `publications_related_data.jsonl` | One HAL notice per line + all related tokens and resolutions |
| `doi_resolutions.jsonl` | One unique DOI per line (DataCite fields + repository label) |
| `doi_to_repository.csv` | Flat DOI → repository dictionary (all object kinds) |
| `doi_hal_repository_map.csv` | Full correspondence: HAL notice ↔ DOI ↔ repository ↔ **source field** |
| `dataset_to_publications.csv` / `.jsonl` | **Dataset-only** DOI → HAL publications (+ `retrieved_at`) |
| `misfiled_dataset_links.csv` | Dataset landings filed outside `relatedData_s` (correction queue) |
| `summary.json` | Aggregated counts including `by_dataset_source_field` / `by_object_kind` |
| `run_manifest.json` | Run metadata and method checklist |
| `ube-census.log` | Chronological run log |

Project-level documentation (design, refresh schedule, classification rules):
repository root `README.md`.


## Counts (this run)

- HAL notices with linked identifiers: **261**
- Related tokens: **385**
- Unique DOIs resolved: **301**
- Publications with at least one dataset-repo landing: **147**
- Misfiled dataset links (wrong HAL field): **20**
- Publications with ≥1 misfiled dataset link: **19**

### Dataset DOIs by HAL source field

- **`relatedData_s`**: 177
- **`relatedPublication_s`**: 18
- **`seeAlso_s`**: 7

### By repository (DOI evidence)

- **Recherche Data Gouv**: 104
- **NAKALA**: 28
- **Journal DOI (10.4000)**: 24
- **Zenodo**: 23
- **dataUBFC - Atelier de la donnée de Bourgogne-Franche-Comté**: 15
- **Portail Data Inra**: 13
- **Dryad**: 10
- **Journal DOI (10.1007)**: 9
- **Journal DOI (10.3917)**: 9
- **Progedo-Adisp**: 9
- **Journal DOI (10.1002)**: 7
- **Figshare**: 5
- **Journal DOI (10.1016)**: 5
- **Mendeley Data**: 4
- **Australian Antarctic Data Centre**: 3
- **CIRAD Dataverse**: 3
- **DOI prefix 10.3390**: 3
- **Imagerie et Vision Artificielle**: 3
- **Journal DOI (10.1093)**: 3
- **Agroscope**: 2
- **Autorité de sûreté nucléaire et de radioprotection**: 2
- **Centre interlangues : texte, image, langage**: 2
- **Classiques Garnier**: 2
- **DOI prefix 10.1111**: 2
- **DOI prefix 10.1515**: 2
- **DOI prefix 10.25666**: 2
- **DOI prefix 10.37811**: 2
- **Editions et presses universitaires de Reims**: 2
- **GitHub**: 2
- **INRAE (prefix 10.15454)**: 2
- **Journal DOI (10.1109)**: 2
- **Laboratoire Chrono-environnement (UMR 6249)**: 2
- **arXiv**: 2
- **AU/AADC > Australian Antarctic Data Centre, Australia**: 1
- **Copernicus Climate Change Service (C3S) Climate Data Store (CDS)**: 1
- **DOI prefix 10.1021**: 1
- **DOI prefix 10.1046**: 1
- **DOI prefix 10.1128**: 1
- **DOI prefix 10.1364**: 1
- **DOI prefix 10.17504**: 1
- **DOI prefix 10.18485**: 1
- **DOI prefix 10.20870**: 1
- **DOI prefix 10.24310**: 1
- **DOI prefix 10.26820**: 1
- **DOI prefix 10.33386**: 1
- **DOI prefix 10.3389**: 1
- **DOI prefix 10.33996**: 1
- **DOI prefix 10.35381**: 1
- **DOI prefix 10.3897**: 1
- **DOI prefix 10.4324**: 1
- **DOI prefix 10.5194**: 1
- **DOI prefix 10.52497**: 1
- **DOI prefix 10.57088**: 1
- **Journal DOI (10.1017)**: 1
- **Journal DOI (10.1038)**: 1
- **Journal DOI (10.1371)**: 1
- **KIT publications**: 1
- **Laboratoire Chrono-environnement**: 1
- **OSF**: 1
- **Portail Data INRAE**: 1
- **Recherche Data Gouv → HAL notice**: 1
- **Science Data Bank**: 1
- **data.InDoRES**: 1

### By landing host

- `entrepot.recherche.data.gouv.fr`: 77
- `nakala.fr`: 26
- `search-data.ubfc.fr`: 25
- `zenodo.org`: 23
- `data.inrae.fr`: 21
- `data.inra.fr`: 14
- `datadryad.org`: 10
- `data.progedo.fr`: 9
- `figshare.com`: 5
- `data.aad.gov.au`: 4
- `data.mendeley.com`: 4
- `dataverse.cirad.fr`: 3
- `arxiv.org`: 2
- `classiques-garnier.com`: 2
- `ira.agroscope.ch`: 2
- `irsn.spherik.com`: 2
- `library.oapen.org`: 2
- `www2.dijon.inrae.fr`: 2
- `carrtel-collection.hub.inrae.fr`: 1
- `cds.climate.copernicus.eu`: 1
- `data.indores.fr:443`: 1
- `hal.inrae.fr`: 1
- `osf.io`: 1
- `publikationen.bibliothek.kit.edu`: 1
- `scidb.cn`: 1
