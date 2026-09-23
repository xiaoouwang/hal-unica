"""Harvest UniCA HAL data papers (ART + docSubType_s=DATAPAPER)."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import HalClient

DATA_PAPER_FL = [
    "docid",
    "halId_s",
    "uri_s",
    "title_s",
    "docType_s",
    "docSubType_s",
    "doiId_s",
    "journalTitle_s",
    "journalPublisher_s",
    "keyword_s",
    "abstract_s",
    "authFullName_s",
    "relatedData_s",
    "relatedPublication_s",
    "seeAlso_s",
    "fileMain_s",
    "files_s",
    "producedDate_s",
    "producedDateY_i",
    "modifiedDate_tdate",
    "structAcronym_s",
    "structName_s",
]

_DOI_RE = re.compile(
    r"(?:doi\.org/|doi:)?\s*(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]


def _uniq_strs(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        text = str(v).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _lab_labels(acronyms: list[str], names: list[str], *, limit: int = 12) -> list[str]:
    labels = _uniq_strs(acronyms)
    if not labels:
        labels = _uniq_strs(names)
    return labels[:limit]


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _extract_doi(token: str) -> str | None:
    text = (token or "").strip()
    if not text:
        return None
    m = _DOI_RE.search(text)
    if not m:
        return None
    return m.group(1).rstrip(").,;").lower()


def _load_previous_retrieved(jsonl_path: Path) -> dict[str, str]:
    previous: dict[str, str] = {}
    if not jsonl_path.exists():
        return previous
    with jsonl_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            hid = row.get("halId_s")
            retrieved = row.get("retrieved_at")
            if hid and retrieved:
                previous[str(hid)] = retrieved
    return previous


def harvest_data_papers(client: HalClient) -> list[dict[str, Any]]:
    """Fetch all UniCA notices tagged as data papers."""
    rows: list[dict[str, Any]] = []
    for doc in client.iter_docs(q="docSubType_s:DATAPAPER", fl=DATA_PAPER_FL, rows=200):
        acronyms = _uniq_strs(_as_list(doc.get("structAcronym_s")))
        names = _uniq_strs(_as_list(doc.get("structName_s")))
        related_data = _as_list(doc.get("relatedData_s"))
        see_also = _as_list(doc.get("seeAlso_s"))
        related_pubs = _as_list(doc.get("relatedPublication_s"))
        rows.append(
            {
                "halId_s": _first(doc.get("halId_s")),
                "uri_s": _first(doc.get("uri_s")),
                "title_s": _first(doc.get("title_s")),
                "docType_s": _first(doc.get("docType_s")) or "ART",
                "docSubType_s": _first(doc.get("docSubType_s")) or "DATAPAPER",
                "doiId_s": _first(doc.get("doiId_s")),
                "journalTitle_s": _first(doc.get("journalTitle_s")),
                "journalPublisher_s": _first(doc.get("journalPublisher_s")),
                "keyword_s": _uniq_strs(_as_list(doc.get("keyword_s"))),
                "abstract_s": _strip_html(_first(doc.get("abstract_s"))),
                "authFullName_s": _as_list(doc.get("authFullName_s")),
                "producedDateY_i": doc.get("producedDateY_i"),
                "producedDate_s": _first(doc.get("producedDate_s")),
                "modifiedDate_tdate": _first(doc.get("modifiedDate_tdate")),
                "structAcronym_s": acronyms,
                "structName_s": names,
                "laboratories": _lab_labels(acronyms, names),
                "relatedData_s": related_data,
                "relatedPublication_s": related_pubs,
                "seeAlso_s": see_also,
                "fileMain_s": _first(doc.get("fileMain_s")),
                "files_s": _as_list(doc.get("files_s")),
                "linked_datasets": [],
            }
        )
    rows.sort(
        key=lambda r: (r.get("modifiedDate_tdate") or "", r.get("title_s") or ""),
        reverse=True,
    )
    return rows


def enrich_data_papers_from_resolutions(
    rows: list[dict[str, Any]],
    census_dir: Path,
) -> int:
    """Attach resolved dataset landings from census DOI cache + related tokens."""
    doi_path = census_dir / "doi_resolutions.jsonl"
    by_doi: dict[str, dict[str, Any]] = {}
    if doi_path.exists():
        with doi_path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                doi = (row.get("doi") or "").lower().strip()
                if doi:
                    by_doi[doi] = row

    pubs_path = census_dir / "publications_related_data.jsonl"
    pubs_by_id: dict[str, dict[str, Any]] = {}
    if pubs_path.exists():
        with pubs_path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                pub = json.loads(line)
                hid = pub.get("halId_s")
                if hid:
                    pubs_by_id[str(hid)] = pub

    filled = 0
    for row in rows:
        linked: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_link(
            *,
            raw: str,
            source_field: str,
            doi: str | None = None,
            res: dict[str, Any] | None = None,
        ) -> None:
            key = (doi or raw).lower()
            if not key or key in seen:
                return
            seen.add(key)
            kind = (res or {}).get("object_kind")
            # Keep relatedData / seeAlso always; skip non-dataset resolutions elsewhere
            if kind and kind != "dataset_repo" and source_field not in {
                "relatedData_s",
                "seeAlso_s",
            }:
                return
            linked.append(
                {
                    "raw": raw,
                    "source_field": source_field,
                    "dataset_doi": doi,
                    "repository": (res or {}).get("repository"),
                    "landing_url": (res or {}).get("landing_url")
                    or (f"https://doi.org/{doi}" if doi else (raw if raw.startswith("http") else None)),
                    "dataset_title": (res or {}).get("title"),
                    "object_kind": kind,
                }
            )

        for field in ("relatedData_s", "seeAlso_s", "relatedPublication_s"):
            for raw in row.get(field) or []:
                doi = _extract_doi(raw)
                res = by_doi.get(doi) if doi else None
                add_link(raw=raw, source_field=field, doi=doi, res=res)

        pub = pubs_by_id.get(str(row.get("halId_s") or ""))
        if pub:
            for tok in pub.get("datasets") or []:
                if not isinstance(tok, dict):
                    continue
                doi = (tok.get("value") or tok.get("doi") or "").lower() or _extract_doi(
                    str(tok.get("raw") or "")
                )
                res = tok.get("resolution") if isinstance(tok.get("resolution"), dict) else None
                if not res and doi:
                    res = by_doi.get(doi)
                add_link(
                    raw=str(tok.get("raw") or doi or ""),
                    source_field=str(tok.get("source_field") or "relatedData_s"),
                    doi=doi,
                    res=res,
                )

        row["linked_datasets"] = linked
        if linked:
            filled += 1
    return filled


def apply_retrieved_at(rows: list[dict[str, Any]], jsonl_path: Path) -> None:
    previous = _load_previous_retrieved(jsonl_path)
    now = _utc_now()
    for row in rows:
        hid = row.get("halId_s")
        row["retrieved_at"] = (
            (previous.get(str(hid)) if hid else None)
            or row.get("modifiedDate_tdate")
            or row.get("producedDate_s")
            or now
        )


def summarize_data_papers(rows: list[dict[str, Any]]) -> dict[str, Any]:
    with_doi = sum(1 for r in rows if r.get("doiId_s"))
    with_datasets = sum(1 for r in rows if r.get("linked_datasets"))
    with_journal = sum(1 for r in rows if r.get("journalTitle_s"))
    with_file = sum(1 for r in rows if r.get("fileMain_s") or r.get("files_s"))
    by_year: Counter[int] = Counter()
    by_journal: Counter[str] = Counter()
    for r in rows:
        y = r.get("producedDateY_i")
        try:
            yi = int(y)
        except (TypeError, ValueError):
            yi = None
        if yi is not None and 1950 <= yi <= 2100:
            by_year[yi] += 1
        journal = r.get("journalTitle_s")
        if journal:
            by_journal[str(journal)] += 1
    return {
        "generated_at": _utc_now(),
        "data_papers": len(rows),
        "with_doi": with_doi,
        "with_linked_dataset": with_datasets,
        "with_journal": with_journal,
        "with_hal_file": with_file,
        "by_year": dict(sorted(by_year.items())),
        "by_journal": dict(by_journal.most_common()),
    }


def write_data_paper_artifacts(rows: list[dict[str, Any]], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / "data_papers.jsonl"
    apply_retrieved_at(rows, jsonl)
    rows.sort(
        key=lambda r: (
            r.get("retrieved_at") or r.get("modifiedDate_tdate") or "",
            r.get("title_s") or "",
        ),
        reverse=True,
    )
    summary = summarize_data_papers(rows)
    paths: dict[str, Path] = {}

    with jsonl.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    paths["data_papers_jsonl"] = jsonl

    csv_path = out_dir / "data_papers.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "halId_s",
                "uri_s",
                "title_s",
                "doiId_s",
                "journalTitle_s",
                "producedDateY_i",
                "retrieved_at",
                "modifiedDate_tdate",
                "laboratories",
                "authors",
                "linked_dataset_dois",
                "linked_repositories",
                "keywords",
            ],
        )
        writer.writeheader()
        for row in rows:
            datasets = row.get("linked_datasets") or []
            writer.writerow(
                {
                    "halId_s": row.get("halId_s"),
                    "uri_s": row.get("uri_s"),
                    "title_s": row.get("title_s"),
                    "doiId_s": row.get("doiId_s"),
                    "journalTitle_s": row.get("journalTitle_s"),
                    "producedDateY_i": row.get("producedDateY_i"),
                    "retrieved_at": row.get("retrieved_at"),
                    "modifiedDate_tdate": row.get("modifiedDate_tdate"),
                    "laboratories": " | ".join(row.get("laboratories") or []),
                    "authors": " | ".join(row.get("authFullName_s") or []),
                    "linked_dataset_dois": " | ".join(
                        d.get("dataset_doi") or d.get("raw") or "" for d in datasets
                    ),
                    "linked_repositories": " | ".join(
                        d.get("repository") or "" for d in datasets if d.get("repository")
                    ),
                    "keywords": " | ".join(row.get("keyword_s") or []),
                }
            )
    paths["data_papers_csv"] = csv_path

    summary_path = out_dir / "data_papers_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["data_papers_summary"] = summary_path
    return paths
