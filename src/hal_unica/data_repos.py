"""Detect HAL records linked to NAKALA or Research Data Gouv."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import urlparse

from .client import HalClient

# --- Platform signatures -----------------------------------------------------

NAKALA_DOI_PREFIXES = ("10.34847",)
# National Recherche Data Gouv Dataverse DOI prefix
RDG_DOI_PREFIXES = ("10.57745",)
# Federated / partner Dataverses commonly cited under the RDG ecosystem
RDG_NETWORK_DOI_PREFIXES = (
    "10.15454",  # data.inrae.fr (INRAE)
)

NAKALA_HOSTS = (
    "nakala.fr",
    "www.nakala.fr",
    "api.nakala.fr",
)
RDG_HOSTS = (
    "recherche.data.gouv.fr",
    "www.recherche.data.gouv.fr",
    "entrepot.recherche.data.gouv.fr",
)

# Legacy NAKALA handle (pre-DOI era)
NAKALA_HANDLE_RE = re.compile(r"\b11280/[0-9a-fA-F]+\b")

DOI_RE = re.compile(
    r"\b(10\.\d{4,9}/[^\s\"'<>\]\),;]+)",
    re.IGNORECASE,
)

ENRICH_FL = [
    "docid",
    "halId_s",
    "uri_s",
    "title_s",
    "docType_s",
    "doiId_s",
    "relatedData_s",
    "seeAlso_s",
    "researchData_s",
    "related_s",
    "comment_s",
    "description_s",
    "publisherLink_s",
    "abstract_s",
]


@dataclass
class Evidence:
    platform: str  # nakala | rdg | rdg_network
    kind: str  # primary_doi | related_data | see_also | url | handle | text
    value: str
    field: str
    confidence: str  # high | medium | low
    # Filled by DataCite / URL resolution
    repository: str | None = None
    publisher: str | None = None
    landing_url: str | None = None
    landing_host: str | None = None
    datacite_client: str | None = None
    object_kind: str | None = None  # dataset_repo | publication_landing | other | unresolved
    dataset_title: str | None = None
    misfiled_dataset_link: bool = False
    also_in_relatedData_s: bool = False


@dataclass
class Hit:
    hal_id: str
    uri: str | None
    title: str | None
    doc_type: str | None
    doi: str | None
    platforms: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    laboratories: list[str] = field(default_factory=list)
    modifiedDate_tdate: str | None = None

    def add(self, ev: Evidence) -> None:
        self.evidence.append(ev)
        if ev.platform not in self.platforms:
            self.platforms.append(ev.platform)
        if ev.repository and ev.repository not in self.repositories:
            self.repositories.append(ev.repository)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_str(value: Any) -> str | None:
    items = _as_list(value)
    if not items:
        return None
    return str(items[0])


def _normalize_doi(value: str) -> str:
    v = value.strip().rstrip(").,;")
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v, flags=re.I)
    # HAL sometimes embeds DOIs inside HTML-entity-laden citation strings
    v = re.sub(r"&#x[0-9a-fA-F]+;?", "", v)
    v = re.sub(r"&[a-zA-Z]+;", "", v)
    v = v.strip().rstrip(").,;\"'")
    return v


# Fields that often repeat DOIs inside citation blobs — skip to reduce noise
_SKIP_SCAN_FIELDS = {
    "label_s",
    "label_bibtex",
    "label_endnote",
    "label_xml",
    "label_coins",
    "citationRef_s",
    "citationFull_s",
}


def _host(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _platform_for_doi(doi: str) -> str | None:
    d = _normalize_doi(doi).lower()
    for prefix in NAKALA_DOI_PREFIXES:
        if d.startswith(prefix.lower()):
            return "nakala"
    for prefix in RDG_DOI_PREFIXES:
        if d.startswith(prefix.lower()):
            return "rdg"
    for prefix in RDG_NETWORK_DOI_PREFIXES:
        if d.startswith(prefix.lower()):
            return "rdg_network"
    return None


def _platform_for_host(host: str) -> str | None:
    h = host.lower()
    if h.startswith("www."):
        h = h[4:]
    if h in NAKALA_HOSTS or h.endswith(".nakala.fr"):
        return "nakala"
    if h in RDG_HOSTS or h.endswith("recherche.data.gouv.fr"):
        return "rdg"
    return None


def _scan_string(text: str, *, field_name: str, allow_text: bool) -> list[Evidence]:
    found: list[Evidence] = []
    seen: set[tuple[str, str, str]] = set()

    def push(platform: str, kind: str, value: str, confidence: str) -> None:
        key = (platform, kind, value)
        if key in seen:
            return
        seen.add(key)
        found.append(
            Evidence(
                platform=platform,
                kind=kind,
                value=value,
                field=field_name,
                confidence=confidence,
            )
        )

    # URLs
    for match in re.finditer(r"https?://[^\s\"'<>\]]+", text):
        url = match.group(0).rstrip(").,;\"'")
        host = _host(url)
        if not host:
            continue
        platform = _platform_for_host(host)
        if platform:
            push(platform, "url", url, "high")

    # DOIs
    for match in DOI_RE.finditer(text):
        doi = _normalize_doi(match.group(1))
        platform = _platform_for_doi(doi)
        if platform:
            kind = "primary_doi" if field_name == "doiId_s" else "doi_in_field"
            confidence = "high" if kind == "primary_doi" or field_name in {
                "relatedData_s",
                "seeAlso_s",
                "researchData_s",
            } else "medium"
            push(platform, kind, doi, confidence)

    # Legacy NAKALA handles
    for match in NAKALA_HANDLE_RE.finditer(text):
        push("nakala", "handle", match.group(0), "high")

    # Weak textual mentions (opt-in)
    if allow_text:
        lower = text.lower()
        if "nakala.fr" in lower or re.search(r"\bnakala\b", lower):
            push("nakala", "text", text[:240], "low")
        if "recherche.data.gouv" in lower or "entrepot.recherche.data.gouv" in lower:
            push("rdg", "text", text[:240], "low")

    return found


def scan_record(
    doc: dict[str, Any],
    *,
    include_network: bool = True,
    include_text_mentions: bool = False,
    fields: Iterable[str] | None = None,
) -> Hit | None:
    """Return a Hit if the record links to NAKALA / RDG (else None)."""
    field_names = list(fields) if fields is not None else list(doc.keys())
    hit = Hit(
        hal_id=_first_str(doc.get("halId_s")) or "",
        uri=_first_str(doc.get("uri_s")),
        title=_first_str(doc.get("title_s")),
        doc_type=_first_str(doc.get("docType_s")),
        doi=_first_str(doc.get("doiId_s")),
    )
    if not hit.hal_id:
        return None

    for name in field_names:
        if name not in doc or name in _SKIP_SCAN_FIELDS:
            continue
        # relatedData_s values are often bare DOIs — treat specially for kind
        for raw in _as_list(doc.get(name)):
            if raw is None:
                continue
            text = str(raw)
            evidences = _scan_string(
                text, field_name=name, allow_text=include_text_mentions
            )
            for ev in evidences:
                if ev.platform == "rdg_network" and not include_network:
                    continue
                if name == "relatedData_s" and ev.kind in {"doi_in_field", "primary_doi"}:
                    ev = Evidence(
                        platform=ev.platform,
                        kind="related_data",
                        value=ev.value,
                        field=name,
                        confidence="high",
                    )
                elif name == "relatedPublication_s" and ev.kind in {"doi_in_field", "primary_doi"}:
                    ev = Evidence(
                        platform=ev.platform,
                        kind="related_publication",
                        value=ev.value,
                        field=name,
                        confidence="medium",
                    )
                elif name == "seeAlso_s" and ev.kind == "url":
                    ev = Evidence(
                        platform=ev.platform,
                        kind="see_also",
                        value=ev.value,
                        field=name,
                        confidence="high",
                    )
                elif name == "seeAlso_s" and ev.kind in {"doi_in_field", "primary_doi"}:
                    ev = Evidence(
                        platform=ev.platform,
                        kind="see_also",
                        value=ev.value,
                        field=name,
                        confidence="medium",
                    )
                elif name == "doiId_s" and ev.kind in {"doi_in_field", "primary_doi"}:
                    ev = Evidence(
                        platform=ev.platform,
                        kind="primary_doi",
                        value=ev.value,
                        field=name,
                        confidence="high",
                    )
                hit.add(ev)

    if not hit.evidence:
        return None
    return hit


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def scan_jsonl(
    path: Path,
    *,
    include_network: bool = True,
    include_text_mentions: bool = False,
) -> dict[str, Hit]:
    hits: dict[str, Hit] = {}
    for doc in iter_jsonl(path):
        hit = scan_record(
            doc,
            include_network=include_network,
            include_text_mentions=include_text_mentions,
        )
        if hit:
            hits[hit.hal_id] = hit
    return hits


def enrich_from_hal(
    client: HalClient,
    *,
    include_network: bool = True,
    include_text_mentions: bool = False,
    rows: int = 1000,
) -> dict[str, Hit]:
    """
    Pull related-data fields from HAL for the collection.

    The local harvest does not include relatedData_s / seeAlso_s; this pass
    recovers explicit dataset links.
    """
    # Broad Solr query: any relatedData, or DOI/URL signatures in indexed text.
    clauses = [
        "relatedData_s:*",
        "researchData_s:*",
        "seeAlso_s:*nakala*",
        "seeAlso_s:*34847*",
        "seeAlso_s:*recherche.data.gouv*",
        "seeAlso_s:*57745*",
        "doiId_s:10.34847*",
        "doiId_s:10.57745*",
    ]
    if include_network:
        clauses.append("doiId_s:10.15454*")
        clauses.append("seeAlso_s:*15454*")
        clauses.append("relatedData_s:10.15454*")
    clauses.append("relatedData_s:10.34847*")
    clauses.append("relatedData_s:10.57745*")
    clauses.append('text:"nakala.fr"')
    clauses.append('text:"recherche.data.gouv.fr"')

    q = " OR ".join(f"({c})" for c in clauses)
    hits: dict[str, Hit] = {}
    for doc in client.iter_docs(q=q, fl=ENRICH_FL, rows=rows):
        hit = scan_record(
            doc,
            include_network=include_network,
            include_text_mentions=include_text_mentions,
        )
        if hit:
            hits[hit.hal_id] = hit
    return hits


def merge_hits(base: dict[str, Hit], extra: dict[str, Hit]) -> dict[str, Hit]:
    out = {k: v for k, v in base.items()}
    for hal_id, hit in extra.items():
        if hal_id not in out:
            out[hal_id] = hit
            continue
        existing = out[hal_id]
        # Prefer richer title/uri from enrich if missing
        if not existing.title and hit.title:
            existing.title = hit.title
        if not existing.uri and hit.uri:
            existing.uri = hit.uri
        if not existing.doc_type and hit.doc_type:
            existing.doc_type = hit.doc_type
        if not existing.doi and hit.doi:
            existing.doi = hit.doi
        for ev in hit.evidence:
            key = (ev.platform, ev.kind, ev.value, ev.field)
            if any(
                (e.platform, e.kind, e.value, e.field) == key for e in existing.evidence
            ):
                continue
            existing.add(ev)
        for repo in hit.repositories:
            if repo not in existing.repositories:
                existing.repositories.append(repo)
    return out


def hit_to_dict(hit: Hit) -> dict[str, Any]:
    return {
        "halId_s": hit.hal_id,
        "uri_s": hit.uri,
        "title_s": hit.title,
        "docType_s": hit.doc_type,
        "doiId_s": hit.doi,
        "platforms": hit.platforms,
        "repositories": hit.repositories,
        "laboratories": list(hit.laboratories or []),
        "modifiedDate_tdate": hit.modifiedDate_tdate,
        "evidence": [asdict(e) for e in hit.evidence],
    }


def hits_from_jsonl(path: Path) -> dict[str, Hit]:
    """Reload previously written find-data-repos JSONL into Hit objects."""
    hits: dict[str, Hit] = {}
    for doc in iter_jsonl(path):
        hit = Hit(
            hal_id=doc.get("halId_s") or "",
            uri=doc.get("uri_s"),
            title=doc.get("title_s"),
            doc_type=doc.get("docType_s"),
            doi=doc.get("doiId_s"),
            platforms=list(doc.get("platforms") or []),
            repositories=list(doc.get("repositories") or []),
            laboratories=list(doc.get("laboratories") or []),
            modifiedDate_tdate=doc.get("modifiedDate_tdate"),
        )
        for raw in doc.get("evidence") or []:
            hit.evidence.append(
                Evidence(
                    platform=raw.get("platform") or "",
                    kind=raw.get("kind") or "",
                    value=raw.get("value") or "",
                    field=raw.get("field") or "",
                    confidence=raw.get("confidence") or "high",
                    repository=raw.get("repository"),
                    publisher=raw.get("publisher"),
                    landing_url=raw.get("landing_url"),
                    landing_host=raw.get("landing_host"),
                    datacite_client=raw.get("datacite_client"),
                    object_kind=raw.get("object_kind"),
                    dataset_title=raw.get("dataset_title") or raw.get("title"),
                    misfiled_dataset_link=bool(raw.get("misfiled_dataset_link")),
                    also_in_relatedData_s=bool(raw.get("also_in_relatedData_s")),
                )
            )
            if raw.get("repository") and raw["repository"] not in hit.repositories:
                hit.repositories.append(raw["repository"])
        if hit.hal_id:
            hits[hit.hal_id] = hit
    return hits


def resolve_repositories(
    hits: dict[str, Hit],
    *,
    min_interval: float = 0.15,
) -> dict[str, Hit]:
    """Attach DataCite publisher / landing host / fine repository label to evidence."""
    from .datacite import DataCiteClient, classify_repository, looks_like_doi

    with DataCiteClient(min_interval=min_interval) as dc:
        for hit in hits.values():
            hit.repositories = []
            for ev in hit.evidence:
                if looks_like_doi(ev.value):
                    doi = _normalize_doi(ev.value)
                    res = dc.resolve(doi)
                    ev.repository = res.repository
                    ev.publisher = res.publisher
                    ev.landing_url = res.landing_url
                    ev.landing_host = res.landing_host
                    ev.datacite_client = res.client_id
                    ev.object_kind = res.object_kind
                elif ev.value.startswith("http"):
                    host = _host(ev.value)
                    repo, kind = classify_repository(
                        doi="",
                        publisher=None,
                        landing_url=ev.value,
                        prefix=None,
                        client_id=None,
                    )
                    ev.repository = repo
                    ev.landing_url = ev.value
                    ev.landing_host = host
                    ev.object_kind = kind
                if ev.repository and ev.repository not in hit.repositories:
                    hit.repositories.append(ev.repository)
    return hits


def summarize(hits: dict[str, Hit]) -> dict[str, Any]:
    by_platform: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_repository: dict[str, int] = {}
    by_object_kind: dict[str, int] = {}
    for hit in hits.values():
        for p in hit.platforms:
            by_platform[p] = by_platform.get(p, 0) + 1
        for repo in hit.repositories:
            by_repository[repo] = by_repository.get(repo, 0) + 1
        kinds = {e.kind for e in hit.evidence}
        for k in kinds:
            by_kind[k] = by_kind.get(k, 0) + 1
        obj_kinds = {e.object_kind for e in hit.evidence if e.object_kind}
        for k in obj_kinds:
            by_object_kind[k] = by_object_kind.get(k, 0) + 1
    return {
        "total_hits": len(hits),
        "by_platform": dict(sorted(by_platform.items())),
        "by_repository": dict(sorted(by_repository.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_object_kind": dict(sorted(by_object_kind.items())),
        "by_evidence_kind": dict(sorted(by_kind.items())),
    }
