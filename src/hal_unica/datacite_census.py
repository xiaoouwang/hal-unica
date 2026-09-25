"""Institutional DataCite dataset census (affiliation / ROR → datasets).

Complements the HAL-centric relatedData census: many datasets never appear on a
HAL notice. This module queries DataCite for Dataset DOIs attributed to a
university via ROR affiliation identifiers and/or affiliation name strings.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from .datacite import DataCiteClient, classify_repository, _host
from .timeutil import format_hal_date, utc_now
from .universities import University


def build_datacite_affiliation_query(
    *,
    ror_ids: tuple[str, ...] = (),
    affiliation_names: tuple[str, ...] = (),
    resource_type: str = "Dataset",
) -> str:
    """Lucene query for DataCite DOIs attributed to an institution."""
    clauses: list[str] = []
    for ror in ror_ids:
        rid = ror.strip()
        if not rid:
            continue
        clauses.append(f'creators.affiliation.affiliationIdentifier:"{rid}"')
        clauses.append(f'contributors.affiliation.affiliationIdentifier:"{rid}"')
    for name in affiliation_names:
        n = name.strip()
        if not n:
            continue
        # Escape quotes inside names.
        safe = n.replace('"', '\\"')
        clauses.append(f'creators.affiliation.name:"{safe}"')
        clauses.append(f'contributors.affiliation.name:"{safe}"')
    if not clauses:
        raise ValueError("Need at least one ROR id or affiliation name")
    joined = " OR ".join(clauses)
    if resource_type:
        return f"({joined}) AND types.resourceTypeGeneral:{resource_type}"
    return f"({joined})"


def _affiliation_names(creators: list[dict[str, Any]], contributors: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for person in list(creators or []) + list(contributors or []):
        for aff in person.get("affiliation") or []:
            if isinstance(aff, dict):
                label = aff.get("name") or aff.get("affiliationIdentifier") or ""
            else:
                label = str(aff)
            label = label.strip()
            if label and label not in seen:
                seen.add(label)
                names.append(label)
    return names


def _match_reasons(
    *,
    creators: list[dict[str, Any]],
    contributors: list[dict[str, Any]],
    ror_ids: tuple[str, ...],
    affiliation_names: tuple[str, ...],
) -> list[str]:
    reasons: list[str] = []
    ror_set = {r.rstrip("/").lower() for r in ror_ids}
    name_set = {n.casefold() for n in affiliation_names}

    def walk(people: list[dict[str, Any]], role: str) -> None:
        for person in people or []:
            for aff in person.get("affiliation") or []:
                if isinstance(aff, dict):
                    ident = (aff.get("affiliationIdentifier") or "").rstrip("/").lower()
                    name = (aff.get("name") or "").strip()
                else:
                    ident = ""
                    name = str(aff).strip()
                if ident and ident in ror_set:
                    reasons.append(f"{role}_ror")
                if name and name.casefold() in name_set:
                    reasons.append(f"{role}_name")

    walk(creators, "creator")
    walk(contributors, "contributor")
    # Deduplicate while preserving order
    out: list[str] = []
    seen: set[str] = set()
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def record_from_datacite_item(
    item: dict[str, Any],
    *,
    ror_ids: tuple[str, ...] = (),
    affiliation_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    attrs = item.get("attributes") or {}
    rel = item.get("relationships") or {}
    client = ((rel.get("client") or {}).get("data") or {})
    doi = (attrs.get("doi") or item.get("id") or "").strip()
    titles = attrs.get("titles") or []
    title = titles[0].get("title") if titles else None
    landing = attrs.get("url")
    publisher = attrs.get("publisher")
    if isinstance(publisher, dict):
        publisher = publisher.get("name") or publisher.get("publisherName")
    prefix = attrs.get("prefix") or (doi.split("/")[0] if doi else None)
    client_id = client.get("id")
    types = attrs.get("types") or {}
    repository, object_kind = classify_repository(
        doi=doi,
        publisher=publisher,
        landing_url=landing,
        prefix=prefix,
        client_id=client_id,
    )
    creators = attrs.get("creators") or []
    contributors = attrs.get("contributors") or []
    return {
        "doi": doi.lower() if doi else "",
        "doi_raw": doi,
        "title": title,
        "publisher": publisher,
        "landing_url": landing,
        "landing_host": _host(landing),
        "commons_url": f"https://commons.datacite.org/doi.org/{doi}" if doi else None,
        "prefix": prefix,
        "client_id": client_id,
        "repository": repository,
        "object_kind": object_kind,
        "resource_type_general": types.get("resourceTypeGeneral"),
        "publication_year": attrs.get("publicationYear"),
        "created": attrs.get("created"),
        "updated": attrs.get("updated"),
        "registered": attrs.get("registered"),
        "affiliation_names": _affiliation_names(creators, contributors),
        "match_reasons": _match_reasons(
            creators=creators,
            contributors=contributors,
            ror_ids=ror_ids,
            affiliation_names=affiliation_names,
        ),
    }


@dataclass
class DataciteCensusResult:
    university_id: str
    collection: str
    query: str
    started_at: str
    finished_at: str
    total_api: int
    datasets: list[dict[str, Any]] = field(default_factory=list)
    also_on_hal: int = 0
    datacite_only: int = 0
    hal_only: int = 0
    hal_linked_datasets: int = 0


def load_hal_dataset_dois(census_dir: Path) -> dict[str, dict[str, Any]]:
    """Map lowercased DOI → HAL dataset_to_publications row."""
    path = census_dir / "dataset_to_publications.jsonl"
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            doi = (row.get("dataset_doi") or "").strip().lower()
            if doi:
                out[doi] = row
    return out


def run_datacite_census(
    *,
    university: University,
    datacite: DataCiteClient | None = None,
    page_size: int = 100,
    max_records: int | None = None,
    log: TextIO | None = None,
) -> DataciteCensusResult:
    def say(msg: str) -> None:
        if log:
            log.write(msg + "\n")
            log.flush()

    if not university.has_datacite_census:
        raise ValueError(f"{university.id} has no DataCite ROR/affiliation config")

    query = build_datacite_affiliation_query(
        ror_ids=university.ror_ids,
        affiliation_names=university.affiliation_names,
    )
    started = format_hal_date(utc_now())
    say(f"[{started}] datacite census start university={university.id}")
    say(f"  query: {query}")

    owns_client = datacite is None
    client = datacite or DataCiteClient()
    try:
        # Prefer a cheap count via page size 1.
        first = client.search_page(query=query, page_size=1, cursor="1")
        total_api = int((first.get("meta") or {}).get("total") or 0)
        say(f"  DataCite numFound≈{total_api}")

        by_doi: dict[str, dict[str, Any]] = {}
        for item in client.iter_dois(query=query, page_size=page_size, max_records=max_records):
            rec = record_from_datacite_item(
                item,
                ror_ids=university.ror_ids,
                affiliation_names=university.affiliation_names,
            )
            doi = rec.get("doi") or ""
            if not doi:
                continue
            by_doi[doi] = rec
        datasets = list(by_doi.values())
        say(f"  harvested unique DOIs={len(datasets)}")
    finally:
        if owns_client:
            client.close()

    hal_map = load_hal_dataset_dois(university.census_dir)
    also = 0
    for rec in datasets:
        hal = hal_map.get(rec["doi"])
        if hal:
            also += 1
            rec["also_on_hal"] = True
            rec["hal_publications"] = len(hal.get("publications") or [])
            rec["hal_repository"] = hal.get("repository")
            pubs = hal.get("publications") or []
            rec["hal_ids"] = [p.get("halId_s") for p in pubs if p.get("halId_s")]
        else:
            rec["also_on_hal"] = False
            rec["hal_publications"] = 0
            rec["hal_repository"] = None
            rec["hal_ids"] = []

    datacite_dois = {r["doi"] for r in datasets}
    hal_only = sum(1 for d in hal_map if d not in datacite_dois)
    finished = format_hal_date(utc_now())
    return DataciteCensusResult(
        university_id=university.id,
        collection=university.collection,
        query=query,
        started_at=started,
        finished_at=finished,
        total_api=total_api,
        datasets=datasets,
        also_on_hal=also,
        datacite_only=len(datasets) - also,
        hal_only=hal_only,
        hal_linked_datasets=len(hal_map),
    )


def write_datacite_census_artifacts(
    result: DataciteCensusResult,
    census_dir: Path,
) -> dict[str, Path]:
    census_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = census_dir / "datacite_datasets.jsonl"
    csv_path = census_dir / "datacite_datasets.csv"
    summary_path = census_dir / "datacite_datasets_summary.json"

    with jsonl_path.open("w", encoding="utf-8") as fh:
        for row in sorted(result.datasets, key=lambda r: r.get("doi") or ""):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
        "doi",
        "title",
        "repository",
        "publisher",
        "landing_url",
        "commons_url",
        "client_id",
        "publication_year",
        "also_on_hal",
        "hal_publications",
        "hal_ids",
        "match_reasons",
        "object_kind",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in sorted(result.datasets, key=lambda r: r.get("doi") or ""):
            w.writerow(
                {
                    **row,
                    "hal_ids": "|".join(row.get("hal_ids") or []),
                    "match_reasons": "|".join(row.get("match_reasons") or []),
                }
            )

    by_repo: Counter[str] = Counter()
    by_year: Counter[str] = Counter()
    by_client: Counter[str] = Counter()
    for row in result.datasets:
        by_repo[row.get("repository") or "Unknown"] += 1
        y = row.get("publication_year")
        by_year[str(y) if y is not None else "unknown"] += 1
        by_client[row.get("client_id") or "unknown"] += 1

    summary = {
        "university_id": result.university_id,
        "collection": result.collection,
        "query": result.query,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "datacite_total_api": result.total_api,
        "datacite_datasets": len(result.datasets),
        "also_on_hal": result.also_on_hal,
        "datacite_only": result.datacite_only,
        "hal_linked_datasets": result.hal_linked_datasets,
        "hal_only": result.hal_only,
        "coverage_of_hal": (
            round(result.also_on_hal / result.hal_linked_datasets, 4)
            if result.hal_linked_datasets
            else None
        ),
        "by_repository": dict(sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_publication_year": dict(sorted(by_year.items())),
        "by_client": dict(sorted(by_client.items(), key=lambda kv: (-kv[1], kv[0]))[:40]),
        "method": [
            "Query DataCite REST /dois for resourceTypeGeneral=Dataset.",
            "Match creators/contributors affiliation ROR ids and/or affiliation name strings.",
            "Crosswalk DOIs against HAL dataset_to_publications.jsonl (relatedData census).",
            "HAL-only = linked from HAL but missing UniCA affiliation metadata on DataCite.",
            "DataCite-only = attributed to the university on DataCite but not linked from a HAL notice.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "summary": summary_path,
    }
