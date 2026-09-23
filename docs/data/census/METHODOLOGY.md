# Related-data repository census — methodology

Generated: `2026-09-23T09:12:44Z`  
Collection: `UNIV-COTEDAZUR`  
Run window: `2026-09-23T09:12:43Z` → `2026-09-23T09:12:44Z`

## Goal

For every UniCA HAL notice that links a related identifier (ideally as
`relatedData`), record **which identifier was linked**, **which HAL field it
came from**, **which repository it resolves to**, and keep the raw evidence so
misfiled dataset links can be corrected.

## Pipeline

1. **HAL Search API** — `q=(relatedData_s:*) OR (relatedPublication_s:10.*) OR (seeAlso_s:*)` on `/search/UNIV-COTEDAZUR/`
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
| `census.log` | Chronological run log |

Project-level documentation (design, refresh schedule, classification rules):
repository root `README.md`.


## Counts (this run)

- HAL notices with linked identifiers: **313**
- Related tokens: **508**
- Unique DOIs resolved: **401**
- Publications with at least one dataset-repo landing: **164**
- Misfiled dataset links (wrong HAL field): **72**
- Publications with ≥1 misfiled dataset link: **53**

### Dataset DOIs by HAL source field

- **`relatedData_s`**: 191
- **`relatedPublication_s`**: 71
- **`seeAlso_s`**: 2

### By repository (DOI evidence)

- **Zenodo**: 96
- **Recherche Data Gouv**: 78
- **Journal DOI (10.1007)**: 31
- **Journal DOI (10.1109)**: 20
- **SEANOE**: 15
- **Sismer**: 11
- **Journal DOI (10.1016)**: 10
- **NAKALA**: 10
- **Journal DOI (10.4000)**: 9
- **SEDOO / Theia**: 9
- **Journal DOI (10.1002)**: 6
- **Journal DOI (10.3917)**: 6
- **FDSN / seismic network**: 5
- **Figshare**: 5
- **arXiv**: 5
- **Journal DOI (10.1093)**: 4
- **DOI prefix 10.22489**: 3
- **Journal DOI (10.1038)**: 3
- **Journal DOI (10.1137)**: 3
- **Journal DOI (10.1145)**: 3
- **ResearchGate**: 3
- **Archimer (Ifremer publications)**: 2
- **BIRA-IASB data**: 2
- **CDS**: 2
- **DOI prefix 10.1101**: 2
- **DOI prefix 10.1287**: 2
- **DOI prefix 10.22541**: 2
- **DOI prefix 10.23919**: 2
- **DOI prefix 10.31223**: 2
- **DOI prefix 10.32614**: 2
- **DOI prefix 10.3390**: 2
- **DOI prefix 10.5194**: 2
- **DataSuds**: 2
- **Epos-France Seismological Data Center**: 2
- **Harvard Dataverse**: 2
- **JAMSTEC**: 2
- **Journal DOI (10.1017)**: 2
- **Journal DOI (10.1371)**: 2
- **Mendeley Data**: 2
- **Mercator Ocean / Copernicus Marine**: 2
- **OSF**: 2
- **OSU Réunion**: 2
- **RADAR KIT**: 2
- **data.InDoRES**: 2
- **Canal-U**: 1
- **DOI prefix 10.1044**: 1
- **DOI prefix 10.1051**: 1
- **DOI prefix 10.1075**: 1
- **DOI prefix 10.1111**: 1
- **DOI prefix 10.1117**: 1
- **DOI prefix 10.11606**: 1
- **DOI prefix 10.1163**: 1
- **DOI prefix 10.1177**: 1
- **DOI prefix 10.1504**: 1
- **DOI prefix 10.1561**: 1
- **DOI prefix 10.16995**: 1
- **DOI prefix 10.17632**: 1
- **DOI prefix 10.19272**: 1
- **DOI prefix 10.2139**: 1
- **DOI prefix 10.21494**: 1
- **DOI prefix 10.22152**: 1
- **DOI prefix 10.24072**: 1
- **DOI prefix 10.2478**: 1
- **DOI prefix 10.26508**: 1
- **DOI prefix 10.32908**: 1
- **DOI prefix 10.33166**: 1
- **DOI prefix 10.36863**: 1
- **DOI prefix 10.4135**: 1
- **DOI prefix 10.4171**: 1
- **DOI prefix 10.5465**: 1
- **DOI prefix 10.59641**: 1
- **DOI prefix 10.7819**: 1
- **Dagstuhl**: 1
- **ETH Zurich seismic networks**: 1
- **GEOSCOPE**: 1
- **Geoscience Australia**: 1
- **IEDA**: 1
- **INRAE (prefix 10.15454)**: 1
- **KIT publications**: 1
- **NASA Planetary Data System**: 1
- **NOAA NCEI**: 1
- **OSU OREME**: 1
- **OpenNeuro**: 1
- **PANGAEA**: 1
- **Progedo-Adisp**: 1
- **STScI/MAST**: 1
- **University of Bristol data.bris**: 1

### By landing host

- `zenodo.org`: 95
- `entrepot.recherche.data.gouv.fr`: 52
- `data.inrae.fr`: 24
- `seanoe.org`: 15
- `campagnes.flotteoceanographique.fr`: 11
- `nakala.fr`: 10
- `camcatt.sedoo.fr`: 8
- `fdsn.org`: 5
- `arxiv.org`: 4
- `figshare.com`: 4
- `researchgate.net`: 3
- `archimer.ifremer.fr`: 2
- `data.aeronomie.be`: 2
- `data.indores.fr:443`: 2
- `data.mendeley.com`: 2
- `dataverse.harvard.edu`: 2
- `dataverse.ird.fr`: 2
- `geosur.osureunion.fr`: 2
- `jamstec.go.jp`: 2
- `osf.io`: 2
- `radar.kit.edu`: 2
- `resources.marine.copernicus.eu`: 2
- `seismology.epos-france.fr`: 2
- `archive.stsci.edu`: 1
- `canal-u.tv`: 1
- `carrtel-collection.hub.inrae.fr`: 1
- `cdsarc.cds.unistra.fr`: 1
- `data.bris.ac.uk`: 1
- `data.oreme.org`: 1
- `data.progedo.fr`: 1
- `doi.pangaea.de`: 1
- `drops.dagstuhl.de`: 1
- `ecl.earthchem.org`: 1
- `geoscope.ipgp.fr`: 1
- `mistrals.sedoo.fr`: 1
- `ncei.noaa.gov`: 1
- `networks.seismo.ethz.ch`: 1
- `openneuro.org`: 1
- `pdssbn.astro.umd.edu`: 1
- `pid.geoscience.gov.au`: 1
