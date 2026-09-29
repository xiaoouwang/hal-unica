"""Find HAL publications that link both a dataset and software.

HAL exposes typed associated-resource fields (CCSD, 2025):

- ``relatedData_s`` — identifiers typed as datasets
- ``relatedSoftware_s`` — identifiers typed as software (often SWHIDs)
- ``relatedPublication_s`` — other publications

The public notice also stores structured TEI ``<relatedItem>`` nodes with a
DataCite relation ``type`` (e.g. IsSupplementedBy, Cites) and a COAR
``subtype`` (dataset ``c_ddb1``, software ``c_5ce6``). Prefer those typed
signals over DOI-resolution heuristics.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .client import HalClient
from .universities import University, get_university

# COAR resource types used by HAL relatedItem/@subtype
COAR_DATASET = "http://purl.org/coar/resource_type/c_ddb1"
COAR_SOFTWARE = "http://purl.org/coar/resource_type/c_5ce6"

TRIPLET_FL = [
    "halId_s",
    "uri_s",
    "title_s",
    "docType_s",
    "doiId_s",
    "producedDateY_i",
    "structAcronym_s",
    "relatedData_s",
    "relatedSoftware_s",
    "relatedPublication_s",
    "seeAlso_s",
    "swhidId_s",
    "softCodeRepository_s",
    "label_xml",
]

RELATED_ITEM_RE = re.compile(r"<relatedItem\b([^>]*)/?>", re.I)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
HAL_ID_RE = re.compile(
    r"(?:https?://(?:hal\.[\w.-]+)/)?("
    r"(?:hal|tel|med|inserm|pasteur|ineris|ird|univ|uca|sde|emse|cel|"
    r"dumas|memsic|archivesic|hprints|inria|cnrs|cea)-[a-z0-9]+)",
    re.I,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None and str(x).strip()]
    text = str(value).strip()
    return [text] if text else []


def _flat_title(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _norm_hal(token: str) -> str | None:
    m = HAL_ID_RE.search(str(token or ""))
    if not m:
        if re.fullmatch(r"[a-z]+-\d+", str(token).strip(), re.I):
            return str(token).strip().lower()
        return None
    return re.sub(r"v\d+$", "", m.group(1), flags=re.I).lower()


def parse_related_items_tei(xml: str | None) -> list[dict[str, str]]:
    """Parse TEI ``relatedItem`` nodes → target, relation type, COAR subtype."""
    if not xml:
        return []
    out: list[dict[str, str]] = []
    for m in RELATED_ITEM_RE.finditer(xml):
        attrs = dict(ATTR_RE.findall(m.group(1)))
        target = (attrs.get("target") or "").strip()
        if not target:
            continue
        subtype = (attrs.get("subtype") or "").strip()
        rel = (attrs.get("type") or "").strip()
        if subtype == COAR_SOFTWARE or "softwareheritage" in target.lower() or target.lower().startswith("swh:"):
            kind = "software"
        elif subtype == COAR_DATASET:
            kind = "dataset"
        else:
            kind = "other"
        out.append(
            {
                "target": target,
                "relation": rel,
                "coar_subtype": subtype,
                "kind": kind,
            }
        )
    return out


def coar_kind_label(kind: str) -> str:
    return {"dataset": "Dataset", "software": "Software"}.get(kind, kind)


@dataclass
class TripletResult:
    university_id: str
    collection: str
    started_at: str
    finished_at: str = ""
    rows: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""


def _software_signals_from_doc(doc: dict[str, Any]) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for raw in _as_list(doc.get("relatedSoftware_s")):
        signals.append(
            {
                "kind": "relatedSoftware_s",
                "value": raw,
                "source": "publication.relatedSoftware_s",
            }
        )
    for raw in _as_list(doc.get("swhidId_s")):
        signals.append(
            {
                "kind": "swhidId_s",
                "value": raw,
                "source": "publication.swhidId_s",
            }
        )
    for raw in _as_list(doc.get("softCodeRepository_s")):
        signals.append(
            {
                "kind": "softCodeRepository_s",
                "value": raw,
                "source": "publication.softCodeRepository_s",
            }
        )
    for item in parse_related_items_tei(doc.get("label_xml")):
        if item["kind"] != "software":
            continue
        signals.append(
            {
                "kind": "tei_relatedItem_software",
                "value": item["target"],
                "source": f"tei.relatedItem:{item['relation'] or 'unknown'}",
                "relation": item["relation"],
                "coar_subtype": item["coar_subtype"],
            }
        )
    # Dedupe
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for s in signals:
        key = (s["kind"], s["value"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _datasets_from_doc(doc: dict[str, Any]) -> list[dict[str, str]]:
    datasets: list[dict[str, str]] = []
    tei_items = parse_related_items_tei(doc.get("label_xml"))
    tei_by_target = {i["target"].rstrip("/").lower(): i for i in tei_items}

    for raw in _as_list(doc.get("relatedData_s")):
        target_keys = [
            raw.lower(),
            f"https://doi.org/{raw}".lower() if raw.lower().startswith("10.") else "",
        ]
        tei = None
        for k in target_keys:
            if k and k in tei_by_target:
                tei = tei_by_target[k]
                break
            # fuzzy: doi in tei target
            for tk, item in tei_by_target.items():
                if raw.lower() in tk:
                    tei = item
                    break
            if tei:
                break
        # If TEI explicitly marks this relatedData token as software, skip as dataset
        if tei and tei["kind"] == "software":
            continue
        entry = {
            "value": raw,
            "source": "publication.relatedData_s",
            "kind": "dataset",
        }
        if tei:
            entry["relation"] = tei["relation"]
            entry["coar_subtype"] = tei["coar_subtype"]
            entry["tei_kind"] = tei["kind"]
        datasets.append(entry)

    # TEI-only dataset items not already listed
    seen = {d["value"].lower() for d in datasets}
    for item in tei_items:
        if item["kind"] != "dataset":
            continue
        # Prefer identifier form
        val = item["target"]
        if val.lower() in seen or any(val.lower().endswith(s) or s in val.lower() for s in seen):
            continue
        datasets.append(
            {
                "value": val,
                "source": f"tei.relatedItem:{item['relation'] or 'unknown'}",
                "kind": "dataset",
                "relation": item["relation"],
                "coar_subtype": item["coar_subtype"],
                "tei_kind": "dataset",
            }
        )
        seen.add(val.lower())
    return datasets


def _load_software_backlinks(census_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Map publication HAL id → SOFTWARE deposits that cite it."""
    path = census_dir / "software_deposits.jsonl"
    out: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            for tok in row.get("relatedPublication_s") or []:
                hid = _norm_hal(str(tok))
                if not hid:
                    continue
                out.setdefault(hid, []).append(row)
    return out


def find_publication_dataset_software(
    *,
    university: University | None = None,
    client: HalClient | None = None,
    include_software_deposit_backlinks: bool = True,
    require_typed_software_field: bool = False,
) -> TripletResult:
    """
    List non-SOFTWARE notices with both dataset and software associations.

    Primary signals (HAL typed metadata):
      - datasets: ``relatedData_s`` (+ TEI relatedItem COAR dataset)
      - software: ``relatedSoftware_s`` (+ TEI relatedItem COAR software,
        ``swhidId_s``, ``softCodeRepository_s``)

    Optional: SOFTWARE deposits that point at the publication via
    ``relatedPublication_s`` (and may carry ``relatedData_s`` themselves).
    """
    uni = university or get_university()
    started = _utc_now()
    owns = client is None
    hal = client or HalClient()

    # Broad candidate pool: any typed data or software association
    q = (
        f"collCode_s:{uni.collection} AND ("
        "relatedData_s:* OR relatedSoftware_s:* OR swhidId_s:* OR softCodeRepository_s:*"
        ")"
    )
    result = TripletResult(
        university_id=uni.id,
        collection=uni.collection,
        started_at=started,
        query=q,
    )

    try:
        docs = list(hal.iter_docs(q=q, fl=TRIPLET_FL, rows=200))

        soft_backlinks = (
            _load_software_backlinks(uni.census_dir)
            if include_software_deposit_backlinks
            else {}
        )

        # Index HAL docs; also fetch pubs cited by SOFTWARE deposits that have
        # relatedData (they may lack relatedData_s / relatedSoftware_s on the pub).
        by_hal: dict[str, dict[str, Any]] = {}
        for doc in docs:
            hid = (doc.get("halId_s") or "").lower()
            if hid:
                by_hal[hid] = doc

        if include_software_deposit_backlinks:
            need_fetch: list[str] = []
            for hid, softs in soft_backlinks.items():
                if hid in by_hal:
                    continue
                if any(s.get("relatedData_s") for s in softs):
                    need_fetch.append(hid)
            for i in range(0, len(need_fetch), 20):
                chunk = need_fetch[i : i + 20]
                or_q = " OR ".join(f'halId_s:"{h}"' for h in chunk)
                for doc in hal.iter_docs(q=f"({or_q})", fl=TRIPLET_FL, rows=len(chunk)):
                    hid = (doc.get("halId_s") or "").lower()
                    if hid:
                        by_hal[hid] = doc
    finally:
        if owns:
            close = getattr(hal, "close", None)
            if callable(close):
                close()

    rows: list[dict[str, Any]] = []
    for hid, doc in sorted(by_hal.items()):
        if doc.get("docType_s") == "SOFTWARE":
            continue

        datasets = _datasets_from_doc(doc)
        soft_signals = _software_signals_from_doc(doc)

        linked_soft = soft_backlinks.get(hid) or []
        # Deduplicate SOFTWARE deposits
        uniq_soft: dict[str, dict[str, Any]] = {}
        for s in linked_soft:
            sid = s.get("halId_s")
            if sid:
                uniq_soft[sid] = s
        linked_soft = list(uniq_soft.values())

        for s in linked_soft:
            soft_signals.append(
                {
                    "kind": "software_deposit_relatedPublication",
                    "value": s["halId_s"],
                    "source": "software.relatedPublication_s",
                }
            )
            for raw in s.get("relatedData_s") or []:
                datasets.append(
                    {
                        "value": str(raw),
                        "source": f"software:{s['halId_s']}.relatedData_s",
                        "kind": "dataset",
                    }
                )
            for raw in s.get("swhidId_s") or []:
                soft_signals.append(
                    {
                        "kind": "swhid_from_software_deposit",
                        "value": str(raw),
                        "source": f"software:{s['halId_s']}.swhidId_s",
                    }
                )

        # Dedup datasets / signals
        ds_out: list[dict[str, str]] = []
        seen_d: set[str] = set()
        for d in datasets:
            key = d["value"].lower()
            if key in seen_d:
                continue
            seen_d.add(key)
            ds_out.append(d)
        sig_out: list[dict[str, str]] = []
        seen_s: set[tuple[str, str]] = set()
        for s in soft_signals:
            key = (s["kind"], s["value"].lower())
            if key in seen_s:
                continue
            seen_s.add(key)
            sig_out.append(s)

        if not ds_out or not sig_out:
            continue
        if require_typed_software_field and not _as_list(doc.get("relatedSoftware_s")):
            # Still allow TEI software relatedItem
            if not any(s["kind"] == "tei_relatedItem_software" for s in sig_out):
                if not any(s["kind"] == "relatedSoftware_s" for s in sig_out):
                    continue

        has_typed_data = bool(_as_list(doc.get("relatedData_s")))
        has_typed_soft = bool(_as_list(doc.get("relatedSoftware_s")))
        rows.append(
            {
                "publication_halId": hid,
                "publication_uri": doc.get("uri_s") or f"https://hal.science/{hid}",
                "publication_title": _flat_title(doc.get("title_s")),
                "publication_doi": (
                    doc.get("doiId_s")[0]
                    if isinstance(doc.get("doiId_s"), list) and doc.get("doiId_s")
                    else doc.get("doiId_s")
                ),
                "publication_docType": doc.get("docType_s"),
                "publication_year": doc.get("producedDateY_i"),
                "laboratories": _as_list(doc.get("structAcronym_s")),
                "relatedData_s": _as_list(doc.get("relatedData_s")),
                "relatedSoftware_s": _as_list(doc.get("relatedSoftware_s")),
                "relatedPublication_s": _as_list(doc.get("relatedPublication_s")),
                "seeAlso_s": _as_list(doc.get("seeAlso_s")),
                "swhidId_s": _as_list(doc.get("swhidId_s")),
                "n_datasets": len(ds_out),
                "datasets": ds_out,
                "dataset_values": [d["value"] for d in ds_out],
                "n_software_signals": len(sig_out),
                "software_signals": sig_out,
                "software_halIds": [s["halId_s"] for s in linked_soft],
                "software_uris": [s.get("uri_s") for s in linked_soft],
                "software_titles": [_flat_title(s.get("title_s")) for s in linked_soft],
                "has_typed_relatedData": has_typed_data,
                "has_typed_relatedSoftware": has_typed_soft,
                "match_basis": (
                    "relatedData_s+relatedSoftware_s"
                    if has_typed_data and has_typed_soft
                    else (
                        "relatedData_s+software_signals"
                        if has_typed_data
                        else "mixed_or_software_deposit"
                    )
                ),
            }
        )

    rows.sort(
        key=lambda r: (-(r.get("publication_year") or 0), r["publication_halId"])
    )
    result.rows = rows
    result.finished_at = _utc_now()
    return result


def write_triplet_artifacts(
    result: TripletResult,
    census_dir: Path,
) -> dict[str, Path]:
    census_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = census_dir / "publications_with_dataset_and_software.jsonl"
    csv_path = census_dir / "publications_with_dataset_and_software.csv"
    md_path = census_dir / "publications_with_dataset_and_software.md"
    summary_path = census_dir / "publications_with_dataset_and_software_summary.json"

    with jsonl_path.open("w", encoding="utf-8") as fh:
        for row in result.rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
        "publication_halId",
        "publication_uri",
        "publication_title",
        "publication_doi",
        "publication_docType",
        "publication_year",
        "laboratories",
        "relatedData_s",
        "relatedSoftware_s",
        "n_datasets",
        "dataset_values",
        "n_software_signals",
        "software_signal_kinds",
        "software_signal_values",
        "software_signal_sources",
        "software_halIds",
        "software_titles",
        "has_typed_relatedData",
        "has_typed_relatedSoftware",
        "match_basis",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in result.rows:
            sigs = r.get("software_signals") or []
            w.writerow(
                {
                    "publication_halId": r["publication_halId"],
                    "publication_uri": r["publication_uri"],
                    "publication_title": r["publication_title"],
                    "publication_doi": r.get("publication_doi") or "",
                    "publication_docType": r.get("publication_docType") or "",
                    "publication_year": r.get("publication_year") or "",
                    "laboratories": " | ".join(r.get("laboratories") or []),
                    "relatedData_s": " | ".join(r.get("relatedData_s") or []),
                    "relatedSoftware_s": " | ".join(r.get("relatedSoftware_s") or []),
                    "n_datasets": r["n_datasets"],
                    "dataset_values": " | ".join(r.get("dataset_values") or []),
                    "n_software_signals": r["n_software_signals"],
                    "software_signal_kinds": " | ".join(s["kind"] for s in sigs),
                    "software_signal_values": " | ".join(str(s["value"]) for s in sigs),
                    "software_signal_sources": " | ".join(s["source"] for s in sigs),
                    "software_halIds": " | ".join(r.get("software_halIds") or []),
                    "software_titles": " | ".join(r.get("software_titles") or []),
                    "has_typed_relatedData": r.get("has_typed_relatedData"),
                    "has_typed_relatedSoftware": r.get("has_typed_relatedSoftware"),
                    "match_basis": r.get("match_basis") or "",
                }
            )

    md = [
        f"# Publications {result.collection} : publi + jeu de données + software\n",
        f"**{len(result.rows)}** notice(s) — généré {result.finished_at}.\n",
        "## Méthode (métadonnées HAL typées)\n",
        "HAL expose des champs d’API distincts pour les ressources associées "
        "([CCSD, 2025](https://www.ccsd.cnrs.fr/en/2025/02/enhance-the-link-between-your-hal-deposit-and-a-dataset-or-software-a-new-feature-to-increase-the-visibility-of-your-research/)) :\n",
        "- `relatedData_s` — jeux de données\n",
        "- `relatedSoftware_s` — logiciels / codes (souvent SWHID)\n",
        "- `relatedPublication_s` — autres publications\n",
        "\nLe TEI du dépôt précise aussi chaque lien via `<relatedItem type=\"…\" "
        "subtype=\"COAR\">` (ex. Dataset `c_ddb1`, Software `c_5ce6`).\n",
        "\nOn ne se fie **pas** uniquement à la résolution DataCite d’un DOI : "
        "le typage HAL / COAR prime.\n",
        "\nSignaux software acceptés en complément : `swhidId_s`, "
        "`softCodeRepository_s`, dépôt HAL `SOFTWARE` lié par "
        "`relatedPublication_s`.\n",
    ]
    for r in result.rows:
        md.append(f"\n## {r['publication_halId']} — {r['publication_title']}\n")
        md.append(
            f"- Type / année : `{r.get('publication_docType')}` / {r.get('publication_year')}"
        )
        md.append(f"- URL : {r['publication_uri']}")
        if r.get("publication_doi"):
            md.append(f"- DOI : `{r['publication_doi']}`")
        md.append(f"- Base : `{r.get('match_basis')}`")
        md.append(
            f"- Champs typés : relatedData={r.get('has_typed_relatedData')} · "
            f"relatedSoftware={r.get('has_typed_relatedSoftware')}"
        )
        md.append(
            f"- `relatedData_s` : "
            + (", ".join(f"`{x}`" for x in (r.get("relatedData_s") or [])) or "—")
        )
        md.append(
            f"- `relatedSoftware_s` : "
            + (", ".join(f"`{x}`" for x in (r.get("relatedSoftware_s") or [])) or "—")
        )
        md.append(f"- Jeux de données ({r['n_datasets']}) :")
        for d in r.get("datasets") or []:
            rel = d.get("relation")
            extra = f" · {rel}" if rel else ""
            md.append(f"  - `{d['value']}` ← `{d['source']}`{extra}")
        md.append(f"- Signaux software ({r['n_software_signals']}) :")
        for s in r.get("software_signals") or []:
            md.append(f"  - `{s['kind']}` ← `{s['source']}` : {s['value']}")
        if r.get("software_halIds"):
            md.append("- Dépôts SOFTWARE :")
            for sid, suri, st in zip(
                r["software_halIds"], r["software_uris"], r["software_titles"]
            ):
                md.append(f"  - [{sid}]({suri}) — {st}")
    md.append(
        "\n---\nFichiers : `publications_with_dataset_and_software.csv` / `.jsonl`.\n"
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    summary = {
        "university_id": result.university_id,
        "collection": result.collection,
        "query": result.query,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "publications": len(result.rows),
        "with_typed_relatedData_and_relatedSoftware": sum(
            1
            for r in result.rows
            if r.get("has_typed_relatedData") and r.get("has_typed_relatedSoftware")
        ),
        "by_match_basis": dict(Counter(r.get("match_basis") for r in result.rows)),
        "by_docType": dict(Counter(r.get("publication_docType") for r in result.rows)),
        "method": [
            "Prefer HAL typed API fields relatedData_s and relatedSoftware_s.",
            "Enrich from TEI relatedItem (@type DataCite relation, @subtype COAR).",
            "Also accept swhidId_s / softCodeRepository_s and SOFTWARE deposit backlinks.",
            "Do not classify solely by DataCite DOI resolution.",
        ],
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "md": md_path,
        "summary": summary_path,
    }
