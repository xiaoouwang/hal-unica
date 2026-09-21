"""Harvest HAL SOFTWARE deposits (code repos, SWHIDs, related publications)."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import HalClient

SOFTWARE_FL = [
    "docid",
    "halId_s",
    "uri_s",
    "title_s",
    "docType_s",
    "doiId_s",
    "swhidId_s",
    "softCodeRepository_s",
    "softProgrammingLanguage_s",
    "softVersion_s",
    "softPlatform_s",
    "softDevelopmentStatus_s",
    "softRuntimePlatform_s",
    "relatedPublication_s",
    "relatedData_s",
    "seeAlso_s",
    "fileMain_s",
    "files_s",
    "abstract_s",
    "authFullName_s",
    "producedDate_s",
    "producedDateY_i",
]


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


def swh_browse_url(swhid: str) -> str:
    """Build a Software Heritage browse URL from a raw SWHID (may include context)."""
    core = swhid.split(";")[0].strip()
    return f"https://archive.softwareheritage.org/browse/{core}"


def harvest_software(client: HalClient) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in client.iter_docs(q="docType_s:SOFTWARE", fl=SOFTWARE_FL, rows=200):
        swhids = _as_list(doc.get("swhidId_s"))
        code_repos = _as_list(doc.get("softCodeRepository_s"))
        related_pubs = _as_list(doc.get("relatedPublication_s"))
        rows.append(
            {
                "halId_s": _first(doc.get("halId_s")),
                "uri_s": _first(doc.get("uri_s")),
                "title_s": _first(doc.get("title_s")),
                "doiId_s": _first(doc.get("doiId_s")),
                "producedDateY_i": doc.get("producedDateY_i"),
                "softCodeRepository_s": code_repos,
                "softProgrammingLanguage_s": _as_list(doc.get("softProgrammingLanguage_s")),
                "softVersion_s": _as_list(doc.get("softVersion_s")),
                "softPlatform_s": _as_list(doc.get("softPlatform_s")),
                "softDevelopmentStatus_s": _as_list(doc.get("softDevelopmentStatus_s")),
                "swhidId_s": swhids,
                "swh_browse_urls": [swh_browse_url(s) for s in swhids],
                "relatedPublication_s": related_pubs,
                "relatedData_s": _as_list(doc.get("relatedData_s")),
                "seeAlso_s": _as_list(doc.get("seeAlso_s")),
                "fileMain_s": _first(doc.get("fileMain_s")),
                "files_s": _as_list(doc.get("files_s")),
                "authFullName_s": _as_list(doc.get("authFullName_s")),
            }
        )
    rows.sort(key=lambda r: (r.get("title_s") or "").lower())
    return rows


def summarize_software(rows: list[dict[str, Any]]) -> dict[str, Any]:
    with_swh = sum(1 for r in rows if r.get("swhidId_s"))
    with_code_repo = sum(1 for r in rows if r.get("softCodeRepository_s"))
    with_related_pub = sum(1 for r in rows if r.get("relatedPublication_s"))
    with_file = sum(1 for r in rows if r.get("fileMain_s") or r.get("files_s"))
    langs: Counter[str] = Counter()
    for r in rows:
        for lang in r.get("softProgrammingLanguage_s") or []:
            langs[lang] += 1
    return {
        "generated_at": _utc_now(),
        "software_deposits": len(rows),
        "with_swhid": with_swh,
        "with_code_repository": with_code_repo,
        "with_related_publication": with_related_pub,
        "with_hal_file": with_file,
        "programming_languages": dict(langs.most_common()),
    }


def write_software_artifacts(rows: list[dict[str, Any]], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_software(rows)
    paths: dict[str, Path] = {}

    jsonl = out_dir / "software_deposits.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    paths["software_jsonl"] = jsonl

    csv_path = out_dir / "software_deposits.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "halId_s",
                "uri_s",
                "title_s",
                "doiId_s",
                "code_repositories",
                "swhids",
                "swh_browse_urls",
                "related_publications",
                "programming_languages",
                "hal_file",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "halId_s": row.get("halId_s"),
                    "uri_s": row.get("uri_s"),
                    "title_s": row.get("title_s"),
                    "doiId_s": row.get("doiId_s"),
                    "code_repositories": " | ".join(row.get("softCodeRepository_s") or []),
                    "swhids": " | ".join(row.get("swhidId_s") or []),
                    "swh_browse_urls": " | ".join(row.get("swh_browse_urls") or []),
                    "related_publications": " | ".join(row.get("relatedPublication_s") or []),
                    "programming_languages": " | ".join(row.get("softProgrammingLanguage_s") or []),
                    "hal_file": row.get("fileMain_s") or "",
                }
            )
    paths["software_csv"] = csv_path

    summary_path = out_dir / "software_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["software_summary"] = summary_path
    return paths


def build_dataset_to_publications(census_pubs_jsonl: Path, out_dir: Path) -> dict[str, Path]:
    """Invert relatedData census: dataset DOI → list of HAL publications."""
    out_dir.mkdir(parents=True, exist_ok=True)
    by_doi: dict[str, dict[str, Any]] = {}

    with census_pubs_jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            pub = json.loads(line)
            for t in pub.get("datasets") or []:
                if t.get("kind") != "doi":
                    continue
                doi = t.get("value")
                if not doi:
                    continue
                res = t.get("resolution") or {}
                entry = by_doi.setdefault(
                    doi,
                    {
                        "dataset_doi": doi,
                        "repository": res.get("repository"),
                        "publisher": res.get("publisher"),
                        "landing_url": res.get("landing_url"),
                        "landing_host": res.get("landing_host"),
                        "object_kind": res.get("object_kind"),
                        "dataset_title": res.get("title"),
                        "publications": [],
                    },
                )
                # refresh resolution if richer
                for k in ("repository", "publisher", "landing_url", "landing_host", "object_kind", "dataset_title"):
                    if not entry.get(k) and res.get(k if k != "dataset_title" else "title"):
                        entry[k] = res.get("title") if k == "dataset_title" else res.get(k)
                pub_ref = {
                    "halId_s": pub.get("halId_s"),
                    "uri_s": pub.get("uri_s"),
                    "title_s": pub.get("title_s"),
                    "docType_s": pub.get("docType_s"),
                    "doiId_s": pub.get("doiId_s"),
                }
                if pub_ref not in entry["publications"]:
                    entry["publications"].append(pub_ref)

    rows = sorted(by_doi.values(), key=lambda r: (r.get("repository") or "", r["dataset_doi"]))

    jsonl = out_dir / "dataset_to_publications.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    csv_path = out_dir / "dataset_to_publications.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "dataset_doi",
                "repository",
                "landing_url",
                "landing_host",
                "dataset_title",
                "halId_s",
                "hal_uri",
                "hal_title",
                "hal_docType",
                "publication_doi",
            ],
        )
        writer.writeheader()
        for row in rows:
            for pub in row["publications"]:
                writer.writerow(
                    {
                        "dataset_doi": row["dataset_doi"],
                        "repository": row.get("repository"),
                        "landing_url": row.get("landing_url"),
                        "landing_host": row.get("landing_host"),
                        "dataset_title": row.get("dataset_title"),
                        "halId_s": pub.get("halId_s"),
                        "hal_uri": pub.get("uri_s"),
                        "hal_title": pub.get("title_s"),
                        "hal_docType": pub.get("docType_s"),
                        "publication_doi": pub.get("doiId_s"),
                    }
                )

    summary = {
        "generated_at": _utc_now(),
        "unique_datasets": len(rows),
        "dataset_publication_links": sum(len(r["publications"]) for r in rows),
        "datasets_with_multiple_publications": sum(
            1 for r in rows if len(r["publications"]) > 1
        ),
    }
    summary_path = out_dir / "dataset_to_publications_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "dataset_to_publications_jsonl": jsonl,
        "dataset_to_publications_csv": csv_path,
        "dataset_to_publications_summary": summary_path,
    }
