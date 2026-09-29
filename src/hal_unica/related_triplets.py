"""Detect open-science triptych candidates: publication + data + software.

HAL typed associated-resource fields (CCSD, 2025):

- ``relatedData_s`` — datasets
- ``relatedSoftware_s`` — software / source code (often SWHID)
- ``relatedPublication_s`` — publications

Three complementary hubs can complete the same triangle:

1. **Publication hub** — a scholarly notice declares both ``relatedData_s`` and
   software (``relatedSoftware_s`` / SWHID / code repo / linked SOFTWARE).
2. **Software hub** — a ``SOFTWARE`` deposit declares both
   ``relatedPublication_s`` and ``relatedData_s``.
3. **Dataset hub** — a dataset-like notice (often ``OTHER``) declares both a
   related publication and related software (the notice itself is the data
   pillar, optionally with ``relatedData_s`` too).

TEI ``<relatedItem type="…" subtype="COAR">`` enriches typing
(dataset ``c_ddb1``, software ``c_5ce6``). DOIs in ``relatedPublication_s``
are resolved to HAL ids when possible.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import HalClient
from .universities import University, get_university

COAR_DATASET = "http://purl.org/coar/resource_type/c_ddb1"
COAR_SOFTWARE = "http://purl.org/coar/resource_type/c_5ce6"

# Notices that often host a dataset description / data product rather than a paper.
DATASET_LIKE_DOC_TYPES = frozenset(
    {
        "OTHER",
        "MAP",
        "IMG",
        "SON",
        "VIDEO",
        "LECTURE",
    }
)

SCHOLARLY_DOC_TYPES = frozenset(
    {
        "ART",
        "COMM",
        "COUV",
        "OUV",
        "DOUV",
        "PROCEEDINGS",
        "ISSUE",
        "POSTER",
        "REPORT",
        "THESE",
        "HDR",
        "MEM",
        "OTHER",  # can also be scholarly; hub logic disambiguates
        "UNDEFINED",
        "BLOG",
    }
)

TRIPLET_FL = [
    "halId_s",
    "uri_s",
    "title_s",
    "docType_s",
    "docSubType_s",
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
DOI_RE = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"'<>\]\),;]+)",
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


def _norm_hal(token: str | None) -> str | None:
    if not token:
        return None
    m = HAL_ID_RE.search(str(token))
    if not m:
        if re.fullmatch(r"[a-z]+-\d+", str(token).strip(), re.I):
            return str(token).strip().lower()
        return None
    return re.sub(r"v\d+$", "", m.group(1), flags=re.I).lower()


def _extract_doi(token: str | None) -> str | None:
    if not token:
        return None
    m = DOI_RE.search(str(token))
    if not m:
        return None
    return m.group(1).rstrip(").,;]").lower()


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
        if (
            subtype == COAR_SOFTWARE
            or "softwareheritage" in target.lower()
            or target.lower().startswith("swh:")
        ):
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


@dataclass
class TripletResult:
    university_id: str
    collection: str
    started_at: str
    finished_at: str = ""
    rows: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""


def _dedupe_signals(signals: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for s in signals:
        key = (s.get("kind") or "", (s.get("value") or "").lower())
        if not key[1] or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _software_signals_from_doc(doc: dict[str, Any], *, source_prefix: str) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for raw in _as_list(doc.get("relatedSoftware_s")):
        signals.append(
            {
                "kind": "relatedSoftware_s",
                "value": raw,
                "source": f"{source_prefix}.relatedSoftware_s",
            }
        )
    for raw in _as_list(doc.get("swhidId_s")):
        signals.append(
            {
                "kind": "swhidId_s",
                "value": raw,
                "source": f"{source_prefix}.swhidId_s",
            }
        )
    for raw in _as_list(doc.get("softCodeRepository_s")):
        signals.append(
            {
                "kind": "softCodeRepository_s",
                "value": raw,
                "source": f"{source_prefix}.softCodeRepository_s",
            }
        )
    for item in parse_related_items_tei(doc.get("label_xml")):
        if item["kind"] != "software":
            continue
        signals.append(
            {
                "kind": "tei_relatedItem_software",
                "value": item["target"],
                "source": f"{source_prefix}.tei.relatedItem:{item['relation'] or 'unknown'}",
                "relation": item["relation"],
                "coar_subtype": item["coar_subtype"],
            }
        )
    return _dedupe_signals(signals)


def _datasets_from_doc(doc: dict[str, Any], *, source_prefix: str) -> list[dict[str, str]]:
    datasets: list[dict[str, str]] = []
    tei_items = parse_related_items_tei(doc.get("label_xml"))

    for raw in _as_list(doc.get("relatedData_s")):
        tei = None
        for item in tei_items:
            if raw.lower() in item["target"].lower():
                tei = item
                break
        if tei and tei["kind"] == "software":
            continue
        entry: dict[str, str] = {
            "value": raw,
            "source": f"{source_prefix}.relatedData_s",
            "kind": "dataset",
        }
        if tei:
            entry["relation"] = tei["relation"]
            entry["coar_subtype"] = tei["coar_subtype"]
            entry["tei_kind"] = tei["kind"]
        datasets.append(entry)

    seen = {d["value"].lower() for d in datasets}
    for item in tei_items:
        if item["kind"] != "dataset":
            continue
        val = item["target"]
        if val.lower() in seen or any(val.lower() in s or s in val.lower() for s in seen):
            continue
        datasets.append(
            {
                "value": val,
                "source": f"{source_prefix}.tei.relatedItem:{item['relation'] or 'unknown'}",
                "kind": "dataset",
                "relation": item["relation"],
                "coar_subtype": item["coar_subtype"],
                "tei_kind": "dataset",
            }
        )
        seen.add(val.lower())
    return datasets


def _doc_brief(doc: dict[str, Any] | None, *, fallback_id: str | None = None) -> dict[str, Any]:
    if not doc:
        hid = fallback_id or ""
        return {
            "halId_s": hid,
            "uri_s": f"https://hal.science/{hid}" if hid else None,
            "title_s": None,
            "docType_s": None,
            "doiId_s": None,
            "producedDateY_i": None,
            "laboratories": [],
        }
    doi = doc.get("doiId_s")
    if isinstance(doi, list):
        doi = doi[0] if doi else None
    hid = (doc.get("halId_s") or fallback_id or "").lower()
    return {
        "halId_s": hid,
        "uri_s": doc.get("uri_s") or (f"https://hal.science/{hid}" if hid else None),
        "title_s": _flat_title(doc.get("title_s")),
        "docType_s": doc.get("docType_s"),
        "docSubType_s": doc.get("docSubType_s"),
        "doiId_s": doi,
        "producedDateY_i": doc.get("producedDateY_i"),
        "laboratories": _as_list(doc.get("structAcronym_s")),
    }


def _is_dataset_like(doc: dict[str, Any]) -> bool:
    dtype = doc.get("docType_s") or ""
    subtype = str(doc.get("docSubType_s") or "").upper()
    if dtype in DATASET_LIKE_DOC_TYPES:
        return True
    if subtype in {"DATAPAPER", "DATA", "DATASET"}:
        return True
    return False


def _merge_candidate(
    store: dict[str, dict[str, Any]],
    *,
    key: str,
    hubs: list[str],
    publication: dict[str, Any],
    datasets: list[dict[str, str]],
    software_signals: list[dict[str, str]],
    software_deposits: list[dict[str, Any]],
    dataset_notices: list[dict[str, Any]],
    match_basis: str,
) -> None:
    if key not in store:
        store[key] = {
            "candidate_key": key,
            "hubs": [],
            "publication": publication,
            "datasets": [],
            "software_signals": [],
            "software_deposits": [],
            "dataset_notices": [],
            "match_bases": [],
        }
    row = store[key]
    for h in hubs:
        if h not in row["hubs"]:
            row["hubs"].append(h)
    if match_basis and match_basis not in row["match_bases"]:
        row["match_bases"].append(match_basis)

    # Prefer richer publication metadata
    cur = row["publication"] or {}
    if publication.get("title_s") and not cur.get("title_s"):
        row["publication"] = publication
    elif publication.get("doiId_s") and not cur.get("doiId_s"):
        row["publication"] = {**cur, **{k: v for k, v in publication.items() if v}}

    def _extend(bucket: str, items: list[dict[str, Any]], id_key: str = "value") -> None:
        seen = {
            str(x.get(id_key) or x.get("halId_s") or "").lower()
            for x in row[bucket]
        }
        for item in items:
            ident = str(item.get(id_key) or item.get("halId_s") or "").lower()
            if not ident or ident in seen:
                continue
            seen.add(ident)
            row[bucket].append(item)

    _extend("datasets", datasets, "value")
    _extend("software_signals", software_signals, "value")
    _extend("software_deposits", software_deposits, "halId_s")
    _extend("dataset_notices", dataset_notices, "halId_s")


def _batch_fetch(hal: HalClient, ids: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    uniq = sorted({i.lower() for i in ids if i})
    for i in range(0, len(uniq), 20):
        chunk = uniq[i : i + 20]
        or_q = " OR ".join(f'halId_s:"{h}"' for h in chunk)
        for doc in hal.iter_docs(q=f"({or_q})", fl=TRIPLET_FL, rows=len(chunk)):
            hid = (doc.get("halId_s") or "").lower()
            if hid:
                out[hid] = doc
    return out


def _build_doi_index(docs: list[dict[str, Any]], census_dir: Path) -> dict[str, str]:
    """Map lowercase DOI → HAL id."""
    doi_to_hal: dict[str, str] = {}
    for doc in docs:
        hid = (doc.get("halId_s") or "").lower()
        doi = doc.get("doiId_s")
        if isinstance(doi, list):
            doi = doi[0] if doi else None
        if hid and doi:
            doi_to_hal[str(doi).lower()] = hid

    # Harvest metadata (broader DOI coverage)
    for name in (
        "unica_hal_metadata.jsonl",
        "ube_hal_metadata.jsonl",
    ):
        # Prefer tenant harvest next to census parent
        pass
    harvest_candidates = [
        census_dir.parent / "unica_hal_metadata.jsonl",
        census_dir.parent / "ube_hal_metadata.jsonl",
        Path("data/unica_hal_metadata.jsonl"),
        Path("data/ube/ube_hal_metadata.jsonl"),
        Path("data/ube_hal_metadata.jsonl"),
    ]
    uni = get_university()
    if uni.id == "ube":
        harvest_candidates.insert(0, Path("data/ube") / "ube_hal_metadata.jsonl")
        harvest_candidates.insert(0, uni.census_dir.parent / "hal_metadata.jsonl")
    # universities may store harvest at uni.harvest_path if available
    harvest_path = getattr(uni, "harvest_path", None)
    if harvest_path:
        harvest_candidates.insert(0, Path(harvest_path))

    for path in harvest_candidates:
        if not path or not Path(path).exists():
            continue
        with Path(path).open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hid = (row.get("halId_s") or "").lower()
                doi = row.get("doiId_s")
                if isinstance(doi, list):
                    doi = doi[0] if doi else None
                if hid and doi:
                    doi_to_hal.setdefault(str(doi).lower(), hid)
        break
    return doi_to_hal


def _resolve_publication_refs(
    tokens: list[str],
    *,
    doi_to_hal: dict[str, str],
) -> list[str]:
    """Return HAL ids from relatedPublication tokens (HAL id or DOI)."""
    out: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        hid = _norm_hal(tok)
        if not hid:
            doi = _extract_doi(tok)
            if doi:
                hid = doi_to_hal.get(doi)
        if hid and hid not in seen:
            seen.add(hid)
            out.append(hid)
    return out


def find_publication_dataset_software(
    *,
    university: University | None = None,
    client: HalClient | None = None,
    include_software_deposit_backlinks: bool = True,
    require_typed_software_field: bool = False,
) -> TripletResult:
    """
    Find triptych candidates via publication, software, and dataset hubs.

    ``require_typed_software_field`` keeps only rows that have ``relatedSoftware_s``
    or a TEI COAR software relatedItem (stricter mode for audits).
    """
    uni = university or get_university()
    started = _utc_now()
    owns = client is None
    # Collection already scopes the client endpoint; keep q without collCode.
    hal = client or HalClient(collection=uni.collection)

    q = (
        "relatedData_s:* OR relatedSoftware_s:* OR relatedPublication_s:* OR "
        "swhidId_s:* OR softCodeRepository_s:* OR docType_s:SOFTWARE"
    )
    result = TripletResult(
        university_id=uni.id,
        collection=uni.collection,
        started_at=started,
        query=q,
    )

    try:
        docs = list(hal.iter_docs(q=q, fl=TRIPLET_FL, rows=200))
        by_hal: dict[str, dict[str, Any]] = {
            (d.get("halId_s") or "").lower(): d
            for d in docs
            if d.get("halId_s")
        }

        # Load local SOFTWARE deposits (richer related* than a partial API page)
        soft_rows: list[dict[str, Any]] = []
        soft_path = uni.census_dir / "software_deposits.jsonl"
        if soft_path.exists():
            with soft_path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        soft_rows.append(json.loads(line))
        soft_by_hal = {
            (s.get("halId_s") or "").lower(): s for s in soft_rows if s.get("halId_s")
        }
        # Ensure SOFTWARE docs from API are present even if census file is stale
        for hid, doc in by_hal.items():
            if doc.get("docType_s") == "SOFTWARE" and hid not in soft_by_hal:
                soft_by_hal[hid] = {
                    "halId_s": hid,
                    "uri_s": doc.get("uri_s"),
                    "title_s": _flat_title(doc.get("title_s")),
                    "relatedPublication_s": _as_list(doc.get("relatedPublication_s")),
                    "relatedData_s": _as_list(doc.get("relatedData_s")),
                    "relatedSoftware_s": _as_list(doc.get("relatedSoftware_s")),
                    "swhidId_s": _as_list(doc.get("swhidId_s")),
                    "softCodeRepository_s": _as_list(doc.get("softCodeRepository_s")),
                    "docType_s": "SOFTWARE",
                }

        doi_to_hal = _build_doi_index(list(by_hal.values()) + list(soft_by_hal.values()), uni.census_dir)

        # Prefetch publications referenced by SOFTWARE / dataset hubs
        need: list[str] = []
        for s in soft_by_hal.values():
            need.extend(
                _resolve_publication_refs(
                    _as_list(s.get("relatedPublication_s")),
                    doi_to_hal=doi_to_hal,
                )
            )
        for doc in by_hal.values():
            if _is_dataset_like(doc) or (
                doc.get("docType_s") != "SOFTWARE"
                and _as_list(doc.get("relatedPublication_s"))
                and _as_list(doc.get("relatedSoftware_s"))
            ):
                need.extend(
                    _resolve_publication_refs(
                        _as_list(doc.get("relatedPublication_s")),
                        doi_to_hal=doi_to_hal,
                    )
                )
        missing = [h for h in need if h not in by_hal]
        if missing:
            by_hal.update(_batch_fetch(hal, missing))
            # Refresh DOI index with newly fetched pubs
            for hid, doc in by_hal.items():
                doi = doc.get("doiId_s")
                if isinstance(doi, list):
                    doi = doi[0] if doi else None
                if doi:
                    doi_to_hal.setdefault(str(doi).lower(), hid)

        candidates: dict[str, dict[str, Any]] = {}

        # ---- Hub 1: publication ----
        for hid, doc in by_hal.items():
            if doc.get("docType_s") == "SOFTWARE":
                continue
            datasets = _datasets_from_doc(doc, source_prefix="publication")
            soft_signals = _software_signals_from_doc(doc, source_prefix="publication")

            linked_soft: list[dict[str, Any]] = []
            if include_software_deposit_backlinks:
                for s in soft_by_hal.values():
                    pubs = _resolve_publication_refs(
                        _as_list(s.get("relatedPublication_s")),
                        doi_to_hal=doi_to_hal,
                    )
                    if hid not in pubs:
                        continue
                    linked_soft.append(s)
                    soft_signals.append(
                        {
                            "kind": "software_deposit_relatedPublication",
                            "value": s["halId_s"],
                            "source": "software.relatedPublication_s",
                        }
                    )
                    for raw in _as_list(s.get("relatedData_s")):
                        datasets.append(
                            {
                                "value": raw,
                                "source": f"software:{s['halId_s']}.relatedData_s",
                                "kind": "dataset",
                            }
                        )
                    for raw in _as_list(s.get("swhidId_s")):
                        soft_signals.append(
                            {
                                "kind": "swhid_from_software_deposit",
                                "value": raw,
                                "source": f"software:{s['halId_s']}.swhidId_s",
                            }
                        )

            datasets = _dedupe_signals(datasets)
            soft_signals = _dedupe_signals(soft_signals)
            if not datasets or not soft_signals:
                continue
            if require_typed_software_field and not (
                _as_list(doc.get("relatedSoftware_s"))
                or any(s["kind"] == "tei_relatedItem_software" for s in soft_signals)
            ):
                continue

            has_typed_data = bool(_as_list(doc.get("relatedData_s")))
            has_typed_soft = bool(_as_list(doc.get("relatedSoftware_s")))
            basis = (
                "publication_hub:relatedData+relatedSoftware"
                if has_typed_data and has_typed_soft
                else "publication_hub:relatedData+software_signals"
            )
            _merge_candidate(
                candidates,
                key=f"pub:{hid}",
                hubs=["publication"],
                publication=_doc_brief(doc),
                datasets=datasets,
                software_signals=soft_signals,
                software_deposits=[_doc_brief(by_hal.get(s["halId_s"].lower()), fallback_id=s["halId_s"]) | {"title_s": _flat_title(s.get("title_s"))} for s in linked_soft],
                dataset_notices=[],
                match_basis=basis,
            )

        # ---- Hub 2: software deposit ----
        for sid, s in soft_by_hal.items():
            data_vals = _as_list(s.get("relatedData_s"))
            pub_ids = _resolve_publication_refs(
                _as_list(s.get("relatedPublication_s")),
                doi_to_hal=doi_to_hal,
            )
            if not data_vals or not pub_ids:
                # Still record unresolved DOI pubs as soft-only notes? skip — incomplete triangle
                continue
            soft_doc = by_hal.get(sid) or s
            soft_signals = _software_signals_from_doc(soft_doc, source_prefix=f"software:{sid}")
            soft_signals.insert(
                0,
                {
                    "kind": "software_deposit",
                    "value": sid,
                    "source": "software.hub",
                },
            )
            soft_signals = _dedupe_signals(soft_signals)
            datasets = [
                {
                    "value": raw,
                    "source": f"software:{sid}.relatedData_s",
                    "kind": "dataset",
                }
                for raw in data_vals
            ]
            for pub_id in pub_ids:
                pub_doc = by_hal.get(pub_id)
                # Merge publication-side relatedData if present
                if pub_doc:
                    datasets = _dedupe_signals(
                        datasets + _datasets_from_doc(pub_doc, source_prefix="publication")
                    )
                    soft_signals = _dedupe_signals(
                        soft_signals
                        + _software_signals_from_doc(pub_doc, source_prefix="publication")
                    )
                _merge_candidate(
                    candidates,
                    key=f"pub:{pub_id}",
                    hubs=["software"],
                    publication=_doc_brief(pub_doc, fallback_id=pub_id),
                    datasets=datasets,
                    software_signals=soft_signals,
                    software_deposits=[
                        _doc_brief(by_hal.get(sid), fallback_id=sid)
                        | {"title_s": _flat_title(s.get("title_s"))}
                    ],
                    dataset_notices=[],
                    match_basis="software_hub:relatedPublication+relatedData",
                )

        # ---- Hub 3: dataset-like notice (OTHER / MAP / …) ----
        # The notice itself is the data pillar: it points to a publication and to
        # software. Do not treat ordinary ART/COMM that merely cite both as
        # dataset hubs — those belong to the publication hub when they also
        # declare relatedData_s.
        for hid, doc in by_hal.items():
            if doc.get("docType_s") == "SOFTWARE":
                continue
            if not _is_dataset_like(doc):
                continue
            pubs = _resolve_publication_refs(
                _as_list(doc.get("relatedPublication_s")),
                doi_to_hal=doi_to_hal,
            )
            soft_signals = _software_signals_from_doc(
                doc, source_prefix=f"dataset_notice:{hid}"
            )
            if not pubs or not soft_signals:
                continue

            datasets = _datasets_from_doc(doc, source_prefix=f"dataset_notice:{hid}")
            # The notice itself is the data product / dataset description
            datasets = _dedupe_signals(
                datasets
                + [
                    {
                        "value": hid,
                        "source": f"dataset_notice:{hid}.self",
                        "kind": "dataset_notice",
                        "label": _flat_title(doc.get("title_s")),
                    }
                ]
            )

            notice_brief = _doc_brief(doc)
            for pub_id in pubs:
                # Avoid treating the notice as its own publication
                if pub_id == hid:
                    continue
                pub_doc = by_hal.get(pub_id)
                merged_datasets = list(datasets)
                merged_soft = list(soft_signals)
                if pub_doc:
                    merged_datasets = _dedupe_signals(
                        merged_datasets
                        + _datasets_from_doc(pub_doc, source_prefix="publication")
                    )
                    merged_soft = _dedupe_signals(
                        merged_soft
                        + _software_signals_from_doc(pub_doc, source_prefix="publication")
                    )
                _merge_candidate(
                    candidates,
                    key=f"pub:{pub_id}",
                    hubs=["dataset"],
                    publication=_doc_brief(pub_doc, fallback_id=pub_id),
                    datasets=merged_datasets,
                    software_signals=merged_soft,
                    software_deposits=[],
                    dataset_notices=[notice_brief],
                    match_basis="dataset_hub:relatedPublication+relatedSoftware",
                )

            # If no resolvable publication HAL id but we have DOI tokens, keep
            # a dataset-anchored candidate so nothing is silently dropped.
            if not pubs and _as_list(doc.get("relatedPublication_s")):
                key = f"dataset:{hid}"
                _merge_candidate(
                    candidates,
                    key=key,
                    hubs=["dataset"],
                    publication={
                        "halId_s": None,
                        "uri_s": None,
                        "title_s": None,
                        "docType_s": None,
                        "doiId_s": _extract_doi(_as_list(doc.get("relatedPublication_s"))[0]),
                        "producedDateY_i": None,
                        "laboratories": [],
                        "unresolved_relatedPublication_s": _as_list(
                            doc.get("relatedPublication_s")
                        ),
                    },
                    datasets=datasets,
                    software_signals=soft_signals,
                    software_deposits=[],
                    dataset_notices=[notice_brief],
                    match_basis="dataset_hub:unresolved_publication_ref",
                )

    finally:
        if owns:
            close = getattr(hal, "close", None)
            if callable(close):
                close()

    rows: list[dict[str, Any]] = []
    for key, raw in candidates.items():
        pub = raw["publication"] or {}
        datasets = raw["datasets"]
        soft_signals = raw["software_signals"]
        if not soft_signals or not datasets:
            continue
        hubs = raw["hubs"]
        rows.append(
            {
                "candidate_key": key,
                "hubs": hubs,
                "primary_hub": hubs[0] if hubs else "unknown",
                "publication_halId": pub.get("halId_s"),
                "publication_uri": pub.get("uri_s"),
                "publication_title": pub.get("title_s"),
                "publication_doi": pub.get("doiId_s"),
                "publication_docType": pub.get("docType_s"),
                "publication_year": pub.get("producedDateY_i"),
                "laboratories": pub.get("laboratories") or [],
                "unresolved_relatedPublication_s": pub.get(
                    "unresolved_relatedPublication_s"
                )
                or [],
                "n_datasets": len(datasets),
                "datasets": datasets,
                "dataset_values": [d.get("value") for d in datasets],
                "n_software_signals": len(soft_signals),
                "software_signals": soft_signals,
                "software_halIds": [
                    d.get("halId_s") for d in raw["software_deposits"] if d.get("halId_s")
                ],
                "software_uris": [d.get("uri_s") for d in raw["software_deposits"]],
                "software_titles": [d.get("title_s") for d in raw["software_deposits"]],
                "software_deposits": raw["software_deposits"],
                "dataset_notices": raw["dataset_notices"],
                "relatedData_s": _as_list(
                    (by_hal.get(pub.get("halId_s") or "") or {}).get("relatedData_s")
                ),
                "relatedSoftware_s": _as_list(
                    (by_hal.get(pub.get("halId_s") or "") or {}).get("relatedSoftware_s")
                ),
                "has_typed_relatedData": bool(
                    _as_list(
                        (by_hal.get(pub.get("halId_s") or "") or {}).get("relatedData_s")
                    )
                ),
                "has_typed_relatedSoftware": bool(
                    _as_list(
                        (by_hal.get(pub.get("halId_s") or "") or {}).get(
                            "relatedSoftware_s"
                        )
                    )
                ),
                "match_basis": "|".join(raw["match_bases"]),
                "match_bases": raw["match_bases"],
            }
        )

    rows.sort(
        key=lambda r: (
            -(r.get("publication_year") or 0),
            r.get("publication_halId") or r.get("candidate_key") or "",
        )
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
        "candidate_key",
        "hubs",
        "primary_hub",
        "publication_halId",
        "publication_uri",
        "publication_title",
        "publication_doi",
        "publication_docType",
        "publication_year",
        "laboratories",
        "n_datasets",
        "dataset_values",
        "n_software_signals",
        "software_signal_kinds",
        "software_signal_values",
        "software_halIds",
        "dataset_notice_ids",
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
                    "candidate_key": r.get("candidate_key"),
                    "hubs": " | ".join(r.get("hubs") or []),
                    "primary_hub": r.get("primary_hub"),
                    "publication_halId": r.get("publication_halId") or "",
                    "publication_uri": r.get("publication_uri") or "",
                    "publication_title": r.get("publication_title") or "",
                    "publication_doi": r.get("publication_doi") or "",
                    "publication_docType": r.get("publication_docType") or "",
                    "publication_year": r.get("publication_year") or "",
                    "laboratories": " | ".join(r.get("laboratories") or []),
                    "n_datasets": r.get("n_datasets"),
                    "dataset_values": " | ".join(
                        str(x) for x in (r.get("dataset_values") or [])
                    ),
                    "n_software_signals": r.get("n_software_signals"),
                    "software_signal_kinds": " | ".join(s.get("kind") or "" for s in sigs),
                    "software_signal_values": " | ".join(
                        str(s.get("value") or "") for s in sigs
                    ),
                    "software_halIds": " | ".join(r.get("software_halIds") or []),
                    "dataset_notice_ids": " | ".join(
                        d.get("halId_s") or ""
                        for d in (r.get("dataset_notices") or [])
                    ),
                    "has_typed_relatedData": r.get("has_typed_relatedData"),
                    "has_typed_relatedSoftware": r.get("has_typed_relatedSoftware"),
                    "match_basis": r.get("match_basis") or "",
                }
            )

    md = [
        f"# Open science triptych — {result.collection}\n",
        f"**{len(result.rows)}** candidate(s) — {result.finished_at}.\n",
        "## Detection hubs\n",
        "1. **Publication** — scholarly notice with dataset + software associations "
        "(`relatedData_s` / `relatedSoftware_s` / TEI / SOFTWARE backlinks).\n",
        "2. **Software** — `SOFTWARE` deposit with `relatedPublication_s` + "
        "`relatedData_s` (DOI→HAL when needed).\n",
        "3. **Dataset notice** — dataset-like deposit (often `OTHER`) with "
        "`relatedPublication_s` + `relatedSoftware_s` (notice itself = data pillar).\n",
    ]
    for r in result.rows:
        title = r.get("publication_title") or r.get("candidate_key")
        md.append(
            f"\n## {r.get('publication_halId') or r.get('candidate_key')} — {title}\n"
        )
        md.append(f"- Hubs: {', '.join(f'`{h}`' for h in (r.get('hubs') or []))}")
        md.append(f"- Match: `{r.get('match_basis')}`")
        if r.get("publication_uri"):
            md.append(f"- Publication: {r['publication_uri']}")
        md.append(f"- Datasets ({r.get('n_datasets')}):")
        for d in r.get("datasets") or []:
            md.append(f"  - `{d.get('value')}` ← `{d.get('source')}`")
        md.append(f"- Software ({r.get('n_software_signals')}):")
        for s in r.get("software_signals") or []:
            md.append(f"  - `{s.get('kind')}` ← `{s.get('source')}` : {s.get('value')}")
        if r.get("dataset_notices"):
            md.append("- Dataset notices:")
            for n in r["dataset_notices"]:
                md.append(
                    f"  - [{n.get('halId_s')}]({n.get('uri_s')}) — {n.get('title_s')}"
                )
    md.append(
        "\n---\nFiles: `publications_with_dataset_and_software.csv` / `.jsonl`.\n"
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    hub_counts: Counter[str] = Counter()
    for r in result.rows:
        for h in r.get("hubs") or []:
            hub_counts[h] += 1

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
        "by_hub": dict(hub_counts),
        "by_primary_hub": dict(Counter(r.get("primary_hub") for r in result.rows)),
        "by_match_basis": dict(Counter(r.get("match_basis") for r in result.rows)),
        "by_docType": dict(
            Counter(r.get("publication_docType") for r in result.rows)
        ),
        "method": [
            "Publication hub: relatedData_s + software signals on a scholarly notice.",
            "Software hub: SOFTWARE with relatedPublication_s + relatedData_s (DOI→HAL).",
            "Dataset hub: dataset-like / OTHER notice with relatedPublication + relatedSoftware.",
            "TEI relatedItem COAR subtypes enrich dataset vs software typing.",
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
