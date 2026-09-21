# Related-data repository census — methodology

Generated: `2026-09-21T15:47:09Z`  
Collection: `UNIV-COTEDAZUR`  
Run window: `2026-09-21T15:46:39Z` → `2026-09-21T15:47:09Z`

## Goal

For every UniCA HAL notice that declares `relatedData`, record **which identifier
was linked**, **which repository it resolves to**, and keep the raw evidence.

## Pipeline

1. **HAL Search API** — `q=relatedData_s:*` on `/search/UNIV-COTEDAZUR/`
   with Solr cursor pagination (`sort=docid asc`).
2. **Token parse** — each `relatedData_s` value is classified as `doi`, `url`,
   `hal_id`, or `other`.
3. **DataCite resolve** — each unique DOI is fetched from
   `https://api.datacite.org/dois/{doi}`.
4. **Repository label** — derived from landing URL host when possible
   (e.g. `zenodo.org` → Zenodo, `nakala.fr` → NAKALA,
   `*.recherche.data.gouv.fr` / `data.inrae.fr` → Recherche Data Gouv),
   else DataCite publisher / DOI prefix.

## Artifacts

| File | Contents |
|---|---|
| `publications_related_data.jsonl` | One HAL notice per line + all related tokens and resolutions |
| `doi_resolutions.jsonl` | One unique DOI per line (DataCite fields + repository label) |
| `doi_to_repository.csv` | Flat DOI → repository dictionary |
| `doi_hal_repository_map.csv` | Full correspondence: HAL notice ↔ related DOI ↔ repository |
| `summary.json` | Aggregated counts |
| `run_manifest.json` | Run metadata and method checklist |
| `census.log` | Chronological run log |

## Counts (this run)

- HAL notices with `relatedData`: **129**
- Related tokens: **202**
- Unique DOIs resolved: **181**
- Publications with at least one dataset-repo landing: **123**

### By repository (DOI evidence)

- **Recherche Data Gouv**: 75
- **Zenodo**: 52
- **SEANOE**: 15
- **Theia**: 8
- **NAKALA**: 7
- **International Federation of Digital Seismograph Networks**: 4
- **Figshare**: 3
- **DataSuds**: 2
- **Epos-France Seismological Data Center**: 2
- **Harvard Dataverse**: 2
- **Karlsruhe Institute of Technology**: 2
- **Mendeley Data**: 2
- **Mercator Ocean International**: 2
- **Observatoire des Sciences de l'Univers de la Réunion**: 2
- **Unknown (DOI not in DataCite)**: 2
- **data.InDoRES**: 2
- **AusPass**: 1
- **Centre de Donnees Strasbourg (CDS)**: 1
- **INRAE (prefix 10.15454)**: 1
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
- **University of Bristol**: 1

### By landing host

- `zenodo.org`: 52
- `entrepot.recherche.data.gouv.fr`: 50
- `data.inrae.fr`: 24
- `seanoe.org`: 15
- `camcatt.sedoo.fr`: 8
- `nakala.fr`: 7
- `fdsn.org`: 5
- `data.indores.fr:443`: 2
- `data.mendeley.com`: 2
- `dataverse.harvard.edu`: 2
- `dataverse.ird.fr`: 2
- `figshare.com`: 2
- `geosur.osureunion.fr`: 2
- `radar.kit.edu`: 2
- `resources.marine.copernicus.eu`: 2
- `seismology.epos-france.fr`: 2
- `archive.stsci.edu`: 1
- `carrtel-collection.hub.inrae.fr`: 1
- `cdsarc.cds.unistra.fr`: 1
- `data.bris.ac.uk`: 1
- `data.oreme.org`: 1
- `data.progedo.fr`: 1
- `doi.pangaea.de`: 1
- `ecl.earthchem.org`: 1
- `mistrals.sedoo.fr`: 1
- `ncei.noaa.gov`: 1
- `openneuro.org`: 1
- `pdssbn.astro.umd.edu`: 1
- `publikationen.bibliothek.kit.edu`: 1
- `springernature.figshare.com`: 1
- `www2.dijon.inrae.fr`: 1
