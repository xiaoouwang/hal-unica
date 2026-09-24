"""Full census of HAL relatedData → any data repository (via DataCite)."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from .client import HalClient
from .datacite import DataCiteClient, DoiResolution, looks_like_doi
from .timeutil import format_hal_date, utc_now

CENSUS_FL = [
    "docid",
    "halId_s",
    "uri_s",
    "title_s",
    "docType_s",
    "doiId_s",
    "relatedData_s",
    "relatedPublication_s",
    "seeAlso_s",
    "producedDate_s",
    "producedDateY_i",
    "producedDateM_i",
    "modifiedDate_tdate",
    "structAcronym_s",
    "structName_s",
]

# Fields that may carry dataset identifiers on HAL notices.
# Datasets belong in relatedData_s; other fields are tracked as provenance anomalies.
LINK_SOURCE_FIELDS = (
    "relatedData_s",
    "relatedPublication_s",
    "seeAlso_s",
)
EXPECTED_DATASET_FIELD = "relatedData_s"

# Broad enough to catch relatedData plus DOIs / Nakala URLs filed elsewhere.
CENSUS_Q = (
    "(relatedData_s:*) OR (relatedPublication_s:10.*) OR (seeAlso_s:*)"
)

DOI_RE = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"'<>\]\),;]+)",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return format_hal_date(utc_now())


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_related_token(raw: str, *, source_field: str) -> dict[str, Any]:
    """Classify a related-link token and attach HAL field provenance."""
    text = raw.strip()
    m = DOI_RE.search(text)
    if m:
        doi = m.group(1).rstrip(").,;\"'")
        doi = re.sub(r"&#x[0-9a-fA-F]+;?", "", doi)
        kind = "doi"
        value = doi
    elif text.startswith("http://") or text.startswith("https://"):
        kind = "url"
        value = text
    elif re.match(r"^(hal|tel|hrt|ineris|insu|halshs|hal-)", text, re.I):
        kind = "hal_id"
        value = text
    else:
        kind = "other"
        value = text
    return {
        "raw": raw,
        "kind": kind,
        "value": value,
        "source_field": source_field,
        "expected_field": EXPECTED_DATASET_FIELD,
        "field_ok": source_field == EXPECTED_DATASET_FIELD,
    }


def _tokens_from_doc(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    tokens: list[dict[str, Any]] = []
    raw_by_field: dict[str, list[str]] = {}
    for field_name in LINK_SOURCE_FIELDS:
        values = [str(x) for x in _as_list(doc.get(field_name))]
        if not values:
            continue
        raw_by_field[field_name] = values
        for raw in values:
            tokens.append(normalize_related_token(raw, source_field=field_name))
    return tokens, raw_by_field


@dataclass
class CensusLinks:
    publications: list[dict[str, Any]] = field(default_factory=list)
    resolutions: dict[str, DoiResolution] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""
    collection: str = ""
    num_hal_with_related: int = 0
    num_related_tokens: int = 0
    num_unique_dois: int = 0
    since: str | None = None
    pubs_fetched: int = 0
    pubs_updated: int = 0
    pubs_inserted: int = 0
    dois_resolved_live: int = 0
    dois_from_cache: int = 0
    watermark_modified: str | None = None


def load_publications_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return by_id
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                pub = json.loads(line)
            except json.JSONDecodeError:
                continue
            hid = pub.get("halId_s")
            if hid:
                by_id[str(hid)] = pub
    return by_id


def load_doi_resolutions_jsonl(path: Path) -> dict[str, DoiResolution]:
    out: dict[str, DoiResolution] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            doi = row.get("doi")
            if doi:
                out[str(doi)] = DoiResolution.from_dict(row).reclassify()
    return out


def _as_str_list(value: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in _as_list(value):
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def laboratory_labels(
    acronyms: list[str] | None,
    names: list[str] | None,
    *,
    limit: int = 10,
) -> list[str]:
    """Prefer unique structure acronyms; fall back to names. Cap for display."""
    labels = _as_str_list(acronyms)
    if not labels:
        labels = _as_str_list(names)
    return labels[:limit]


def _publication_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    tokens, raw_by_field = _tokens_from_doc(doc)
    acronyms = _as_str_list(doc.get("structAcronym_s"))
    names = _as_str_list(doc.get("structName_s"))
    return {
        "halId_s": _first(doc.get("halId_s")),
        "uri_s": _first(doc.get("uri_s")),
        "title_s": _first(doc.get("title_s")),
        "docType_s": _first(doc.get("docType_s")),
        "doiId_s": _first(doc.get("doiId_s")),
        "producedDate_s": _first(doc.get("producedDate_s")),
        "producedDateY_i": doc.get("producedDateY_i"),
        "producedDateM_i": doc.get("producedDateM_i"),
        "modifiedDate_tdate": _first(doc.get("modifiedDate_tdate")),
        "structAcronym_s": acronyms,
        "structName_s": names,
        "laboratories": laboratory_labels(acronyms, names),
        "relatedData_raw": raw_by_field.get("relatedData_s", []),
        "relatedPublication_raw": raw_by_field.get("relatedPublication_s", []),
        "seeAlso_raw": raw_by_field.get("seeAlso_s", []),
        "link_raw_by_field": raw_by_field,
        "related_tokens": tokens,
    }


def backfill_laboratories_from_harvest(
    publications: list[dict[str, Any]],
    harvest_path: Path,
) -> int:
    """Fill laboratory fields from a local harvest JSONL when missing."""
    if not harvest_path.exists():
        return 0
    by_id = {
        str(p.get("halId_s")): p
        for p in publications
        if p.get("halId_s") and not p.get("laboratories") and not p.get("structAcronym_s")
    }
    if not by_id:
        return 0
    filled = 0
    with harvest_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or not by_id:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            hid = _first(doc.get("halId_s"))
            if not hid or hid not in by_id:
                continue
            acronyms = _as_str_list(doc.get("structAcronym_s"))
            names = _as_str_list(doc.get("structName_s"))
            pub = by_id.pop(hid)
            pub["structAcronym_s"] = acronyms
            pub["structName_s"] = names
            pub["laboratories"] = laboratory_labels(acronyms, names)
            filled += 1
    return filled


def _attach_resolutions(
    publications: list[dict[str, Any]],
    resolutions: dict[str, DoiResolution],
) -> None:
    for pub in publications:
        # Ensure display labs exist even on older JSONL rows.
        if not pub.get("laboratories"):
            pub["laboratories"] = laboratory_labels(
                pub.get("structAcronym_s") or [],
                pub.get("structName_s") or [],
            )

        tokens = pub.get("related_tokens") or []
        related_data_dois = {
            str(t.get("value") or "").lower()
            for t in tokens
            if t.get("kind") == "doi"
            and t.get("source_field") == EXPECTED_DATASET_FIELD
            and t.get("value")
        }

        datasets = []
        repos: list[str] = []
        anomaly_fields: list[str] = []
        for t in tokens:
            entry: dict[str, Any] = dict(t)
            if t.get("kind") == "doi" and t.get("value") in resolutions:
                r = resolutions[t["value"]]
                entry["resolution"] = r.to_dict()
                if r.repository:
                    repos.append(r.repository)
                # Wrong HAL field is only a correction if the same DOI is absent
                # from relatedData_s on this notice (otherwise it is supplementary).
                doi_l = str(t.get("value") or "").lower()
                if (
                    r.object_kind == "dataset_repo"
                    and not t.get("field_ok", True)
                    and doi_l not in related_data_dois
                ):
                    entry["misfiled_dataset_link"] = True
                    entry["correction_note"] = (
                        f"Dataset DOI found only in {t.get('source_field')}; "
                        f"expected HAL field is {EXPECTED_DATASET_FIELD}."
                    )
                    src = t.get("source_field")
                    if src and src not in anomaly_fields:
                        anomaly_fields.append(src)
                elif (
                    r.object_kind == "dataset_repo"
                    and not t.get("field_ok", True)
                    and doi_l in related_data_dois
                ):
                    entry["misfiled_dataset_link"] = False
                    entry["also_in_relatedData_s"] = True
            datasets.append(entry)
        seen: set[str] = set()
        uniq_repos: list[str] = []
        for r in repos:
            if r not in seen:
                seen.add(r)
                uniq_repos.append(r)
        pub["datasets"] = datasets
        pub["repositories"] = uniq_repos
        pub["misfiled_dataset_source_fields"] = anomaly_fields
        pub["has_misfiled_dataset_link"] = bool(anomaly_fields)


def run_census(
    *,
    client: HalClient,
    datacite: DataCiteClient,
    log: TextIO | None = None,
    since: str | None = None,
    existing_publications: dict[str, dict[str, Any]] | None = None,
    existing_resolutions: dict[str, DoiResolution] | None = None,
) -> CensusLinks:
    def say(msg: str) -> None:
        if log:
            log.write(msg + "\n")
            log.flush()

    started = _utc_now()
    say(f"[{started}] census start collection={client.collection} since={since or '*'}")

    by_id: dict[str, dict[str, Any]] = dict(existing_publications or {})
    prior_ids = set(by_id)
    resolutions: dict[str, DoiResolution] = dict(existing_resolutions or {})

    fq: list[str] = []
    if since:
        fq.append(f"modifiedDate_tdate:[{since} TO *]")

    fetched = 0
    updated = 0
    inserted = 0
    max_modified: str | None = None
    token_count = 0
    dois_needed: set[str] = set()

    for doc in client.iter_docs(q=CENSUS_Q, fq=fq or None, fl=CENSUS_FL, rows=200):
        pub = _publication_from_doc(doc)
        hid = pub.get("halId_s")
        if not hid:
            continue
        # Keep notices that actually yielded tokens from tracked fields
        if not pub.get("related_tokens"):
            continue
        fetched += 1
        mod = pub.get("modifiedDate_tdate")
        if isinstance(mod, str) and (max_modified is None or mod > max_modified):
            max_modified = mod
        if hid in prior_ids:
            updated += 1
        else:
            inserted += 1
            prior_ids.add(hid)
        by_id[hid] = pub

    publications = list(by_id.values())
    for pub in publications:
        tokens = pub.get("related_tokens") or []
        token_count += len(tokens)
        for t in tokens:
            if t.get("kind") == "doi" and t.get("value"):
                dois_needed.add(t["value"])

    say(f"HAL publications with linked identifiers (merged): {len(publications)}")
    say(f"  query: {CENSUS_Q}")
    say(f"  fetched this run: {fetched} (updated={updated}, inserted={inserted})")
    say(f"link tokens: {token_count}")
    say(f"unique DOI candidates: {len(dois_needed)}")

    to_resolve = sorted(d for d in dois_needed if d not in resolutions)
    cached = len(dois_needed) - len(to_resolve)
    say(f"DataCite cache hits: {cached}; to resolve: {len(to_resolve)}")

    for i, doi in enumerate(to_resolve, 1):
        res = datacite.resolve(doi)
        resolutions[doi] = res
        if i % 25 == 0 or i == len(to_resolve):
            say(f"DataCite resolved {i}/{len(to_resolve)}")

    _attach_resolutions(publications, resolutions)

    finished = _utc_now()
    say(f"[{finished}] census done")

    final_resolutions = {d: resolutions[d] for d in sorted(dois_needed) if d in resolutions}

    return CensusLinks(
        publications=publications,
        resolutions=final_resolutions,
        started_at=started,
        finished_at=finished,
        collection=client.collection,
        num_hal_with_related=len(publications),
        num_related_tokens=token_count,
        num_unique_dois=len(dois_needed),
        since=since,
        pubs_fetched=fetched,
        pubs_updated=updated,
        pubs_inserted=inserted,
        dois_resolved_live=len(to_resolve),
        dois_from_cache=cached,
        watermark_modified=max_modified,
    )


def summarize_census(census: CensusLinks) -> dict[str, Any]:
    by_repo: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_prefix: Counter[str] = Counter()
    by_host: Counter[str] = Counter()
    by_token_kind: Counter[str] = Counter()
    by_source_field: Counter[str] = Counter()
    by_dataset_source_field: Counter[str] = Counter()
    pubs_with_dataset_repo = 0
    misfiled_links = 0
    pubs_with_misfiled = 0

    for pub in census.publications:
        has_dataset = False
        has_misfiled = False
        for t in pub.get("datasets") or []:
            by_token_kind[t.get("kind") or "other"] += 1
            src = t.get("source_field") or "unknown"
            by_source_field[src] += 1
            res = t.get("resolution") or {}
            repo = res.get("repository")
            if repo:
                by_repo[repo] += 1
            ok = res.get("object_kind")
            if ok:
                by_kind[ok] += 1
            if ok == "dataset_repo":
                has_dataset = True
                by_dataset_source_field[src] += 1
                if t.get("misfiled_dataset_link"):
                    misfiled_links += 1
                    has_misfiled = True
            if res.get("prefix"):
                by_prefix[res["prefix"]] += 1
            if res.get("landing_host"):
                by_host[res["landing_host"]] += 1
        if has_dataset:
            pubs_with_dataset_repo += 1
        if has_misfiled:
            pubs_with_misfiled += 1

    return {
        "collection": census.collection,
        "started_at": census.started_at,
        "finished_at": census.finished_at,
        "since": census.since,
        "hal_publications_with_relatedData": census.num_hal_with_related,
        "related_tokens": census.num_related_tokens,
        "unique_dois_resolved": census.num_unique_dois,
        "publications_with_dataset_repo_landing": pubs_with_dataset_repo,
        "misfiled_dataset_links": misfiled_links,
        "publications_with_misfiled_dataset_link": pubs_with_misfiled,
        "expected_dataset_field": EXPECTED_DATASET_FIELD,
        "incremental": {
            "pubs_fetched": census.pubs_fetched,
            "pubs_updated": census.pubs_updated,
            "pubs_inserted": census.pubs_inserted,
            "dois_resolved_live": census.dois_resolved_live,
            "dois_from_cache": census.dois_from_cache,
            "watermark_modified": census.watermark_modified,
        },
        "by_repository": dict(sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_object_kind": dict(sorted(by_kind.items())),
        "by_doi_prefix": dict(sorted(by_prefix.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_landing_host": dict(sorted(by_host.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_token_kind": dict(sorted(by_token_kind.items())),
        "by_source_field": dict(sorted(by_source_field.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_dataset_source_field": dict(
            sorted(by_dataset_source_field.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
    }


def write_census_artifacts(census: CensusLinks, out_dir: Path, log_path: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    summary = summarize_census(census)
    paths: dict[str, Path] = {}

    pubs_path = out_dir / "publications_related_data.jsonl"
    with pubs_path.open("w", encoding="utf-8") as fh:
        for pub in sorted(census.publications, key=lambda p: p.get("halId_s") or ""):
            fh.write(json.dumps(pub, ensure_ascii=False) + "\n")
    paths["publications_jsonl"] = pubs_path

    doi_path = out_dir / "doi_resolutions.jsonl"
    with doi_path.open("w", encoding="utf-8") as fh:
        for doi in sorted(census.resolutions):
            fh.write(json.dumps(census.resolutions[doi].to_dict(), ensure_ascii=False) + "\n")
    paths["doi_resolutions_jsonl"] = doi_path

    # Flat correspondence table: every related DOI with HAL context + field provenance
    map_csv = out_dir / "doi_hal_repository_map.csv"
    with map_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "halId_s",
                "hal_uri",
                "hal_title",
                "hal_docType",
                "publication_doi",
                "source_field",
                "expected_field",
                "field_ok",
                "misfiled_dataset_link",
                "related_raw",
                "related_kind",
                "dataset_doi",
                "repository",
                "object_kind",
                "publisher",
                "landing_url",
                "landing_host",
                "doi_prefix",
                "datacite_client",
                "dataset_title",
                "resolve_error",
                "correction_note",
            ],
        )
        writer.writeheader()
        for pub in census.publications:
            for t in pub.get("datasets") or []:
                res = t.get("resolution") or {}
                writer.writerow(
                    {
                        "halId_s": pub.get("halId_s"),
                        "hal_uri": pub.get("uri_s"),
                        "hal_title": pub.get("title_s"),
                        "hal_docType": pub.get("docType_s"),
                        "publication_doi": pub.get("doiId_s"),
                        "source_field": t.get("source_field"),
                        "expected_field": t.get("expected_field") or EXPECTED_DATASET_FIELD,
                        "field_ok": t.get("field_ok"),
                        "misfiled_dataset_link": bool(t.get("misfiled_dataset_link")),
                        "related_raw": t.get("raw"),
                        "related_kind": t.get("kind"),
                        "dataset_doi": t.get("value") if t.get("kind") == "doi" else "",
                        "repository": res.get("repository"),
                        "object_kind": res.get("object_kind"),
                        "publisher": res.get("publisher"),
                        "landing_url": res.get("landing_url"),
                        "landing_host": res.get("landing_host"),
                        "doi_prefix": res.get("prefix"),
                        "datacite_client": res.get("client_id"),
                        "dataset_title": res.get("title"),
                        "resolve_error": res.get("error"),
                        "correction_note": t.get("correction_note") or "",
                    }
                )
    paths["doi_hal_map_csv"] = map_csv

    # Correction queue: dataset landings filed outside relatedData_s
    misfiled_csv = out_dir / "misfiled_dataset_links.csv"
    with misfiled_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "halId_s",
                "hal_uri",
                "hal_title",
                "hal_docType",
                "publication_doi",
                "laboratories",
                "source_field",
                "expected_field",
                "dataset_doi",
                "repository",
                "landing_url",
                "dataset_title",
                "correction_note",
            ],
        )
        writer.writeheader()
        for pub in census.publications:
            for t in pub.get("datasets") or []:
                if not t.get("misfiled_dataset_link"):
                    continue
                res = t.get("resolution") or {}
                writer.writerow(
                    {
                        "halId_s": pub.get("halId_s"),
                        "hal_uri": pub.get("uri_s"),
                        "hal_title": pub.get("title_s"),
                        "hal_docType": pub.get("docType_s"),
                        "publication_doi": pub.get("doiId_s"),
                        "laboratories": " | ".join(pub.get("laboratories") or []),
                        "source_field": t.get("source_field"),
                        "expected_field": t.get("expected_field") or EXPECTED_DATASET_FIELD,
                        "dataset_doi": t.get("value"),
                        "repository": res.get("repository"),
                        "landing_url": res.get("landing_url"),
                        "dataset_title": res.get("title"),
                        "correction_note": t.get("correction_note") or "",
                    }
                )
    paths["misfiled_dataset_links_csv"] = misfiled_csv
    # Unique DOI → repository dictionary
    doi_dict_csv = out_dir / "doi_to_repository.csv"
    with doi_dict_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "doi",
                "repository",
                "object_kind",
                "publisher",
                "landing_url",
                "landing_host",
                "prefix",
                "client_id",
                "title",
                "error",
            ],
        )
        writer.writeheader()
        for doi in sorted(census.resolutions):
            r = census.resolutions[doi]
            writer.writerow(
                {
                    "doi": r.doi,
                    "repository": r.repository,
                    "object_kind": r.object_kind,
                    "publisher": r.publisher,
                    "landing_url": r.landing_url,
                    "landing_host": r.landing_host,
                    "prefix": r.prefix,
                    "client_id": r.client_id,
                    "title": r.title,
                    "error": r.error,
                }
            )
    paths["doi_to_repository_csv"] = doi_dict_csv

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["summary_json"] = summary_path

    manifest = {
        "generated_at": _utc_now(),
        "collection": census.collection,
        "hal_api": f"https://api.archives-ouvertes.fr/search/{census.collection}/",
        "hal_query": CENSUS_Q,
        "link_source_fields": list(LINK_SOURCE_FIELDS),
        "expected_dataset_field": EXPECTED_DATASET_FIELD,
        "since": census.since,
        "watermark_modified": census.watermark_modified,
        "datacite_api": "https://api.datacite.org/dois/{doi}",
        "started_at": census.started_at,
        "finished_at": census.finished_at,
        "artifacts": {k: str(v) for k, v in paths.items()},
        "log_path": str(log_path),
        "counts": {
            "hal_publications_with_relatedData": census.num_hal_with_related,
            "related_tokens": census.num_related_tokens,
            "unique_dois": census.num_unique_dois,
            "pubs_fetched": census.pubs_fetched,
            "pubs_updated": census.pubs_updated,
            "pubs_inserted": census.pubs_inserted,
            "dois_resolved_live": census.dois_resolved_live,
            "dois_from_cache": census.dois_from_cache,
            "misfiled_dataset_links": summary.get("misfiled_dataset_links"),
            "publications_with_misfiled_dataset_link": summary.get(
                "publications_with_misfiled_dataset_link"
            ),
        },
        "method": [
            "List UniCA HAL notices with relatedData_s, relatedPublication_s DOIs, or seeAlso_s.",
            "Record the HAL source field on every token (provenance for corrections).",
            "Optional modifiedDate_tdate window for incremental refresh; merge by halId_s.",
            "Parse each token as DOI, URL, HAL id, or other.",
            "Resolve new DOIs with DataCite REST API; reuse doi_resolutions.jsonl cache.",
            "Label repository and object_kind from landing host / publisher / known DOI prefix; never default unknown hosts to dataset_repo.",
            "Flag dataset_repo DOIs filed only outside relatedData_s (still listed there = supplementary, not a correction).",
            "Build dataset_to_publications (dataset_repo only) with sticky retrieved_at for the All repositories page.",
            "Write publication-level JSONL, DOI resolution JSONL, and CSV correspondence tables.",
        ],
    }
    manifest_path = out_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["manifest_json"] = manifest_path

    # Human-readable methodology
    method_md = out_dir / "METHODOLOGY.md"
    method_md.write_text(
        f"""# Related-data repository census — methodology

Generated: `{manifest['generated_at']}`  
Collection: `{census.collection}`  
Run window: `{census.started_at}` → `{census.finished_at}`

## Goal

For every UniCA HAL notice that links a related identifier (ideally as
`relatedData`), record **which identifier was linked**, **which HAL field it
came from**, **which repository it resolves to**, and keep the raw evidence so
misfiled dataset links can be corrected.

## Pipeline

1. **HAL Search API** — `q={CENSUS_Q}` on `/search/{census.collection}/`
   with Solr cursor pagination (`sort=docid asc`). Optional
   `modifiedDate_tdate` window for incremental refresh; merge by `halId_s`.
2. **Token parse** — values from `relatedData_s`, `relatedPublication_s`, and
   `seeAlso_s` are classified as `doi`, `url`, `hal_id`, or `other`. Each token
   keeps `source_field` / `expected_field` / `field_ok` provenance.
3. **DataCite resolve** — each unique DOI is fetched from
   `https://api.datacite.org/dois/{{doi}}` (cache: `doi_resolutions.jsonl`).
4. **Repository label + object_kind** — from landing host / publisher / known
   DOI prefix (`dataset_repo` vs `publication_landing` vs unresolved). Unknown
   hosts are **not** assumed to be data repositories. See project `README.md`.
5. **Misfiled flag** — if a DOI resolves to a `dataset_repo`, was filed outside
   `relatedData_s`, **and** the same DOI is not also present in `relatedData_s`
   on that notice, it is listed in `misfiled_dataset_links.csv`. When the DOI
   already appears in `relatedData_s`, an extra mention elsewhere is treated as
   supplementary (not a correction).
6. **Dataset index** (built after census) — `dataset_to_publications.*` keeps
   only `object_kind=dataset_repo`, with sticky `retrieved_at` for the
   All repositories page.

## Artifacts

| File | Contents |
|---|---|
| `publications_related_data.jsonl` | One HAL notice per line + all related tokens and resolutions |
| `doi_resolutions.jsonl` | One unique DOI per line (DataCite fields + repository label) |
| `doi_to_repository.csv` | Flat DOI → repository dictionary (all object kinds) |
| `doi_hal_repository_map.csv` | Full correspondence: HAL notice ↔ DOI ↔ repository ↔ **source field** |
| `dataset_to_publications.csv` / `.jsonl` | **Dataset-only** DOI → HAL publications (+ `retrieved_at`) |
| `misfiled_dataset_links.csv` | Dataset landings filed outside `relatedData_s` (correction queue) |
| `summary.json` | Aggregated counts including `by_dataset_source_field` / `by_object_kind` |
| `run_manifest.json` | Run metadata and method checklist |
| `{log_path.name}` | Chronological run log |

Project-level documentation (design, refresh schedule, classification rules):
repository root `README.md`.


## Counts (this run)

- HAL notices with linked identifiers: **{census.num_hal_with_related}**
- Related tokens: **{census.num_related_tokens}**
- Unique DOIs resolved: **{census.num_unique_dois}**
- Publications with at least one dataset-repo landing: **{summary['publications_with_dataset_repo_landing']}**
- Misfiled dataset links (wrong HAL field): **{summary.get('misfiled_dataset_links', 0)}**
- Publications with ≥1 misfiled dataset link: **{summary.get('publications_with_misfiled_dataset_link', 0)}**

### Dataset DOIs by HAL source field

""",
        encoding="utf-8",
    )
    with method_md.open("a", encoding="utf-8") as fh:
        for field_name, count in (summary.get("by_dataset_source_field") or {}).items():
            fh.write(f"- **`{field_name}`**: {count}\n")
        fh.write("\n### By repository (DOI evidence)\n\n")
        for repo, count in summary["by_repository"].items():
            fh.write(f"- **{repo}**: {count}\n")
        fh.write("\n### By landing host\n\n")
        for host, count in list(summary["by_landing_host"].items())[:40]:
            fh.write(f"- `{host}`: {count}\n")
    paths["methodology_md"] = method_md

    # Keep a copy of the run log next to artifacts for the docs bundle
    if log_path.exists():
        bundled = out_dir / "run.log"
        bundled.write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")
        paths["run_log"] = bundled

    meta = {
        "watermark_modified": census.watermark_modified,
        "since": census.since,
        "started_at": census.started_at,
        "finished_at": census.finished_at,
        "collection": census.collection,
        "num_hal_with_related": census.num_hal_with_related,
        "num_unique_dois": census.num_unique_dois,
        "pubs_fetched": census.pubs_fetched,
        "dois_resolved_live": census.dois_resolved_live,
        "dois_from_cache": census.dois_from_cache,
    }
    meta_path = out_dir / "census.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["census_meta"] = meta_path

    return paths
