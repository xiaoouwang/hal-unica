"""Full census of HAL relatedData → any data repository (via DataCite)."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from .client import HalClient
from .datacite import DataCiteClient, DoiResolution, looks_like_doi

CENSUS_FL = [
    "docid",
    "halId_s",
    "uri_s",
    "title_s",
    "docType_s",
    "doiId_s",
    "relatedData_s",
    "seeAlso_s",
    "producedDateY_i",
]

DOI_RE = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"'<>\]\),;]+)",
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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_related_token(raw: str) -> dict[str, str]:
    """Classify a relatedData_s token as doi / url / hal_id / other."""
    text = raw.strip()
    m = DOI_RE.search(text)
    if m:
        doi = m.group(1).rstrip(").,;\"'")
        doi = re.sub(r"&#x[0-9a-fA-F]+;?", "", doi)
        return {"raw": raw, "kind": "doi", "value": doi}
    if text.startswith("http://") or text.startswith("https://"):
        return {"raw": raw, "kind": "url", "value": text}
    if re.match(r"^(hal|tel|hrt|ineris|insu|halshs|hal-)", text, re.I):
        return {"raw": raw, "kind": "hal_id", "value": text}
    return {"raw": raw, "kind": "other", "value": text}


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


def run_census(
    *,
    client: HalClient,
    datacite: DataCiteClient,
    log: TextIO | None = None,
) -> CensusLinks:
    def say(msg: str) -> None:
        if log:
            log.write(msg + "\n")
            log.flush()

    started = _utc_now()
    say(f"[{started}] census start collection={client.collection}")

    publications: list[dict[str, Any]] = []
    token_count = 0
    dois_needed: set[str] = set()

    for doc in client.iter_docs(q="relatedData_s:*", fl=CENSUS_FL, rows=200):
        related_raw = [str(x) for x in _as_list(doc.get("relatedData_s"))]
        tokens = [normalize_related_token(x) for x in related_raw]
        token_count += len(tokens)
        for t in tokens:
            if t["kind"] == "doi":
                dois_needed.add(t["value"])
        publications.append(
            {
                "halId_s": _first(doc.get("halId_s")),
                "uri_s": _first(doc.get("uri_s")),
                "title_s": _first(doc.get("title_s")),
                "docType_s": _first(doc.get("docType_s")),
                "doiId_s": _first(doc.get("doiId_s")),
                "producedDateY_i": doc.get("producedDateY_i"),
                "relatedData_raw": related_raw,
                "related_tokens": tokens,
            }
        )

    say(f"HAL publications with relatedData_s: {len(publications)}")
    say(f"relatedData tokens: {token_count}")
    say(f"unique DOI candidates: {len(dois_needed)}")

    resolutions: dict[str, DoiResolution] = {}
    for i, doi in enumerate(sorted(dois_needed), 1):
        res = datacite.resolve(doi)
        resolutions[doi] = res
        if i % 25 == 0 or i == len(dois_needed):
            say(f"DataCite resolved {i}/{len(dois_needed)}")

    # Attach resolutions onto each publication
    for pub in publications:
        datasets = []
        repos: list[str] = []
        for t in pub["related_tokens"]:
            entry: dict[str, Any] = dict(t)
            if t["kind"] == "doi" and t["value"] in resolutions:
                r = resolutions[t["value"]]
                entry["resolution"] = r.to_dict()
                if r.repository:
                    repos.append(r.repository)
            datasets.append(entry)
        # stable unique repos
        seen: set[str] = set()
        uniq_repos = []
        for r in repos:
            if r not in seen:
                seen.add(r)
                uniq_repos.append(r)
        pub["datasets"] = datasets
        pub["repositories"] = uniq_repos

    finished = _utc_now()
    say(f"[{finished}] census done")

    return CensusLinks(
        publications=publications,
        resolutions=resolutions,
        started_at=started,
        finished_at=finished,
        collection=client.collection,
        num_hal_with_related=len(publications),
        num_related_tokens=token_count,
        num_unique_dois=len(dois_needed),
    )


def summarize_census(census: CensusLinks) -> dict[str, Any]:
    by_repo: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_prefix: Counter[str] = Counter()
    by_host: Counter[str] = Counter()
    by_token_kind: Counter[str] = Counter()
    pubs_with_dataset_repo = 0

    for pub in census.publications:
        has_dataset = False
        for t in pub.get("datasets") or []:
            by_token_kind[t.get("kind") or "other"] += 1
            res = t.get("resolution") or {}
            repo = res.get("repository")
            if repo:
                by_repo[repo] += 1
            ok = res.get("object_kind")
            if ok:
                by_kind[ok] += 1
            if ok == "dataset_repo":
                has_dataset = True
            if res.get("prefix"):
                by_prefix[res["prefix"]] += 1
            if res.get("landing_host"):
                by_host[res["landing_host"]] += 1
        if has_dataset:
            pubs_with_dataset_repo += 1

    return {
        "collection": census.collection,
        "started_at": census.started_at,
        "finished_at": census.finished_at,
        "hal_publications_with_relatedData": census.num_hal_with_related,
        "related_tokens": census.num_related_tokens,
        "unique_dois_resolved": census.num_unique_dois,
        "publications_with_dataset_repo_landing": pubs_with_dataset_repo,
        "by_repository": dict(sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_object_kind": dict(sorted(by_kind.items())),
        "by_doi_prefix": dict(sorted(by_prefix.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_landing_host": dict(sorted(by_host.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_token_kind": dict(sorted(by_token_kind.items())),
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

    # Flat correspondence table: every related DOI with HAL context
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
                    }
                )
    paths["doi_hal_map_csv"] = map_csv

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
        "hal_query": "relatedData_s:*",
        "datacite_api": "https://api.datacite.org/dois/{doi}",
        "started_at": census.started_at,
        "finished_at": census.finished_at,
        "artifacts": {k: str(v) for k, v in paths.items()},
        "log_path": str(log_path),
        "counts": {
            "hal_publications_with_relatedData": census.num_hal_with_related,
            "related_tokens": census.num_related_tokens,
            "unique_dois": census.num_unique_dois,
        },
        "method": [
            "List UniCA HAL notices with relatedData_s via Search API cursor pagination.",
            "Parse each relatedData token as DOI, URL, HAL id, or other.",
            "Resolve every unique DOI with DataCite REST API.",
            "Label repository from landing host / publisher / known DOI prefix.",
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

For every UniCA HAL notice that declares `relatedData`, record **which identifier
was linked**, **which repository it resolves to**, and keep the raw evidence.

## Pipeline

1. **HAL Search API** — `q=relatedData_s:*` on `/search/{census.collection}/`
   with Solr cursor pagination (`sort=docid asc`).
2. **Token parse** — each `relatedData_s` value is classified as `doi`, `url`,
   `hal_id`, or `other`.
3. **DataCite resolve** — each unique DOI is fetched from
   `https://api.datacite.org/dois/{{doi}}`.
4. **Repository label** — derived from landing URL host when possible
   (e.g. `zenodo.org` → Zenodo, `nakala.fr` → NAKALA,
   `*.recherche.data.gouv.fr` / `data.inrae.fr` → Recherche Data Gouv),
   else DataCite publisher / DOI prefix.

## Artifacts

| File | Contents |
|---|---|
| `publications_related_data.jsonl` | One HAL notice per line + all related tokens and resolutions |
| `doi_resolutions.jsonl` | One unique DOI per line (DataCite fields + repository label) |
| `doi_to_repository.csv` | Flat DOI → repository dictionary |
| `doi_hal_repository_map.csv` | Full correspondence: HAL notice ↔ related DOI ↔ repository |
| `summary.json` | Aggregated counts |
| `run_manifest.json` | Run metadata and method checklist |
| `{log_path.name}` | Chronological run log |

## Counts (this run)

- HAL notices with `relatedData`: **{census.num_hal_with_related}**
- Related tokens: **{census.num_related_tokens}**
- Unique DOIs resolved: **{census.num_unique_dois}**
- Publications with at least one dataset-repo landing: **{summary['publications_with_dataset_repo_landing']}**

### By repository (DOI evidence)

""",
        encoding="utf-8",
    )
    with method_md.open("a", encoding="utf-8") as fh:
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

    return paths
