# Publications UNIV-COTEDAZUR : publi + jeu de données + software

**3** notice(s) — généré 2026-09-29T15:24:03Z.

## Méthode (métadonnées HAL typées)

HAL expose des champs d’API distincts pour les ressources associées ([CCSD, 2025](https://www.ccsd.cnrs.fr/en/2025/02/enhance-the-link-between-your-hal-deposit-and-a-dataset-or-software-a-new-feature-to-increase-the-visibility-of-your-research/)) :

- `relatedData_s` — jeux de données

- `relatedSoftware_s` — logiciels / codes (souvent SWHID)

- `relatedPublication_s` — autres publications


Le TEI du dépôt précise aussi chaque lien via `<relatedItem type="…" subtype="COAR">` (ex. Dataset `c_ddb1`, Software `c_5ce6`).


On ne se fie **pas** uniquement à la résolution DataCite d’un DOI : le typage HAL / COAR prime.


Signaux software acceptés en complément : `swhidId_s`, `softCodeRepository_s`, dépôt HAL `SOFTWARE` lié par `relatedPublication_s`.


## hal-04162960 — airGRdatasets: Hydro-Meteorological Catchments Datasets for the 'airGR' Packages. Manual of the R package version 0.2.3

- Type / année : `OTHER` / 2025
- URL : https://hal.inrae.fr/hal-04162960v4
- Base : `relatedData_s+software_signals`
- Champs typés : relatedData=True · relatedSoftware=False
- `relatedData_s` : `10.57745/3SPJ4B`
- `relatedSoftware_s` : —
- Jeux de données (1) :
  - `10.57745/3SPJ4B` ← `publication.relatedData_s` · Cites
- Signaux software (2) :
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04481411
  - `swhid_from_software_deposit` ← `software:hal-04481411.swhidId_s` : swh:1:dir:b047cd45ee4f9346a6fa7338c8d7ec230825143d;origin=https://cran.r-project.org/package%253DairGRdatasets;visit=swh:1:snp:c09c87412da9be257d813ea1173036ec6181d5d3;anchor=swh:1:rel:a68ddd145c52c5f9de5771dde91cecd942aecee9;path=/airGRdatasets/
- Dépôts SOFTWARE :
  - [hal-04481411](https://hal.inrae.fr/hal-04481411v4) — airGRdatasets: Hydro-Meteorological Catchments Datasets for the 'airGR' Packages. R package version 0.2.3

## hal-04208050 — airGRteaching: an open-source tool for teaching hydrological modeling with R

- Type / année : `ART` / 2023
- URL : https://hal.inrae.fr/hal-04208050v1
- DOI : `10.5194/hess-27-3293-2023`
- Base : `relatedData_s+relatedSoftware_s`
- Champs typés : relatedData=True · relatedSoftware=True
- `relatedData_s` : `10.32614/CRAN.package.airGRdatasets`, `10.32614/CRAN.package.airGRteaching`
- `relatedSoftware_s` : `swh:1:dir:3ddc33933e5818871e5d5dfc5aeb3f857c40f8b1;origin=https://cran.r-project.org/package%253DairGRteaching;visit=swh:1:snp:cb9adfa360a7cb140bd65ef48c34fd0ee076a7e1;anchor=swh:1:rel:ba15b1b00733887709ff37c99460cdaf6773e3dc;path=/airGRteaching/`
- Jeux de données (2) :
  - `10.32614/CRAN.package.airGRdatasets` ← `publication.relatedData_s` · IsSupplementedBy
  - `10.32614/CRAN.package.airGRteaching` ← `publication.relatedData_s` · Cites
- Signaux software (2) :
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : swh:1:dir:3ddc33933e5818871e5d5dfc5aeb3f857c40f8b1;origin=https://cran.r-project.org/package%253DairGRteaching;visit=swh:1:snp:cb9adfa360a7cb140bd65ef48c34fd0ee076a7e1;anchor=swh:1:rel:ba15b1b00733887709ff37c99460cdaf6773e3dc;path=/airGRteaching/
  - `tei_relatedItem_software` ← `tei.relatedItem:IsSupplementedBy` : https://archive.softwareheritage.org/swh:1:dir:3ddc33933e5818871e5d5dfc5aeb3f857c40f8b1;origin=https://cran.r-project.org/package%253DairGRteaching;visit=swh:1:snp:cb9adfa360a7cb140bd65ef48c34fd0ee076a7e1;anchor=swh:1:rel:ba15b1b00733887709ff37c99460cdaf6773e3dc;path=/airGRteaching/

## hal-03807744 — ISSA: Generic Pipeline, Knowledge Model and Visualization tools to Help Scientists Search and Make Sense of a Scientific Archive

- Type / année : `COMM` / 2022
- URL : https://hal.science/hal-03807744v1
- DOI : `10.1007/978-3-031-19433-7_38`
- Base : `mixed_or_software_deposit`
- Champs typés : relatedData=False · relatedSoftware=True
- `relatedData_s` : —
- `relatedSoftware_s` : `hal-04128090`
- Jeux de données (1) :
  - `10.5281/zenodo.10381606` ← `software:hal-04807540.relatedData_s`
- Signaux software (6) :
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : hal-04128090
  - `tei_relatedItem_software` ← `tei.relatedItem:References` : https://hal.science/hal-04128090v1
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04807540
  - `swhid_from_software_deposit` ← `software:hal-04807540.swhidId_s` : swh:1:rev:0ca5a450c3ba350eb2bb413a7b1fcdc7aa2a293b
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04128090
  - `swhid_from_software_deposit` ← `software:hal-04128090.swhidId_s` : swh:1:dir:8ea716c0d9e69527a5f50378bf135c5952b1a229;origin=https://github.com/frmichel/morph-xr2rml;visit=swh:1:snp:1a5ab65813d598dd4d7353a5f982f7a815e9537c;anchor=swh:1:rev:04f1cd7c5db406bccdb92c29d9fc74bf61a3813c
- Dépôts SOFTWARE :
  - [hal-04807540](https://hal.science/hal-04807540v1) — ISSA Pipeline
  - [hal-04128090](https://hal.science/hal-04128090v1) — Morph-xR2RML: MongoDB-to-RDF translation

---
Fichiers : `publications_with_dataset_and_software.csv` / `.jsonl`.

