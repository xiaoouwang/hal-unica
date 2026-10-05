# Open science triptych — UNIV-COTEDAZUR

**4** candidate(s) — 2026-10-05T11:35:28Z.

## Detection hubs

1. **Publication** — scholarly notice with dataset + software associations (`relatedData_s` / `relatedSoftware_s` / TEI / SOFTWARE backlinks).

2. **Software** — `SOFTWARE` deposit with `relatedPublication_s` + `relatedData_s` (DOI→HAL when needed).

3. **Dataset notice** — dataset-like deposit (often `OTHER`) with `relatedPublication_s` + `relatedSoftware_s` (notice itself = data pillar).


## hal-05700643 — Are you Talking Logic to Me? Assessing Language Models Syllogistic Reasoning Capabilities

- Hubs: `dataset`
- Match: `dataset_hub:relatedPublication+relatedSoftware`
- Publication: https://hal.science/hal-05700643v1
- Datasets (1):
  - `hal-05709317` ← `dataset_notice:hal-05709317.self`
- Software (2):
  - `relatedSoftware_s` ← `dataset_notice:hal-05709317.relatedSoftware_s` : hal-05608340
  - `tei_relatedItem_software` ← `dataset_notice:hal-05709317.tei.relatedItem:Cites` : https://hal.science/hal-05608340
- Dataset notices:
  - [hal-05709317](https://hal.science/hal-05709317v1) — Logic in the Era of Artificial Intelligence: Common Logic Grammar Construction Framework

## hal-04162960 — airGRdatasets: Hydro-Meteorological Catchments Datasets for the 'airGR' Packages. Manual of the R package version 0.2.3

- Hubs: `publication`
- Match: `publication_hub:relatedData+software_signals`
- Publication: https://hal.inrae.fr/hal-04162960v4
- Datasets (1):
  - `10.57745/3SPJ4B` ← `publication.relatedData_s`
- Software (2):
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04481411
  - `swhid_from_software_deposit` ← `software:hal-04481411.swhidId_s` : swh:1:dir:b047cd45ee4f9346a6fa7338c8d7ec230825143d;origin=https://cran.r-project.org/package%253DairGRdatasets;visit=swh:1:snp:c09c87412da9be257d813ea1173036ec6181d5d3;anchor=swh:1:rel:a68ddd145c52c5f9de5771dde91cecd942aecee9;path=/airGRdatasets/

## hal-04208050 — airGRteaching: an open-source tool for teaching hydrological modeling with R

- Hubs: `publication`
- Match: `publication_hub:relatedData+relatedSoftware`
- Publication: https://hal.inrae.fr/hal-04208050v1
- Datasets (2):
  - `10.32614/CRAN.package.airGRdatasets` ← `publication.relatedData_s`
  - `10.32614/CRAN.package.airGRteaching` ← `publication.relatedData_s`
- Software (4):
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : swh:1:dir:3ddc33933e5818871e5d5dfc5aeb3f857c40f8b1;origin=https://cran.r-project.org/package%253DairGRteaching;visit=swh:1:snp:cb9adfa360a7cb140bd65ef48c34fd0ee076a7e1;anchor=swh:1:rel:ba15b1b00733887709ff37c99460cdaf6773e3dc;path=/airGRteaching/
  - `tei_relatedItem_software` ← `publication.tei.relatedItem:IsSupplementedBy` : https://archive.softwareheritage.org/swh:1:dir:3ddc33933e5818871e5d5dfc5aeb3f857c40f8b1;origin=https://cran.r-project.org/package%253DairGRteaching;visit=swh:1:snp:cb9adfa360a7cb140bd65ef48c34fd0ee076a7e1;anchor=swh:1:rel:ba15b1b00733887709ff37c99460cdaf6773e3dc;path=/airGRteaching/
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04412872
  - `swhid_from_software_deposit` ← `software:hal-04412872.swhidId_s` : swh:1:dir:6e59bda8283ea05228d81c884933d1df7e9574d1;origin=https://cran.r-project.org/package%253DairGRteaching;visit=swh:1:snp:c2eccf233a8b854f85cc5c72a5f7527eb954ae5b;anchor=swh:1:rel:7e8c0045edeb6f8e72495e4b334e4daa187a948d;path=/airGRteaching/

## hal-03807744 — ISSA: Generic Pipeline, Knowledge Model and Visualization tools to Help Scientists Search and Make Sense of a Scientific Archive

- Hubs: `publication`, `software`
- Match: `publication_hub:relatedData+software_signals|software_hub:relatedPublication+relatedData`
- Publication: https://hal.science/hal-03807744v1
- Datasets (1):
  - `10.5281/zenodo.10381606` ← `software:hal-04807540.relatedData_s`
- Software (6):
  - `relatedSoftware_s` ← `publication.relatedSoftware_s` : hal-04128090
  - `tei_relatedItem_software` ← `publication.tei.relatedItem:References` : https://hal.science/hal-04128090v1
  - `software_deposit_relatedPublication` ← `software.relatedPublication_s` : hal-04807540
  - `swhid_from_software_deposit` ← `software:hal-04807540.swhidId_s` : swh:1:rev:0ca5a450c3ba350eb2bb413a7b1fcdc7aa2a293b
  - `swhid_from_software_deposit` ← `software:hal-04128090.swhidId_s` : swh:1:dir:8ea716c0d9e69527a5f50378bf135c5952b1a229;origin=https://github.com/frmichel/morph-xr2rml;visit=swh:1:snp:1a5ab65813d598dd4d7353a5f982f7a815e9537c;anchor=swh:1:rev:04f1cd7c5db406bccdb92c29d9fc74bf61a3813c
  - `softCodeRepository_s` ← `software:hal-04807540.softCodeRepository_s` : https://github.com/issa-project/issa-pipeline

---
Files: `publications_with_dataset_and_software.csv` / `.jsonl`.

