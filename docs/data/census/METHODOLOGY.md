# Related-data repository census — methodology

Generated: `2026-09-22T09:44:15Z`  
Collection: `UNIV-COTEDAZUR`  
Run window: `2026-09-22T09:43:08Z` → `2026-09-22T09:44:15Z`

## Goal

For every UniCA HAL notice that links a related identifier (ideally as
`relatedData`), record **which identifier was linked**, **which HAL field it
came from**, **which repository it resolves to**, and keep the raw evidence so
misfiled dataset links can be corrected.

## Pipeline

1. **HAL Search API** — `q=(relatedData_s:*) OR (relatedPublication_s:10.*) OR (seeAlso_s:*)` on `/search/UNIV-COTEDAZUR/`
   with Solr cursor pagination (`sort=docid asc`).
2. **Token parse** — values from `relatedData_s`, `relatedPublication_s`, and
   `seeAlso_s` are classified as `doi`, `url`, `hal_id`, or `other`. Each token
   keeps `source_field` / `expected_field` / `field_ok` provenance.
3. **DataCite resolve** — each unique DOI is fetched from
   `https://api.datacite.org/dois/{doi}`.
4. **Repository label** — derived from landing URL host when possible
   (e.g. `zenodo.org` → Zenodo, `nakala.fr` → NAKALA,
   `*.recherche.data.gouv.fr` / `data.inrae.fr` → Recherche Data Gouv),
   else DataCite publisher / DOI prefix.
5. **Misfiled flag** — if a DOI resolves to a `dataset_repo` but
   `source_field != relatedData_s`, it is listed in
   `misfiled_dataset_links.csv` for depositor outreach.

## Artifacts

| File | Contents |
|---|---|
| `publications_related_data.jsonl` | One HAL notice per line + all related tokens and resolutions |
| `doi_resolutions.jsonl` | One unique DOI per line (DataCite fields + repository label) |
| `doi_to_repository.csv` | Flat DOI → repository dictionary |
| `doi_hal_repository_map.csv` | Full correspondence: HAL notice ↔ DOI ↔ repository ↔ **source field** |
| `misfiled_dataset_links.csv` | Dataset landings filed outside `relatedData_s` (correction queue) |
| `summary.json` | Aggregated counts including `by_dataset_source_field` |
| `run_manifest.json` | Run metadata and method checklist |
| `census.log` | Chronological run log |

## Counts (this run)

- HAL notices with linked identifiers: **313**
- Related tokens: **508**
- Unique DOIs resolved: **401**
- Publications with at least one dataset-repo landing: **172**
- Misfiled dataset links (wrong HAL field): **82**
- Publications with ≥1 misfiled dataset link: **61**

### Dataset DOIs by HAL source field

- **`relatedData_s`**: 193
- **`relatedPublication_s`**: 80
- **`seeAlso_s`**: 2

### By repository (DOI evidence)

- **Unknown (DOI not in DataCite)**: 148
- **Zenodo**: 95
- **Recherche Data Gouv**: 77
- **SEANOE**: 15
- **Sismer**: 11
- **NAKALA**: 10
- **Theia**: 8
- **Figshare**: 5
- **International Federation of Digital Seismograph Networks**: 4
- **arXiv**: 4
- **Unpublished**: 3
- **DataSuds**: 2
- **Epos-France Seismological Data Center**: 2
- **Harvard Dataverse**: 2
- **Ifremer**: 2
- **JAMSTEC**: 2
- **Karlsruhe Institute of Technology**: 2
- **Mendeley Data**: 2
- **Mercator Ocean International**: 2
- **OSF**: 2
- **Observatoire des Sciences de l'Univers de la Réunion**: 2
- **Royal Belgian Institute for Space Aeronomy**: 2
- **data.InDoRES**: 2
- **AusPass**: 1
- **CDS, Centre de Données astronomiques de Strasbourg**: 1
- **Centre de Donnees Strasbourg (CDS)**: 1
- **Commonwealth of Australia (Geoscience Australia)**: 1
- **ETH Zurich**: 1
- **INRAE (prefix 10.15454)**: 1
- **Institut de physique du globe de Paris, Université Paris Cité**: 1
- **Interdisciplinary Earth Data Alliance (IEDA)**: 1
- **Karlsruher Institut für Technologie (KIT)**: 1
- **Mistrals**: 1
- **NASA Planetary Data System**: 1
- **NOAA National Centers for Environmental Information**: 1
- **OSU OREME**: 1
- **OpenNeuro**: 1
- **PANGAEA**: 1
- **Progedo-Adisp**: 1
- **STScI/MAST**: 1
- **Schloss Dagstuhl – Leibniz-Zentrum für Informatik**: 1
- **University of Bristol**: 1
- **Université Côte d’Azur**: 1

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
