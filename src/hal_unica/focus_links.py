"""Sync Nakala / RDG focus links from the full relatedData census."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .data_repos import Evidence, Hit, hit_to_dict, summarize

FOCUS_REPOS = {
    "NAKALA": "nakala",
    "Recherche Data Gouv": "rdg",
}


def hits_from_census_publications(
    pubs_path: Path,
    *,
    focus_repos: dict[str, str] | None = None,
) -> dict[str, Hit]:
    """
    Build focus Hit objects from census publications.

    Keeps the related-datasets page in sync with census without a second HAL pull.
    """
    mapping = focus_repos or FOCUS_REPOS
    hits: dict[str, Hit] = {}
    if not pubs_path.exists():
        return hits

    with pubs_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            pub = json.loads(line)
            hid = pub.get("halId_s")
            if not hid:
                continue
            evidence: list[Evidence] = []
            for t in pub.get("datasets") or []:
                if t.get("kind") != "doi":
                    continue
                res = t.get("resolution") or {}
                repo = res.get("repository")
                if repo not in mapping:
                    continue
                if res.get("object_kind") and res.get("object_kind") != "dataset_repo":
                    continue
                evidence.append(
                    Evidence(
                        platform=mapping[repo],
                        kind=(
                            "related_data"
                            if (t.get("source_field") or "relatedData_s") == "relatedData_s"
                            else "related_publication"
                            if t.get("source_field") == "relatedPublication_s"
                            else "see_also"
                        ),
                        value=t.get("value") or "",
                        field=t.get("source_field") or "relatedData_s",
                        confidence="high" if not t.get("misfiled_dataset_link") else "medium",
                        repository=repo,
                        publisher=res.get("publisher"),
                        landing_url=res.get("landing_url"),
                        landing_host=res.get("landing_host"),
                        datacite_client=res.get("client_id"),
                        object_kind=res.get("object_kind") or "dataset_repo",
                        dataset_title=res.get("title"),
                        misfiled_dataset_link=bool(t.get("misfiled_dataset_link")),
                        also_in_relatedData_s=bool(t.get("also_in_relatedData_s")),
                    )
                )
            if not evidence:
                continue
            hit = Hit(
                hal_id=str(hid),
                uri=pub.get("uri_s"),
                title=pub.get("title_s"),
                doc_type=pub.get("docType_s"),
                doi=pub.get("doiId_s"),
                laboratories=list(pub.get("laboratories") or []),
                modifiedDate_tdate=pub.get("modifiedDate_tdate"),
                producedDateY_i=pub.get("producedDateY_i"),
            )
            for ev in evidence:
                hit.add(ev)
            hits[hit.hal_id] = hit
    return hits


def write_focus_links(hits: dict[str, Hit], output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for hit in sorted(hits.values(), key=lambda h: h.hal_id):
            fh.write(json.dumps(hit_to_dict(hit), ensure_ascii=False) + "\n")
    summary = summarize(hits)
    summary_path = output.with_suffix(output.suffix + ".summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary
