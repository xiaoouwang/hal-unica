# Open science triptych — UNIV-BOURGOGNE

**4** candidate(s) — 2026-10-01T11:01:14Z.

## Detection hubs

1. **Publication** — scholarly notice with dataset + software associations (`relatedData_s` / `relatedSoftware_s` / TEI / SOFTWARE backlinks).

2. **Software** — `SOFTWARE` deposit with `relatedPublication_s` + `relatedData_s` (DOI→HAL when needed).

3. **Dataset notice** — dataset-like deposit (often `OTHER`) with `relatedPublication_s` + `relatedSoftware_s` (notice itself = data pillar).


## tel-05027848 — Géoprospective et modélisation climatique de la végétation urbaine dans une perspective d'adaptation aux fortes chaleurs : application à Dijon Métropole.

- Hubs: `publication`
- Match: `publication_hub:relatedData+relatedSoftware`
- Publication: https://theses.hal.science/tel-05027848v2
- Datasets (1):
  - `10.25666/DATAUBFC-2025-07-04` ← `publication.relatedData_s`
- Software (2):
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : hal-05127963
  - `tei_relatedItem_software` ← `publication.tei.relatedItem:Cites` : https://hal.science/hal-05127963

## tel-03815132 — Production et circulation des épées à poignée métallique de l'âge du Bronze en Europe occidentale

- Hubs: `publication`, `software`
- Match: `publication_hub:relatedData+software_signals|software_hub:relatedPublication+relatedData`
- Publication: https://theses.hal.science/tel-03815132v1
- Datasets (17):
  - `10.25666/DATAUBFC-2024-03-06` ← `publication.relatedData_s`
  - `10.34847/nkl.d39d9961` ← `publication.relatedData_s`
  - `10.34847/nkl.bc14e229` ← `publication.relatedData_s`
  - `10.34847/nkl.ceb7wma5` ← `publication.relatedData_s`
  - `10.34847/nkl.c3cb1u04` ← `publication.relatedData_s`
  - `10.34847/nkl.25a6053g` ← `publication.relatedData_s`
  - `10.34847/nkl.b89d1b31` ← `publication.relatedData_s`
  - `10.34847/nkl.57b97j11` ← `publication.relatedData_s`
  - `10.34847/nkl.d2e3st7r` ← `publication.relatedData_s`
  - `10.34847/nkl.43cfm658` ← `publication.relatedData_s`
  - `10.34847/nkl.bd85a75x` ← `publication.relatedData_s`
  - `10.34847/nkl.26edsxq7` ← `publication.relatedData_s`
  - `10.34847/nkl.0d0f3cfn` ← `publication.relatedData_s`
  - `10.34847/nkl.283c14y2` ← `publication.relatedData_s`
  - `10.34847/nkl.37c9dja7` ← `publication.relatedData_s`
  - `10.34847/nkl.1fef36al` ← `publication.relatedData_s`
  - `10.34847/nkl.b397xqmx` ← `publication.relatedData_s`
- Software (2):
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04589525
  - `softCodeRepository_s` ← `software:hal-04589525.softCodeRepository_s` : https://github.com/lodumont/EPoMAB

## hal-03049733 — Microbial networks inferred from environmental DNA data for biomonitoring ecosystem change: strengths and pitfalls

- Hubs: `publication`
- Match: `publication_hub:relatedData+relatedSoftware`
- Publication: https://hal.science/hal-03049733v1
- Datasets (2):
  - `10.15454/3DPFNJ` ← `publication.relatedData_s`
  - `10.15454/WOICSE` ← `publication.relatedData_s`
- Software (2):
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : 10.15454/ZWDFJK
  - `tei_relatedItem_software` ← `publication.tei.relatedItem:Cites` : https://doi.org/10.15454/ZWDFJK

## hal-03218256 — Microbial association networks give relevant insights into plant pathobiomes

- Hubs: `publication`
- Match: `publication_hub:relatedData+relatedSoftware`
- Publication: https://hal.science/hal-03218256v1
- Datasets (2):
  - `10.15454/5WD6P6` ← `publication.relatedData_s`
  - `10.15454/A24N4C` ← `publication.relatedData_s`
- Software (2):
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : 10.15454/WLHBP6
  - `tei_relatedItem_software` ← `publication.tei.relatedItem:Cites` : https://doi.org/10.15454/WLHBP6

---
Files: `publications_with_dataset_and_software.csv` / `.jsonl`.

