# Publications UNIV-BOURGOGNE : publi + jeu de données + software

**4** notice(s) — généré 2026-09-29T15:24:17Z.

## Méthode (métadonnées HAL typées)

HAL expose des champs d’API distincts pour les ressources associées ([CCSD, 2025](https://www.ccsd.cnrs.fr/en/2025/02/enhance-the-link-between-your-hal-deposit-and-a-dataset-or-software-a-new-feature-to-increase-the-visibility-of-your-research/)) :

- `relatedData_s` — jeux de données

- `relatedSoftware_s` — logiciels / codes (souvent SWHID)

- `relatedPublication_s` — autres publications


Le TEI du dépôt précise aussi chaque lien via `<relatedItem type="…" subtype="COAR">` (ex. Dataset `c_ddb1`, Software `c_5ce6`).


On ne se fie **pas** uniquement à la résolution DataCite d’un DOI : le typage HAL / COAR prime.


Signaux software acceptés en complément : `swhidId_s`, `softCodeRepository_s`, dépôt HAL `SOFTWARE` lié par `relatedPublication_s`.


## tel-05027848 — Géoprospective et modélisation climatique de la végétation urbaine dans une perspective d'adaptation aux fortes chaleurs : application à Dijon Métropole.

- Type / année : `THESE` / 2024
- URL : https://theses.hal.science/tel-05027848v2
- DOI : `10.70675/30a12212zf58bz4ca3zbc44z5859756f196a`
- Base : `relatedData_s+relatedSoftware_s`
- Champs typés : relatedData=True · relatedSoftware=True
- `relatedData_s` : `10.25666/DATAUBFC-2025-07-04`
- `relatedSoftware_s` : `hal-05127963`
- Jeux de données (1) :
  - `10.25666/DATAUBFC-2025-07-04` ← `publication.relatedData_s` · Cites
- Signaux software (2) :
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : hal-05127963
  - `tei_relatedItem_software` ← `tei.relatedItem:Cites` : https://hal.science/hal-05127963

## tel-03815132 — Production et circulation des épées à poignée métallique de l'âge du Bronze en Europe occidentale

- Type / année : `THESE` / 2022
- URL : https://theses.hal.science/tel-03815132v1
- DOI : `10.70675/27ab3ddez4da0z4d17z816cz12fa08f321dc`
- Base : `relatedData_s+software_signals`
- Champs typés : relatedData=True · relatedSoftware=False
- `relatedData_s` : `10.25666/DATAUBFC-2024-03-06`, `10.34847/nkl.d39d9961`, `10.34847/nkl.bc14e229`, `10.34847/nkl.ceb7wma5`, `10.34847/nkl.c3cb1u04`, `10.34847/nkl.25a6053g`, `10.34847/nkl.b89d1b31`, `10.34847/nkl.57b97j11`, `10.34847/nkl.d2e3st7r`, `10.34847/nkl.43cfm658`, `10.34847/nkl.bd85a75x`, `10.34847/nkl.26edsxq7`, `10.34847/nkl.0d0f3cfn`, `10.34847/nkl.283c14y2`, `10.34847/nkl.37c9dja7`, `10.34847/nkl.1fef36al`, `10.34847/nkl.b397xqmx`
- `relatedSoftware_s` : —
- Jeux de données (17) :
  - `10.25666/DATAUBFC-2024-03-06` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.d39d9961` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.bc14e229` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.ceb7wma5` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.c3cb1u04` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.25a6053g` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.b89d1b31` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.57b97j11` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.d2e3st7r` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.43cfm658` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.bd85a75x` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.26edsxq7` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.0d0f3cfn` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.283c14y2` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.37c9dja7` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.1fef36al` ← `publication.relatedData_s` · IsCitedBy
  - `10.34847/nkl.b397xqmx` ← `publication.relatedData_s` · IsCitedBy
- Signaux software (1) :
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04589525
- Dépôts SOFTWARE :
  - [hal-04589525](https://hal.science/hal-04589525v1) — EPoMAB. European Bronze Age solid-hilted swords database

## hal-03049733 — Microbial networks inferred from environmental DNA data for biomonitoring ecosystem change: strengths and pitfalls

- Type / année : `ART` / 2021
- URL : https://hal.science/hal-03049733v1
- DOI : `10.1111/1755-0998.13302`
- Base : `relatedData_s+relatedSoftware_s`
- Champs typés : relatedData=True · relatedSoftware=True
- `relatedData_s` : `10.15454/3DPFNJ`, `10.15454/WOICSE`
- `relatedSoftware_s` : `10.15454/ZWDFJK`
- Jeux de données (2) :
  - `10.15454/3DPFNJ` ← `publication.relatedData_s` · Cites
  - `10.15454/WOICSE` ← `publication.relatedData_s` · Cites
- Signaux software (2) :
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : 10.15454/ZWDFJK
  - `tei_relatedItem_software` ← `tei.relatedItem:Cites` : https://doi.org/10.15454/ZWDFJK

## hal-03218256 — Microbial association networks give relevant insights into plant pathobiomes

- Type / année : `UNDEFINED` / 2021
- URL : https://hal.science/hal-03218256v1
- DOI : `10.1101/2020.02.21.958033`
- Base : `relatedData_s+relatedSoftware_s`
- Champs typés : relatedData=True · relatedSoftware=True
- `relatedData_s` : `10.15454/5WD6P6`, `10.15454/A24N4C`
- `relatedSoftware_s` : `10.15454/WLHBP6`
- Jeux de données (2) :
  - `10.15454/5WD6P6` ← `publication.relatedData_s` · Cites
  - `10.15454/A24N4C` ← `publication.relatedData_s` · Cites
- Signaux software (2) :
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : 10.15454/WLHBP6
  - `tei_relatedItem_software` ← `tei.relatedItem:Cites` : https://doi.org/10.15454/WLHBP6

---
Fichiers : `publications_with_dataset_and_software.csv` / `.jsonl`.

