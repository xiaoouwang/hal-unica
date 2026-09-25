"""Orchestrate daily incremental census → software → site refresh."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO

from .census import (
    backfill_laboratories_from_harvest,
    load_doi_resolutions_jsonl,
    load_publications_jsonl,
    run_census,
    write_census_artifacts,
)
from .client import HalClient
from .datacite import DataCiteClient
from .focus_links import hits_from_census_publications, write_focus_links
from .software import (
    build_dataset_to_publications,
    enrich_software_from_harvest,
    harvest_software,
    write_software_artifacts,
)
from .data_papers import (
    enrich_data_papers_from_resolutions,
    harvest_data_papers,
    write_data_paper_artifacts,
)
from .datacite_census import run_datacite_census, write_datacite_census_artifacts
from .site import write_site
from .timeutil import effective_since, format_hal_date, read_watermark, utc_now
from .universities import DEFAULT_UNIVERSITY, University, resolve_university


@dataclass
class RefreshResult:
    collection: str
    university: str
    started_at: str
    finished_at: str
    since: str | None
    full: bool
    census_publications: int
    pubs_fetched: int
    dois_resolved_live: int
    dois_from_cache: int
    software_deposits: int
    data_papers: int
    focus_hits: int
    site_dir: str


def run_refresh(
    *,
    university: University | str | None = None,
    collection: str | None = None,
    census_dir: Path | None = None,
    links_path: Path | None = None,
    harvest_path: Path | None = None,
    stats_fallback: Path | None = None,
    site_dir: Path | None = None,
    lookback_days: float = 2.0,
    since: str | None = None,
    full: bool = False,
    rate: float = 0.15,
    log_path: Path | None = None,
    log: TextIO | None = None,
) -> RefreshResult:
    if isinstance(university, University):
        uni = university
    elif university:
        uni = resolve_university(university)
    elif collection:
        try:
            uni = resolve_university(collection)
        except KeyError:
            uni = DEFAULT_UNIVERSITY
    else:
        uni = DEFAULT_UNIVERSITY

    collection = collection or uni.collection
    census_dir = census_dir or uni.census_dir
    links_path = links_path or uni.links_path
    harvest_path = harvest_path or uni.harvest_path
    site_dir = site_dir or uni.site_dir
    log_path = log_path or uni.log_path
    if stats_fallback is None:
        stats_fallback = uni.stats_fallback if uni.stats_fallback.exists() else None

    def say(msg: str) -> None:
        if log:
            log.write(msg + "\n")
            log.flush()

    started = format_hal_date(utc_now())
    census_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    say(f"university={uni.id} collection={collection} site={site_dir}")

    resolved_since: str | None = None
    existing_pubs: dict[str, Any] = {}
    existing_res = {}

    if not full:
        wm = read_watermark(census_dir / "census.meta.json")
        resolved_since = effective_since(
            since=since,
            lookback_days=lookback_days,
            watermark=wm,
            safety_hours=1.0,
        )
        pubs_path = census_dir / "publications_related_data.jsonl"
        doi_path = census_dir / "doi_resolutions.jsonl"
        existing_pubs = load_publications_jsonl(pubs_path)
        existing_res = load_doi_resolutions_jsonl(doi_path)
        say(
            f"incremental census since={resolved_since} "
            f"(existing pubs={len(existing_pubs)}, doi cache={len(existing_res)})"
        )
    else:
        say("full census (no date filter; rebuild from HAL)")

    with HalClient(collection=collection, min_interval=rate) as client, DataCiteClient(
        min_interval=rate
    ) as datacite:
        census = run_census(
            client=client,
            datacite=datacite,
            log=log,
            since=resolved_since,
            existing_publications=existing_pubs or None,
            existing_resolutions=existing_res or None,
        )
        if not census.watermark_modified:
            census.watermark_modified = read_watermark(census_dir / "census.meta.json")
        filled = backfill_laboratories_from_harvest(census.publications, harvest_path)
        if filled:
            say(f"backfilled laboratories on {filled} publications from harvest")
        write_census_artifacts(census, census_dir, log_path)

        say("harvesting SOFTWARE deposits (full)")
        soft_rows = harvest_software(client)
        enrich_software_from_harvest(soft_rows, harvest_path)
        write_software_artifacts(soft_rows, census_dir)

        say("harvesting data papers (docSubType_s:DATAPAPER)")
        paper_rows = harvest_data_papers(client)
        enrich_data_papers_from_resolutions(paper_rows, census_dir)
        write_data_paper_artifacts(paper_rows, census_dir)

    pubs_path = census_dir / "publications_related_data.jsonl"
    build_dataset_to_publications(pubs_path, census_dir)
    say("updated dataset→publications index")

    hits = hits_from_census_publications(pubs_path)
    focus_summary = write_focus_links(hits, links_path)
    say(f"synced focus links → {links_path} ({focus_summary['total_hits']} hits)")

    if uni.has_datacite_census:
        say("harvesting institutional DataCite datasets (affiliation / ROR)")
        try:
            with DataCiteClient(min_interval=rate) as dc:
                dc_result = run_datacite_census(
                    university=uni,
                    datacite=dc,
                    log=log,
                )
            write_datacite_census_artifacts(dc_result, census_dir)
            say(
                f"DataCite datasets={len(dc_result.datasets)} "
                f"also_on_hal={dc_result.also_on_hal} "
                f"datacite_only={dc_result.datacite_only}"
            )
        except Exception as exc:  # noqa: BLE001 — do not fail HAL refresh on DataCite outage
            say(f"WARNING: DataCite institutional census failed: {exc}")

    write_site(
        harvest_path=harvest_path if harvest_path.exists() else None,
        links_path=links_path,
        output_dir=site_dir,
        collection=collection,
        census_dir=census_dir,
        stats_fallback=stats_fallback if stats_fallback and stats_fallback.exists() else None,
        university=uni,
    )
    say(f"wrote site → {site_dir}/")

    finished = format_hal_date(utc_now())
    result = RefreshResult(
        collection=collection,
        university=uni.id,
        started_at=started,
        finished_at=finished,
        since=resolved_since,
        full=full,
        census_publications=census.num_hal_with_related,
        pubs_fetched=census.pubs_fetched,
        dois_resolved_live=census.dois_resolved_live,
        dois_from_cache=census.dois_from_cache,
        software_deposits=len(soft_rows),
        data_papers=len(paper_rows),
        focus_hits=focus_summary["total_hits"],
        site_dir=str(site_dir),
    )
    (census_dir / "refresh.meta.json").write_text(
        json.dumps(asdict(result), indent=2) + "\n",
        encoding="utf-8",
    )
    return result
