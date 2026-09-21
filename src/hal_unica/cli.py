from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .census import run_census, write_census_artifacts
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
from .report import write_report
from .software import (
    build_dataset_to_publications,
    harvest_software,
    write_software_artifacts,
)
from .site import write_site

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
) -> None:
    """Print how many documents the API reports for the collection."""
    fq = [f"modifiedDate_tdate:[{since} TO *]"] if since else None
    with HalClient(collection=collection) as client:
        n = client.count(fq=fq)
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
    Binaries are never downloaded.
    """
    with HalClient(collection=collection, min_interval=rate) as client:
        result = harvest_metadata(
            client=client,
            output_path=output,
            rows=rows,
            max_docs=max_docs,
            since=since,
            include_file_urls=include_file_urls,
            resume=resume,
        )
    typer.echo(
        f"Wrote {result.written} docs "
        f"(api numFound={result.num_found_api}, "
        f"dup_skipped={result.skipped_duplicate_hal_id}) → {result.output_path}"
    )
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
) -> None:
    """
    Census ALL relatedData repositories (not only Nakala/RDG).

    Writes DOI↔repository maps, publication JSONL, summary, methodology, and a log.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as log, HalClient(
        collection=collection, min_interval=rate
    ) as client, DataCiteClient(min_interval=rate) as datacite:
        census = run_census(client=client, datacite=datacite, log=log)
        paths = write_census_artifacts(census, out_dir, log_file)
    # append artifact list to log
    with log_file.open("a", encoding="utf-8") as log:
        log.write("artifacts:\n")
        for key, path in paths.items():
            log.write(f"  {key}: {path}\n")
    summary = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    typer.echo(f"Census complete → {out_dir}/")
    typer.echo(f"  publications: {summary['hal_publications_with_relatedData']}")
    typer.echo(f"  unique DOIs: {summary['unique_dois_resolved']}")
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


@app.command("build-site")
def build_site_cmd(
    harvest: Path = typer.Option(
        Path("data/unica_hal_metadata.jsonl"),
        "--harvest",
        help="Full HAL metadata JSONL (for general statistics)",
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
    collection: str = typer.Option(DEFAULT_COLLECTION, help="HAL collection code"),
) -> None:
    """Build the public stats + related-datasets + census site into docs/."""
    if not harvest.exists():
        raise typer.BadParameter(f"Harvest not found: {harvest}")
    if not links.exists():
        raise typer.BadParameter(f"Links file not found: {links}")

    if census_dir.exists():
        pubs = census_dir / "publications_related_data.jsonl"
        if pubs.exists():
            build_dataset_to_publications(pubs, census_dir)
            typer.echo("Updated dataset→publications index")

    path = write_site(
        harvest_path=harvest,
        links_path=links,
        output_dir=output,
        collection=collection,
        census_dir=census_dir if census_dir.exists() else None,
    )
    typer.echo(f"Wrote site → {path}/")
    for name in (
        "index.html",
        "related-datasets.html",
        "all-repositories.html",
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
