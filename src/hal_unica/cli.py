from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .census import (
    load_doi_resolutions_jsonl,
    load_publications_jsonl,
    run_census,
    write_census_artifacts,
)
from .client import DEFAULT_COLLECTION, HalClient
from .datacite import DataCiteClient
from .data_repos import (
    enrich_from_hal,
    hit_to_dict,
    hits_from_jsonl,
    merge_hits,
    resolve_repositories,
    scan_jsonl,
    summarize,
)
from .harvest import harvest_metadata
from .refresh import run_refresh
from .report import write_report
from .software import (
    build_dataset_to_publications,
    harvest_software,
    write_software_artifacts,
)
from .site import write_site
from .timeutil import effective_since, read_watermark

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Harvest Université Côte d'Azur metadata from HAL (latest version, metadata only).",
)


@app.command("count")
def count_cmd(
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection / portal code"),
    since: Optional[str] = typer.Option(
        None,
        help="Only count docs with modifiedDate_tdate >= this ISO timestamp (UTC)",
    ),
    lookback_days: Optional[float] = typer.Option(
        None,
        "--lookback-days",
        help="Count docs modified in the last N days (UTC)",
    ),
) -> None:
    """Print how many documents the API reports for the collection."""
    resolved = effective_since(since=since, lookback_days=lookback_days)
    fq = [f"modifiedDate_tdate:[{resolved} TO *]"] if resolved else None
    with HalClient(collection=collection) as client:
        n = client.count(fq=fq)
    if resolved:
        typer.echo(f"{n} (since {resolved})")
    else:
        typer.echo(n)


@app.command("harvest")
def harvest_cmd(
    output: Path = typer.Option(
        Path("data/unica_hal_metadata.jsonl"),
        "--output",
        "-o",
        help="JSONL output path",
    ),
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection / portal code"),
    rows: int = typer.Option(1000, min=1, max=10000, help="Page size (prefer 500–1000)"),
    max_docs: Optional[int] = typer.Option(
        None,
        "--max-docs",
        help="Stop after N documents (smoke tests)",
    ),
    since: Optional[str] = typer.Option(
        None,
        help="Incremental: modifiedDate_tdate >= ISO timestamp, e.g. 2025-01-01T00:00:00Z",
    ),
    lookback_days: Optional[float] = typer.Option(
        None,
        "--lookback-days",
        help="Incremental window: last N days (UTC). Implies upsert by default.",
    ),
    from_watermark: bool = typer.Option(
        False,
        "--from-watermark/--no-from-watermark",
        help="Also use watermark from output *.meta.json (minus 1h safety)",
    ),
    upsert: Optional[bool] = typer.Option(
        None,
        "--upsert/--no-upsert",
        help="Merge by halId_s into existing JSONL (default: on when using a time window)",
    ),
    include_file_urls: bool = typer.Option(
        True,
        "--include-file-urls/--no-file-urls",
        help="Include fileMain_s/files_s URL fields (no download)",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Append and skip halId_s already present in the output file",
    ),
    rate: float = typer.Option(0.25, help="Minimum seconds between API requests"),
) -> None:
    """
    Harvest metadata for the latest version of each UniCA deposit.

    The HAL collection index already stores one record per halId (current version).
    Binaries are never downloaded. Time-windowed pulls upsert into the existing
    corpus by default so --since / --lookback-days never wipe the archive.
    """
    with HalClient(collection=collection, min_interval=rate) as client:
        result = harvest_metadata(
            client=client,
            output_path=output,
            rows=rows,
            max_docs=max_docs,
            since=since,
            lookback_days=lookback_days,
            from_watermark=from_watermark,
            include_file_urls=include_file_urls,
            resume=resume,
            upsert=upsert,
        )
    typer.echo(
        f"Wrote {result.written} docs "
        f"(inserted={result.inserted}, updated={result.updated}, "
        f"api numFound={result.num_found_api}, "
        f"dup_skipped={result.skipped_duplicate_hal_id}, upsert={result.upsert}) "
        f"→ {result.output_path}"
    )
    if result.since:
        typer.echo(f"Window since={result.since}")
    if result.watermark_modified:
        typer.echo(f"Watermark modifiedDate_tdate max={result.watermark_modified}")


@app.command("find-data-repos")
def find_data_repos_cmd(
    input_path: Path = typer.Option(
        Path("data/unica_hal_metadata.jsonl"),
        "--input",
        "-i",
        help="Harvested HAL metadata JSONL",
    ),
    output: Path = typer.Option(
        Path("data/unica_data_repo_links.jsonl"),
        "--output",
        "-o",
        help="JSONL report of matching records",
    ),
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection for enrich"),
    enrich: bool = typer.Option(
        True,
        "--enrich/--no-enrich",
        help="Also query HAL for relatedData_s / seeAlso_s (recommended)",
    ),
    include_network: bool = typer.Option(
        True,
        "--network/--no-network",
        help="Include RDG partner Dataverses (e.g. INRAE 10.15454)",
    ),
    include_text: bool = typer.Option(
        False,
        "--text-mentions/--no-text-mentions",
        help="Also flag weak textual mentions of Nakala / RDG in abstracts etc.",
    ),
    resolve: bool = typer.Option(
        True,
        "--resolve/--no-resolve",
        help="Resolve DOIs via DataCite for publisher / landing host / repository",
    ),
    rate: float = typer.Option(0.25, help="Min seconds between enrich API requests"),
) -> None:
    """
    Find UniCA HAL records linked to NAKALA or Research Data Gouv.

    Detects DOI prefixes / URLs in the local harvest, and by default enriches
    from HAL relatedData_s (dataset links are not in the metadata harvest).
    """
    if not input_path.exists():
        raise typer.BadParameter(f"Input not found: {input_path}")

    typer.echo(f"Scanning {input_path} …")
    hits = scan_jsonl(
        input_path,
        include_network=include_network,
        include_text_mentions=include_text,
    )
    typer.echo(f"  local matches: {len(hits)}")

    if enrich:
        typer.echo(f"Enriching from HAL collection {collection} …")
        with HalClient(collection=collection, min_interval=rate) as client:
            enriched = enrich_from_hal(
                client,
                include_network=include_network,
                include_text_mentions=include_text,
            )
        typer.echo(f"  enrich matches: {len(enriched)}")
        hits = merge_hits(hits, enriched)

    if resolve:
        typer.echo("Resolving DOIs via DataCite …")
        hits = resolve_repositories(hits, min_interval=min(rate, 0.15))

    summary = summarize(hits)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for hit in sorted(hits.values(), key=lambda h: h.hal_id):
            fh.write(json.dumps(hit_to_dict(hit), ensure_ascii=False) + "\n")

    summary_path = output.with_suffix(output.suffix + ".summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    typer.echo(f"Wrote {summary['total_hits']} hits → {output}")
    typer.echo(f"Summary → {summary_path}")
    for platform, count in summary["by_platform"].items():
        typer.echo(f"  platform:{platform}: {count}")
    for repo, count in (summary.get("by_repository") or {}).items():
        typer.echo(f"  repository:{repo}: {count}")
    for kind, count in summary.get("by_object_kind", {}).items():
        typer.echo(f"  object:{kind}: {count}")


@app.command("resolve-repos")
def resolve_repos_cmd(
    input_path: Path = typer.Option(
        Path("data/unica_data_repo_links.jsonl"),
        "--input",
        "-i",
        help="JSONL from find-data-repos",
    ),
    output: Path = typer.Option(
        Path("data/unica_data_repo_links.jsonl"),
        "--output",
        "-o",
        help="Enriched JSONL (defaults to overwrite input)",
    ),
    rate: float = typer.Option(0.15, help="Min seconds between DataCite requests"),
) -> None:
    """Resolve DOIs in an existing links file via DataCite (fine-grained repos)."""
    if not input_path.exists():
        raise typer.BadParameter(f"Input not found: {input_path}")
    typer.echo(f"Loading {input_path} …")
    hits = hits_from_jsonl(input_path)
    typer.echo(f"Resolving DOIs for {len(hits)} records …")
    hits = resolve_repositories(hits, min_interval=rate)
    summary = summarize(hits)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for hit in sorted(hits.values(), key=lambda h: h.hal_id):
            fh.write(json.dumps(hit_to_dict(hit), ensure_ascii=False) + "\n")
    summary_path = output.with_suffix(output.suffix + ".summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    typer.echo(f"Wrote {summary['total_hits']} hits → {output}")
    for repo, count in (summary.get("by_repository") or {}).items():
        typer.echo(f"  {repo}: {count}")
    for kind, count in summary.get("by_object_kind", {}).items():
        typer.echo(f"  object:{kind}: {count}")


@app.command("report")
def report_cmd(
    input_path: Path = typer.Option(
        Path("data/unica_data_repo_links.jsonl"),
        "--input",
        "-i",
        help="JSONL from find-data-repos",
    ),
    output: Path = typer.Option(
        Path("web/data-repo-links.html"),
        "--output",
        "-o",
        help="Self-contained HTML report",
    ),
) -> None:
    """Build a browsable HTML page from find-data-repos results."""
    if not input_path.exists():
        raise typer.BadParameter(f"Input not found: {input_path}")
    summary_path = input_path.with_suffix(input_path.suffix + ".summary.json")
    path = write_report(input_path, summary_path, output)
    typer.echo(f"Wrote {path}")


@app.command("census")
def census_cmd(
    out_dir: Path = typer.Option(
        Path("data/census"),
        "--out-dir",
        "-o",
        help="Directory for census JSONL/CSV/JSON/MD artifacts",
    ),
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection code"),
    rate: float = typer.Option(0.15, help="Min seconds between HAL/DataCite requests"),
    log_file: Path = typer.Option(
        Path("logs/census.log"),
        "--log",
        help="Run log path",
    ),
    since: Optional[str] = typer.Option(
        None,
        help="Incremental: only HAL notices with modifiedDate_tdate >= ISO timestamp",
    ),
    lookback_days: Optional[float] = typer.Option(
        None,
        "--lookback-days",
        help="Incremental window in days (UTC); merges into existing census artifacts",
    ),
    from_watermark: bool = typer.Option(
        False,
        "--from-watermark/--no-from-watermark",
        help="Combine with watermark from census.meta.json",
    ),
    full: bool = typer.Option(
        False,
        "--full/--incremental",
        help="Ignore date filters and rebuild the census from HAL (still reuses DOI cache unless --no-doi-cache)",
    ),
    reuse_doi_cache: bool = typer.Option(
        True,
        "--doi-cache/--no-doi-cache",
        help="Reuse doi_resolutions.jsonl and only resolve new DOIs",
    ),
) -> None:
    """
    Census ALL relatedData repositories (not only Nakala/RDG).

    Writes DOI↔repository maps, publication JSONL, summary, methodology, and a log.
    With --lookback-days / --since, merges into existing publications by halId_s.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_since: Optional[str] = None
    existing_pubs = None
    existing_res = None

    if not full:
        wm = read_watermark(out_dir / "census.meta.json") if from_watermark else None
        resolved_since = effective_since(
            since=since,
            lookback_days=lookback_days,
            watermark=wm,
        )
        if resolved_since is not None or lookback_days is not None or since:
            existing_pubs = load_publications_jsonl(out_dir / "publications_related_data.jsonl")
        if reuse_doi_cache:
            existing_res = load_doi_resolutions_jsonl(out_dir / "doi_resolutions.jsonl")
    elif reuse_doi_cache:
        existing_res = load_doi_resolutions_jsonl(out_dir / "doi_resolutions.jsonl")

    with log_file.open("w", encoding="utf-8") as log, HalClient(
        collection=collection, min_interval=rate
    ) as client, DataCiteClient(min_interval=rate) as datacite:
        census = run_census(
            client=client,
            datacite=datacite,
            log=log,
            since=None if full else resolved_since,
            existing_publications=None if full else existing_pubs,
            existing_resolutions=existing_res,
        )
        paths = write_census_artifacts(census, out_dir, log_file)
    with log_file.open("a", encoding="utf-8") as log:
        log.write("artifacts:\n")
        for key, path in paths.items():
            log.write(f"  {key}: {path}\n")
    summary = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    typer.echo(f"Census complete → {out_dir}/")
    typer.echo(f"  publications: {summary['hal_publications_with_relatedData']}")
    typer.echo(f"  unique DOIs: {summary['unique_dois_resolved']}")
    if not full and resolved_since:
        typer.echo(f"  since: {resolved_since}")
        inc = summary.get("incremental") or {}
        typer.echo(
            f"  fetched={inc.get('pubs_fetched')} "
            f"updated={inc.get('pubs_updated')} inserted={inc.get('pubs_inserted')} "
            f"datacite_live={inc.get('dois_resolved_live')} cache={inc.get('dois_from_cache')}"
        )
    typer.echo(f"  log: {log_file}")
    for repo, count in list(summary.get("by_repository", {}).items())[:15]:
        typer.echo(f"  {repo}: {count}")


@app.command("software")
def software_cmd(
    out_dir: Path = typer.Option(
        Path("data/census"),
        "--out-dir",
        "-o",
        help="Directory for software artifacts (default: data/census)",
    ),
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection code"),
    rate: float = typer.Option(0.2, help="Min seconds between HAL requests"),
) -> None:
    """Harvest HAL SOFTWARE deposits (code repos, SWHIDs, related publications)."""
    with HalClient(collection=collection, min_interval=rate) as client:
        rows = harvest_software(client)
    paths = write_software_artifacts(rows, out_dir)
    summary = json.loads(paths["software_summary"].read_text(encoding="utf-8"))
    typer.echo(f"SOFTWARE deposits: {summary['software_deposits']}")
    typer.echo(f"  with SWHID: {summary['with_swhid']}")
    typer.echo(f"  with code repository URL: {summary['with_code_repository']}")
    typer.echo(f"  with related publication: {summary['with_related_publication']}")
    typer.echo(f"Wrote → {out_dir}/")


@app.command("refresh")
def refresh_cmd(
    lookback_days: float = typer.Option(
        2.0,
        "--lookback-days",
        help="Pull HAL notices modified in the last N days (default: 2)",
    ),
    since: Optional[str] = typer.Option(
        None,
        help="Override lookback with an explicit modifiedDate lower bound",
    ),
    full: bool = typer.Option(
        False,
        "--full/--incremental",
        help="Full relatedData rebuild (weekly safety net); still reuses DOI cache",
    ),
    census_dir: Path = typer.Option(Path("data/census"), "--census-dir"),
    links: Path = typer.Option(
        Path("data/unica_data_repo_links.jsonl"),
        "--links",
        help="Nakala/RDG focus links (synced from census)",
    ),
    harvest: Path = typer.Option(
        Path("data/unica_hal_metadata.jsonl"),
        "--harvest",
        help="Optional full harvest JSONL for home-page stats",
    ),
    stats_fallback: Path = typer.Option(
        Path("docs/data/stats.json"),
        "--stats-fallback",
        help="Reuse harvest stats when full harvest JSONL is missing (CI)",
    ),
    output: Path = typer.Option(Path("docs"), "--output", "-o", help="Site output dir"),
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection code"),
    rate: float = typer.Option(0.15, help="Min seconds between HAL/DataCite requests"),
    log_file: Path = typer.Option(Path("logs/census.log"), "--log"),
) -> None:
    """
    Daily incremental refresh: census (lookback) → software → focus links → site.

    Does not re-scrape the full UniCA metadata corpus. Designed for scheduled CI.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as log:
        result = run_refresh(
            collection=collection,
            census_dir=census_dir,
            links_path=links,
            harvest_path=harvest,
            stats_fallback=stats_fallback if stats_fallback.exists() else None,
            site_dir=output,
            lookback_days=lookback_days,
            since=since,
            full=full,
            rate=rate,
            log_path=log_file,
            log=log,
        )
    typer.echo(
        f"Refresh done (full={result.full}, since={result.since or '*'}) "
        f"pubs={result.census_publications} fetched={result.pubs_fetched} "
        f"datacite_live={result.dois_resolved_live} cache={result.dois_from_cache} "
        f"software={result.software_deposits} focus={result.focus_hits} → {result.site_dir}"
    )


@app.command("build-site")
def build_site_cmd(
    harvest: Path = typer.Option(
        Path("data/unica_hal_metadata.jsonl"),
        "--harvest",
        help="Full HAL metadata JSONL (for general statistics); optional if stats fallback exists",
    ),
    links: Path = typer.Option(
        Path("data/unica_data_repo_links.jsonl"),
        "--links",
        help="Resolved Nakala/RDG links JSONL",
    ),
    census_dir: Path = typer.Option(
        Path("data/census"),
        "--census-dir",
        help="Full relatedData census directory (optional if missing)",
    ),
    output: Path = typer.Option(
        Path("docs"),
        "--output",
        "-o",
        help="GitHub Pages output directory",
    ),
    stats_fallback: Path = typer.Option(
        Path("docs/data/stats.json"),
        "--stats-fallback",
        help="Fallback harvest stats when --harvest is missing",
    ),
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection code"),
) -> None:
    """Build the public stats + related-datasets + census site into docs/."""
    if not links.exists():
        raise typer.BadParameter(f"Links file not found: {links}")
    if not harvest.exists() and not stats_fallback.exists():
        raise typer.BadParameter(
            f"Harvest not found: {harvest} (and no stats fallback at {stats_fallback})"
        )

    if census_dir.exists():
        pubs = census_dir / "publications_related_data.jsonl"
        if pubs.exists():
            build_dataset_to_publications(pubs, census_dir)
            typer.echo("Updated dataset→publications index")

    path = write_site(
        harvest_path=harvest if harvest.exists() else None,
        links_path=links,
        output_dir=output,
        collection=collection,
        census_dir=census_dir if census_dir.exists() else None,
        stats_fallback=stats_fallback if stats_fallback.exists() else None,
    )
    typer.echo(f"Wrote site → {path}/")
    for name in (
        "index.html",
        "embed-chart.html",
        "related-datasets.html",
        "all-repositories.html",
        "to-be-corrected.html",
        "software.html",
        "documentation.html",
    ):
        if (path / name).exists():
            typer.echo(f"  {path / name}")


@app.callback()
def main(version: bool = typer.Option(False, "--version", help="Show version")) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


if __name__ == "__main__":
    app()
