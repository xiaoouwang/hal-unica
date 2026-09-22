"""Build the public GitHub Pages site (stats + related-dataset publications)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data_repos import hits_from_jsonl, summarize


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def harvest_stats(harvest_path: Path) -> dict[str, Any]:
    types: Counter[str] = Counter()
    years: Counter[int] = Counter()
    n = 0
    with_doi = 0
    with open(harvest_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            n += 1
            types[doc.get("docType_s") or "UNKNOWN"] += 1
            if doc.get("doiId_s"):
                with_doi += 1
            y = doc.get("producedDateY_i")
            if y is not None:
                try:
                    years[int(y)] += 1
                except (TypeError, ValueError):
                    pass
    top_types = [{"type": k, "count": v} for k, v in types.most_common(12)]
    # Always surface SOFTWARE even when it falls outside the top 12
    if "SOFTWARE" in types and not any(t["type"] == "SOFTWARE" for t in top_types):
        top_types.append({"type": "SOFTWARE", "count": types["SOFTWARE"]})
    year_series = [{"year": y, "count": years[y]} for y in sorted(years) if 1950 <= y <= 2026]
    return {
        "documents": n,
        "with_doi": with_doi,
        "doi_share": round(with_doi / n, 4) if n else 0,
        "doc_types": top_types,
        "software_deposits": types.get("SOFTWARE", 0),
        "years": year_series,
        "year_min": min(years) if years else None,
        "year_max": max(y for y in years if y <= 2026) if years else None,
    }


def load_harvest_stats_fallback(path: Path | None) -> dict[str, Any] | None:
    """Reuse harvest block from a previous stats.json when the full JSONL is absent."""
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    harvest = data.get("harvest") if isinstance(data, dict) else None
    return harvest if isinstance(harvest, dict) else None


def related_dataset_publications(links_path: Path) -> list[dict[str, Any]]:
    """HAL notices that link to a real data repository (any tracked HAL field)."""
    out: list[dict[str, Any]] = []
    for hit in hits_from_jsonl(links_path).values():
        related = [
            e
            for e in hit.evidence
            if e.object_kind == "dataset_repo"
            and e.kind in {"related_data", "related_publication", "see_also", "doi_in_field"}
        ]
        if not related:
            continue
        repos = []
        for e in related:
            if e.repository and e.repository not in repos:
                repos.append(e.repository)
        out.append(
            {
                "halId_s": hit.hal_id,
                "uri_s": hit.uri,
                "title_s": hit.title,
                "docType_s": hit.doc_type,
                "doiId_s": hit.doi,
                "laboratories": list(hit.laboratories or []),
                "modifiedDate_tdate": hit.modifiedDate_tdate,
                "producedDateY_i": hit.producedDateY_i,
                "repositories": repos,
                "datasets": [
                    {
                        "doi": e.value,
                        "repository": e.repository,
                        "publisher": e.publisher,
                        "landing_url": e.landing_url,
                        "landing_host": e.landing_host,
                        "dataset_title": e.dataset_title,
                        "field": e.field,
                        "misfiled": bool(e.misfiled_dataset_link),
                        "also_in_relatedData_s": bool(e.also_in_relatedData_s),
                    }
                    for e in related
                ],
            }
        )
    out.sort(
        key=lambda r: (r.get("modifiedDate_tdate") or "", (r.get("title_s") or "").lower()),
        reverse=True,
    )
    return out


# Bright stacked-bar palette (BSO-like contrast; last reserved for Autre)
_STACK_COLORS = [
    "#e85d75",  # rose
    "#f4a261",  # apricot
    "#e76f51",  # coral
    "#2a9d8f",  # teal
    "#4cc9f0",  # sky
    "#90be6d",  # lime
    "#f9c74f",  # gold
    "#577590",  # steel blue
    "#f28482",  # salmon
    "#43aa8b",  # green
    "#9b5de5",  # violet accent (sparingly)
    "#00bbf9",  # bright blue
    "#fee440",  # yellow
    "#adb5bd",  # Autre grey
]


def census_homepage_stats(
    census_dir: Path,
    *,
    year_min: int = 2016,
    top_repos: int = 12,
) -> dict[str, Any] | None:
    """
    All-repository dataset stats for the homepage (not Nakala/RDG-only).

    Years use the newest ``producedDateY_i`` among UniCA HAL notices that link
    each dataset DOI (one count per dataset DOI).
    """
    ds_path = census_dir / "dataset_to_publications.jsonl"
    pubs_path = census_dir / "publications_related_data.jsonl"
    if not ds_path.exists():
        return None

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

    by_year_repo: dict[int, Counter[str]] = defaultdict(Counter)
    by_repo: Counter[str] = Counter()
    pubs_with_dataset: set[str] = set()
    datasets = 0

    with ds_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            datasets += 1
            repo = row.get("repository") or "Unknown"
            by_repo[repo] += 1
            years: list[int] = []
            for p in row.get("publications") or []:
                hid = p.get("halId_s")
                if hid:
                    pubs_with_dataset.add(str(hid))
                pub = pubs_by_id.get(str(hid)) if hid else None
                y = (pub or {}).get("producedDateY_i")
                if y is None:
                    y = p.get("producedDateY_i")
                try:
                    yi = int(y)
                except (TypeError, ValueError):
                    continue
                if 1950 <= yi <= 2100:
                    years.append(yi)
            if not years:
                continue
            by_year_repo[max(years)][repo] += 1

    if not by_year_repo:
        years_list = list(range(year_min, datetime.now(timezone.utc).year + 1))
    else:
        years_list = list(range(min(by_year_repo), max(by_year_repo) + 1))

    # Top repositories overall; remainder → Autre (still counted)
    ranked = [r for r, _ in by_repo.most_common()]
    keep = ranked[:top_repos]
    other_label = "Autre"
    series_names = keep + ([other_label] if len(ranked) > len(keep) else [])

    series: list[dict[str, Any]] = []
    for i, name in enumerate(series_names):
        counts: list[int] = []
        for y in years_list:
            if name == other_label:
                counts.append(
                    sum(c for r, c in by_year_repo[y].items() if r not in keep)
                )
            else:
                counts.append(int(by_year_repo[y].get(name, 0)))
        color = (
            "#adb5bd"
            if name == other_label
            else _STACK_COLORS[i % (len(_STACK_COLORS) - 1)]
        )
        series.append(
            {
                "repository": name,
                "color": color,
                "counts": counts,
            }
        )

    totals = [sum(s["counts"][i] for s in series) for i in range(len(years_list))]

    return {
        "unique_datasets": datasets,
        "publications_with_dataset": len(pubs_with_dataset),
        "by_repository": dict(sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))),
        "repositories_in_chart": len(keep),
        "repositories_total": len(by_repo),
        "year_axis": years_list,
        "stacked": {
            "years": years_list,
            "totals": totals,
            "series": series,
        },
        "note": (
            "Unique dataset DOIs linked from UniCA HAL notices, by year of the "
            "newest linking publication (producedDateY_i). All data repositories; "
            f"chart shows top {len(keep)} plus Autre."
        ),
    }


def build_site_payload(
    *,
    harvest_path: Path | None,
    links_path: Path,
    collection: str = "UNIV-COTEDAZUR",
    stats_fallback: Path | None = None,
    census_dir: Path | None = None,
) -> dict[str, Any]:
    if harvest_path and harvest_path.exists():
        harvest = harvest_stats(harvest_path)
    else:
        harvest = load_harvest_stats_fallback(stats_fallback) or {
            "documents": 0,
            "with_doi": 0,
            "doi_share": 0,
            "doc_types": [],
            "software_deposits": 0,
            "years": [],
            "year_min": None,
            "year_max": None,
            "stale": True,
        }
        if harvest and "stale" not in harvest:
            harvest = {**harvest, "stale": True}

    hits = hits_from_jsonl(links_path)
    link_summary = summarize(hits)
    related = related_dataset_publications(links_path)
    related_repos: Counter[str] = Counter()
    for row in related:
        for repo in row.get("repositories") or []:
            related_repos[repo] += 1

    census_stats = census_homepage_stats(census_dir) if census_dir else None

    focus_by_repo = dict(
        sorted(related_repos.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    data_by_repo = (
        census_stats["by_repository"]
        if census_stats
        else (link_summary.get("by_repository") or focus_by_repo)
    )

    return {
        "generated_at": _utc_now(),
        "collection": collection,
        "collection_url": f"https://hal.science/{collection}",
        "harvest": harvest,
        "data_links": {
            "total_hits": (
                census_stats["unique_datasets"]
                if census_stats
                else link_summary["total_hits"]
            ),
            "by_platform": link_summary.get("by_platform") or {},
            "by_repository": data_by_repo,
            "by_object_kind": link_summary.get("by_object_kind") or {},
            "scope": "all_repositories" if census_stats else "focus_fallback",
        },
        # Nakala / RDG focus page payload (unchanged scope)
        "related_datasets": {
            "publication_count": len(related),
            "by_repository": focus_by_repo,
            "publications": related,
            "scope": "nakala_rdg_focus",
        },
        "census_chart": census_stats,
    }


SHARED_CSS = """
:root {
  --ink: #161513;
  --ink-soft: #6a6560;
  --paper: #f1f0ed;
  --surface: #fbfaf8;
  --accent: #2a2622;
  --accent-hover: #8a6a45;
  --wash: #e8e4dc;
  --line: rgba(22, 21, 19, 0.1);
  --radius: 12px;
  --font-display: "Syne", "Avenir Next", sans-serif;
  --font-body: "Figtree", "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; color: var(--ink); font-family: var(--font-body);
  background:
    radial-gradient(1100px 520px at 8% -8%, #e7e2d8 0%, transparent 58%),
    radial-gradient(900px 480px at 100% 0%, #ddd8cf 0%, transparent 52%),
    linear-gradient(180deg, #f5f3ef 0%, var(--paper) 40%, #ebe8e2 100%);
  min-height: 100vh;
}
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 0.15em; }
a:hover { color: var(--accent-hover); }
.wrap { width: min(1100px, calc(100% - 2rem)); margin: 0 auto; padding: 1.5rem 0 4rem; }
nav {
  display: flex; gap: 0.45rem; flex-wrap: wrap; align-items: center;
  margin-bottom: 1.75rem; padding-bottom: 0.9rem; border-bottom: 1px solid var(--line);
}
nav .brand {
  font-family: var(--font-display); font-weight: 700; font-size: 1.2rem;
  letter-spacing: -0.03em; margin-right: auto; text-decoration: none; color: var(--ink);
}
nav a.navlink {
  text-decoration: none; color: var(--ink-soft); font-weight: 500; font-size: 0.9rem;
  padding: 0.38rem 0.7rem; border-radius: 8px; border: 1px solid transparent;
}
nav a.navlink:hover, nav a.navlink[aria-current="page"] {
  color: var(--ink); background: rgba(255,255,255,0.75); border-color: var(--line);
}
.eyebrow {
  font-size: 0.75rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent-hover);
}
h1 {
  margin: 0.4rem 0 0; font-family: var(--font-display); font-weight: 700;
  font-size: clamp(2rem, 4.5vw, 3rem); line-height: 1.05; letter-spacing: -0.035em;
}
.lede { margin: 0.9rem 0 0; max-width: 42rem; color: var(--ink-soft); line-height: 1.55; font-size: 1.05rem; }
.stats {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; margin: 1.5rem 0;
}
@media (max-width: 720px) { .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.stat {
  background: rgba(251,250,248,0.8); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 1rem 1.1rem; backdrop-filter: blur(8px);
}
.stat strong {
  display: block; font-family: var(--font-display); font-size: 1.85rem; font-weight: 700;
  line-height: 1; letter-spacing: -0.03em;
}
.stat span { display: block; margin-top: 0.4rem; font-size: 0.8rem; color: var(--ink-soft); }
.panel {
  background: rgba(251,250,248,0.85); border: 1px solid var(--line);
  border-radius: calc(var(--radius) + 2px); padding: 1.1rem 1.15rem; margin: 1rem 0;
  backdrop-filter: blur(10px);
}
.panel h2 {
  margin: 0 0 0.75rem; font-family: var(--font-display); font-size: 1.2rem; font-weight: 700;
  letter-spacing: -0.02em;
}
.bars { display: grid; gap: 0.45rem; }
.bar-row { display: grid; grid-template-columns: 7.5rem 1fr 3.2rem; gap: 0.6rem; align-items: center; font-size: 0.9rem; }
.bar-track { height: 0.5rem; background: var(--wash); border-radius: 999px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 999px; }
.bar-row span:last-child { text-align: right; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
.muted { color: var(--ink-soft); font-size: 0.88rem; }
.stack-wrap { margin-top: 0.75rem; }
.stack-legend {
  display: flex; flex-wrap: wrap; gap: 0.45rem 0.9rem; margin: 0 0 1rem;
  font-size: 0.82rem; color: var(--ink-soft);
}
.stack-legend .stack-legend-item {
  appearance: none; border: 0; background: transparent; font: inherit;
  display: inline-flex; align-items: center; gap: 0.35rem;
  cursor: pointer; border-radius: 6px; padding: 0.15rem 0.35rem;
  color: inherit;
  transition: opacity 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.stack-legend .stack-legend-item:hover,
.stack-wrap.is-filtering .stack-legend-item.is-active {
  color: var(--ink); background: rgba(42,38,34,0.06);
}
.stack-wrap.is-filtering .stack-legend-item:not(.is-active) { opacity: 0.35; }
.stack-swatch {
  width: 0.7rem; height: 0.7rem; border-radius: 3px; flex: 0 0 auto;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.08);
}
.stack-chart {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(2.4rem, 1fr));
  gap: 0.45rem; align-items: end; min-height: 16rem;
  padding: 0.25rem 0 0;
  border-bottom: 1px solid var(--line);
}
.stack-col {
  display: flex; flex-direction: column; align-items: center; gap: 0.35rem;
  min-width: 0;
}
.stack-total {
  font-family: var(--font-display); font-weight: 700; font-size: 0.85rem;
  letter-spacing: -0.02em; color: var(--ink);
}
.stack-bars {
  width: 100%; max-width: 2.75rem; height: 14rem;
  display: flex; flex-direction: column-reverse; justify-content: flex-start;
  border-radius: 4px 4px 0 0; overflow: hidden; background: var(--wash);
}
.stack-seg {
  width: 100%; display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 0.68rem; font-weight: 700; font-variant-numeric: tabular-nums;
  min-height: 0; cursor: pointer;
  transition: opacity 0.15s ease, filter 0.15s ease, box-shadow 0.15s ease;
  text-shadow: 0 1px 1px rgba(0,0,0,0.25);
}
.stack-seg:hover,
.stack-wrap.is-filtering .stack-seg.is-active {
  filter: brightness(1.08); box-shadow: inset 0 0 0 2px rgba(255,255,255,0.85);
  z-index: 1;
}
.stack-wrap.is-filtering .stack-seg:not(.is-active) { opacity: 0.18; filter: grayscale(0.35); }
.stack-year {
  font-size: 0.78rem; color: var(--ink-soft); font-variant-numeric: tabular-nums;
}
.search {
  width: 100%; border: 1px solid var(--line); border-radius: 10px;
  padding: 0.85rem 1.1rem; font: inherit; background: var(--surface); outline: none; margin-bottom: 0.75rem;
}
.search:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(42,38,34,0.1); }
.filters { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }
.toolbar {
  display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem; align-items: center;
  justify-content: space-between; margin: 0.15rem 0 0.85rem;
}
.toolbar-controls { display: flex; flex-wrap: wrap; gap: 0.65rem 1rem; align-items: center; }
.toolbar-label {
  display: inline-flex; align-items: center; gap: 0.45rem;
  color: var(--ink-soft); font-size: 0.9rem;
}
.toolbar select, .toolbar input[type="search"].lab-filter {
  border: 1px solid var(--line); border-radius: 8px; background: var(--surface);
  color: var(--ink); font: inherit; font-size: 0.9rem; padding: 0.4rem 0.65rem;
}
.toolbar input[type="search"].lab-filter { min-width: 11rem; margin: 0; }
.toolbar select.lab-select { max-width: 14rem; }
.chip {
  appearance: none; border: 1px solid var(--line); background: var(--surface); color: var(--ink-soft);
  border-radius: 8px; padding: 0.4rem 0.75rem; font: inherit; font-size: 0.84rem;
  font-weight: 500; cursor: pointer;
}
.chip[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: #faf9f7; }
.list { display: grid; gap: 0.65rem; }
.result {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 1rem 1.1rem; display: grid; gap: 0.65rem;
}
.title-row { display: flex; gap: 0.75rem; justify-content: space-between; align-items: start; }
.title {
  margin: 0; font-family: var(--font-display); font-size: 1.05rem; font-weight: 700;
  line-height: 1.3; letter-spacing: -0.02em;
}
.doi-annot {
  display: block; margin: 0 0 0.35rem; font-size: 0.8rem; font-weight: 500;
  color: var(--ink-soft); letter-spacing: 0.02em;
}
.badges { display: flex; flex-wrap: wrap; gap: 0.35rem; justify-content: flex-end; max-width: 42%; }
.badge {
  font-size: 0.7rem; font-weight: 600; padding: 0.28rem 0.55rem; border-radius: 6px;
  background: var(--wash); color: var(--accent); border: 1px solid var(--line);
}
.sub { display: flex; flex-wrap: wrap; gap: 0.55rem 1rem; font-size: 0.86rem; color: var(--ink-soft); }
.sub code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem;
  background: var(--paper); padding: 0.1rem 0.35rem; border-radius: 4px;
}
.evidence {
  border-top: 1px solid var(--line); padding-top: 0.75rem; display: grid; gap: 0.5rem;
}
.ev {
  display: grid; grid-template-columns: 6.5rem 1fr; gap: 0.75rem; font-size: 0.9rem;
  padding: 0.55rem 0.65rem; border-radius: 8px; background: #f3f1ec;
}
@media (max-width: 640px) {
  .ev { grid-template-columns: 1fr; }
  .badges { max-width: 100%; justify-content: flex-start; }
}
.ev dt {
  margin: 0; font-weight: 650; color: var(--ink-soft); font-size: 0.72rem;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.ev dd { margin: 0; word-break: break-word; }
.meta-row { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin: 0.5rem 0 0.85rem; color: var(--ink-soft); font-size: 0.92rem; }
footer { margin-top: 2rem; font-size: 0.82rem; color: var(--ink-soft); line-height: 1.5; }
footer .updated { font-weight: 600; color: var(--ink); margin-bottom: 0.35rem; }
footer .updated time { font-variant-numeric: tabular-nums; }
.empty { padding: 2rem; text-align: center; color: var(--ink-soft); }
"""


def _format_last_updated(iso: str | None) -> str:
    """Human-readable UTC stamp for footers."""
    if not iso:
        return "Last updated: unknown"
    text = iso.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text).astimezone(timezone.utc)
        return f"Last updated: {dt.strftime('%d %b %Y, %H:%M')} UTC"
    except ValueError:
        return f"Last updated: {iso}"


def _list_toolbar_html(*, sort_options_html: str) -> str:
    return f"""
      <div class="toolbar">
        <div id="count"></div>
        <div class="toolbar-controls">
          <label class="toolbar-label" for="sort">
            Sort by
            <select id="sort">{sort_options_html}</select>
          </label>
          <label class="toolbar-label" for="yearSelect">
            Year
            <select id="yearSelect" class="lab-select">
              <option value="">All years</option>
            </select>
          </label>
          <label class="toolbar-label" for="labSelect">
            Laboratory
            <select id="labSelect" class="lab-select">
              <option value="">All laboratories</option>
            </select>
          </label>
          <label class="toolbar-label" for="labSearch">
            <input id="labSearch" class="lab-filter" type="search" list="labList"
              placeholder="Type lab prefix…" autocomplete="off" />
            <datalist id="labList"></datalist>
          </label>
        </div>
      </div>"""


def _shared_list_helpers_js() -> str:
    """Plain JS helpers shared by list pages (safe to inject into an f-string)."""
    return r"""
    function esc(s) {
      return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    }
    function formatStamp(iso) {
      if (!iso) return "";
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return esc(iso);
      return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
        + ", " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" })
        + " UTC";
    }
    function cmpStr(a, b) {
      return String(a || "").localeCompare(String(b || ""), undefined, { sensitivity: "base" });
    }
    function cmpIsoDesc(a, b) { return String(b || "").localeCompare(String(a || "")); }
    function cmpIsoAsc(a, b) { return String(a || "").localeCompare(String(b || "")); }
    function uniqueLabs(items, getLabs) {
      const set = new Set();
      for (const item of items) {
        for (const lab of (getLabs(item) || [])) {
          if (lab) set.add(String(lab));
        }
      }
      return [...set].sort((a, b) => cmpStr(a, b));
    }
    function uniqueYears(items, getYears) {
      const set = new Set();
      for (const item of items) {
        for (const y of (getYears(item) || [])) {
          const n = Number(y);
          if (Number.isFinite(n) && n > 0) set.add(n);
        }
      }
      return [...set].sort((a, b) => b - a);
    }
    function paintYearControls(allYears) {
      const sel = document.getElementById("yearSelect");
      if (!sel) return;
      const current = sel.value;
      sel.innerHTML = `<option value="">All years</option>` +
        allYears.map(y => `<option value="${y}">${y}</option>`).join("");
      if (current && [...sel.options].some(o => o.value === current)) sel.value = current;
    }
    function activeYearFilter() {
      const sel = document.getElementById("yearSelect");
      return sel ? (sel.value || "").trim() : "";
    }
    function yearsMatch(years, filter) {
      if (!filter) return true;
      const want = Number(filter);
      return (years || []).some(y => Number(y) === want);
    }
    function yearLine(years) {
      const list = [...new Set((years || []).map(y => Number(y)).filter(y => Number.isFinite(y) && y > 0))]
        .sort((a, b) => b - a);
      if (!list.length) return "";
      const label = list.length === 1 ? "Publication year" : "Publication years";
      return `<div class="muted" style="margin-top:0.2rem;font-size:0.8rem">${label}: ${esc(list.join(" · "))}</div>`;
    }
    function paintLabControls(allLabs) {
      const sel = document.getElementById("labSelect");
      const dl = document.getElementById("labList");
      const typed = (document.getElementById("labSearch").value || "").trim().toLowerCase();
      const forSelect = !typed
        ? allLabs
        : allLabs.filter(l => l.toLowerCase().startsWith(typed) || l.toLowerCase().includes(typed));
      const forSuggest = !typed
        ? allLabs
        : allLabs.filter(l => l.toLowerCase().startsWith(typed));
      const current = sel.value;
      sel.innerHTML = `<option value="">All laboratories</option>` +
        forSelect.map(l => `<option value="${esc(l)}">${esc(l)}</option>`).join("");
      if (current && [...sel.options].some(o => o.value === current)) sel.value = current;
      else if (typed && forSelect.some(l => l.toLowerCase() === typed)) {
        const exact = forSelect.find(l => l.toLowerCase() === typed);
        if (exact) sel.value = exact;
      }
      dl.innerHTML = forSuggest.slice(0, 80).map(l => `<option value="${esc(l)}"></option>`).join("");
    }
    function activeLabFilter() {
      const sel = (document.getElementById("labSelect").value || "").trim();
      const typed = (document.getElementById("labSearch").value || "").trim();
      return sel || typed;
    }
    function labsMatch(labs, filter) {
      if (!filter) return true;
      const q = filter.toLowerCase();
      const list = labs || [];
      if (list.some(l => String(l).toLowerCase() === q)) return true;
      return list.some(l => String(l).toLowerCase().startsWith(q));
    }
    function labsLine(labs, limit) {
      const list = (labs || []).filter(Boolean);
      if (!list.length) return "";
      const shown = list.slice(0, limit || 12);
      const more = list.length > shown.length ? "…" : "";
      return `<div class="muted" style="margin-top:0.2rem;font-size:0.8rem">Labs: ${esc(shown.join(" · "))}${more}</div>`;
    }
    function wireLabControls(onChange) {
      const sel = document.getElementById("labSelect");
      const search = document.getElementById("labSearch");
      const yearSel = document.getElementById("yearSelect");
      sel.addEventListener("change", () => {
        if (sel.value) search.value = sel.value;
        onChange();
      });
      search.addEventListener("input", () => {
        const t = search.value.trim().toLowerCase();
        if (!t) sel.value = "";
        else {
          const match = [...sel.options].find(o => o.value && o.value.toLowerCase() === t);
          sel.value = match ? match.value : "";
        }
        onChange();
      });
      if (yearSel) yearSel.addEventListener("change", onChange);
    }
    """


def _footer(generated_at: str | None, extra_html: str = "") -> str:
    stamp = _format_last_updated(generated_at)
    iso = (generated_at or "").strip()
    time_attr = f' datetime="{iso}"' if iso else ""
    label = stamp.replace("Last updated: ", "", 1) if stamp.startswith("Last updated: ") else stamp
    block = (
        f'<div class="updated">Last updated: <time{time_attr}>{label}</time></div>'
    )
    if extra_html:
        return f"<footer>\n      {block}\n      {extra_html}\n    </footer>"
    return f"<footer>\n      {block}\n    </footer>"


def _nav(active: str) -> str:
    def link(href: str, label: str, key: str) -> str:
        cur = ' aria-current="page"' if key == active else ""
        return f'<a class="navlink" href="{href}"{cur}>{label}</a>'

    return f"""
    <nav>
      <a class="brand" href="./index.html">HAL-UniCA</a>
      {link("./index.html", "Statistics", "stats")}
      {link("./related-datasets.html", "Nakala / RDG", "related")}
      {link("./all-repositories.html", "All repositories", "census")}
      {link("./to-be-corrected.html", "To Be Corrected", "corrections")}
      {link("./software.html", "Software", "software")}
      {link("./documentation.html", "Documentation", "docs")}
    </nav>
    """


def render_index(payload_json: str, *, generated_at: str | None = None) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HAL-UniCA · Statistics</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700&display=swap" rel="stylesheet" />
  <style>{SHARED_CSS}</style>
</head>
<body>
  <main class="wrap">
    {_nav("stats")}
    <div class="eyebrow">Université Côte d’Azur · HAL</div>
    <h1>Open science snapshot</h1>
    <p class="lede">
      Metadata harvest of the institutional HAL collection
      <a id="collectionLink" href="https://hal.science/UNIV-COTEDAZUR">UNIV-COTEDAZUR</a>,
      plus every linked data-repository DOI declared on those notices.
    </p>
    <div class="stats" id="stats"></div>

    <section class="panel">
      <h2>Linked datasets by year and repository</h2>
      <p class="muted" style="margin:0" id="chartNote"></p>
      <div class="stack-wrap">
        <div class="stack-legend" id="stackLegend"></div>
        <div class="stack-chart" id="stackChart"></div>
      </div>
    </section>

    <section class="panel">
      <h2>Document types in HAL</h2>
      <div class="bars" id="docTypes"></div>
    </section>

    <section class="panel">
      <h2>Where linked data live</h2>
      <p class="muted" style="margin-top:0">All data repositories after DataCite resolution (dataset DOIs only).</p>
      <div class="bars" id="repos" style="margin-top:0.85rem"></div>
    </section>

    <section class="panel">
      <h2>Publications with a related dataset</h2>
      <p class="muted" id="relatedBlurb" style="margin:0"></p>
      <p style="margin:0.85rem 0 0">
        <a href="./all-repositories.html">All repositories (+ publications) →</a>
        &nbsp;·&nbsp;
        <a href="./related-datasets.html">Nakala / Recherche Data Gouv focus →</a>
        &nbsp;·&nbsp;
        <a href="./software.html">Software &amp; source code →</a>
        &nbsp;·&nbsp;
        <a href="./documentation.html">DOI maps &amp; logs →</a>
      </p>
    </section>

    {_footer(generated_at, 'Collection <span id="footerExtra"></span>')}
  </main>
  <script id="data" type="application/json">{payload_json}</script>
  <script>
    const data = JSON.parse(document.getElementById("data").textContent);
    const h = data.harvest;
    const rd = data.related_datasets;
    const dl = data.data_links;
    const chart = data.census_chart || null;
    document.getElementById("collectionLink").href = data.collection_url;
    document.getElementById("collectionLink").textContent = data.collection;
    const extra = document.getElementById("footerExtra");
    if (extra) {{
      extra.textContent = `${{data.collection}} · years ${{h.year_min}}–${{h.year_max}}`;
    }}
    const pubsWithData = (chart && chart.publications_with_dataset) || rd.publication_count || 0;
    const uniqueDatasets = (chart && chart.unique_datasets) || 0;
    document.getElementById("stats").innerHTML = [
      {{ v: h.documents.toLocaleString("en"), l: "HAL documents (latest version)" }},
      {{ v: h.with_doi.toLocaleString("en"), l: `With DOI (${{Math.round(h.doi_share*100)}}%)` }},
      {{ v: uniqueDatasets.toLocaleString("en"), l: "Unique linked dataset DOIs (all repos)" }},
      {{ v: pubsWithData.toLocaleString("en"), l: "Pubs with a related dataset (all repos)" }},
    ].map(x => `<div class="stat"><strong>${{x.v}}</strong><span>${{x.l}}</span></div>`).join("");

    const noteEl = document.getElementById("chartNote");
    const legendEl = document.getElementById("stackLegend");
    const chartEl = document.getElementById("stackChart");
    if (chart && chart.stacked && chart.stacked.years && chart.stacked.years.length) {{
      noteEl.textContent = chart.note || "";
      const series = chart.stacked.series || [];
      const years = chart.stacked.years;
      const totals = chart.stacked.totals || [];
      const maxTotal = Math.max(1, ...totals);
      const wrap = legendEl.closest(".stack-wrap");
      const repoKey = (name) => String(name || "");
      legendEl.innerHTML = series.map(s =>
        `<button type="button" class="stack-legend-item" data-repo="${{esc(s.repository)}}">
          <i class="stack-swatch" style="background:${{s.color}}"></i>${{esc(s.repository)}}
        </button>`
      ).join("");
      chartEl.innerHTML = years.map((year, i) => {{
        const total = totals[i] || 0;
        const segs = series.map(s => {{
          const n = (s.counts && s.counts[i]) || 0;
          if (!n) return "";
          const pct = (100 * n / maxTotal).toFixed(2);
          const label = n >= 3 ? String(n) : "";
          return `<div class="stack-seg" data-repo="${{esc(s.repository)}}" data-year="${{year}}" data-count="${{n}}"
            style="flex:0 0 ${{pct}}%; background:${{s.color}}"
            title="${{esc(s.repository)}} · ${{year}}: ${{n}}">${{label}}</div>`;
        }}).join("");
        return `<div class="stack-col">
          <div class="stack-total">${{total}}</div>
          <div class="stack-bars">${{segs}}</div>
          <div class="stack-year">${{year}}</div>
        </div>`;
      }}).join("");

      function setHighlight(repo) {{
        const active = Boolean(repo);
        wrap.classList.toggle("is-filtering", active);
        wrap.querySelectorAll("[data-repo]").forEach(el => {{
          el.classList.toggle("is-active", active && el.getAttribute("data-repo") === repo);
        }});
      }}
      function clearHighlight() {{ setHighlight(""); }}

      wrap.addEventListener("pointerover", (ev) => {{
        const el = ev.target.closest("[data-repo]");
        if (!el || !wrap.contains(el)) return;
        setHighlight(el.getAttribute("data-repo"));
      }});
      wrap.addEventListener("pointerleave", clearHighlight);
      wrap.addEventListener("focusin", (ev) => {{
        const el = ev.target.closest("[data-repo]");
        if (el) setHighlight(el.getAttribute("data-repo"));
      }});
      wrap.addEventListener("focusout", (ev) => {{
        if (!wrap.contains(ev.relatedTarget)) clearHighlight();
      }});
    }} else {{
      noteEl.textContent = "Census chart unavailable — run a census refresh to populate dataset×year series.";
      legendEl.innerHTML = "";
      chartEl.innerHTML = "";
    }}

    const maxType = Math.max(...h.doc_types.map(d => d.count));
    document.getElementById("docTypes").innerHTML = h.doc_types.map(d => `
      <div class="bar-row">
        <span>${{d.type}}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${{100*d.count/maxType}}%"></div></div>
        <span>${{d.count.toLocaleString("en")}}</span>
      </div>`).join("");

    const repos = Object.entries(dl.by_repository || {{}});
    const maxRepo = Math.max(1, ...repos.map(([,c]) => c));
    document.getElementById("repos").innerHTML = repos.map(([name, count]) => `
      <div class="bar-row">
        <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis" title="${{name.replace(/"/g, '&quot;')}}">${{name}}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${{100*count/maxRepo}}%"></div></div>
        <span>${{count}}</span>
      </div>`).join("");

    const topRepos = Object.entries((chart && chart.by_repository) || dl.by_repository || {{}}).slice(0, 8).map(([k,v]) => `${{v}} on ${{k}}`).join(" · ");
    const repoCount = Object.keys((chart && chart.by_repository) || dl.by_repository || {{}}).length;
    const more = repoCount > 8 ? ` · +${{repoCount - 8}} more repositories` : "";
    document.getElementById("relatedBlurb").textContent =
      `${{pubsWithData}} UniCA HAL publications declare at least one related dataset DOI on a data repository (all repositories). ${{topRepos}}${{more}}.`;
  </script>
</body>
</html>
"""


def render_related(payload_json: str, *, generated_at: str | None = None) -> str:
    sort_opts = """
            <option value="hal_desc" selected>Newest HAL update</option>
            <option value="hal_asc">Oldest HAL update</option>
            <option value="year_desc">Publication year (newest)</option>
            <option value="title_asc">Title A–Z</option>
            <option value="repo_asc">Repository A–Z</option>
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>hal-unica · Related datasets</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700&display=swap" rel="stylesheet" />
  <style>{SHARED_CSS}</style>
</head>
<body>
  <main class="wrap">
    {_nav("related")}
    <div class="eyebrow">Publications ↔ datasets</div>
    <h1>Related datasets</h1>
    <p class="lede">
      HAL publications in the UniCA collection that declare a
      <code>relatedData</code> link resolving to a real data repository
      (NAKALA or Recherche Data Gouv — including federated nodes such as Data INRAE).
    </p>
    <div class="stats" id="stats"></div>
    <section class="panel">
      <input id="q" class="search" type="search" placeholder="Search title, HAL id, dataset DOI, lab…" autocomplete="off" />
      <div class="filters" id="filters"></div>
      {_list_toolbar_html(sort_options_html=sort_opts)}
      <div class="list" id="list"></div>
    </section>
    {_footer(generated_at, "Source: HAL <code>relatedData_s</code> + DataCite landing resolution.")}
  </main>
  <script id="data" type="application/json">{payload_json}</script>
  <script>
    {_shared_list_helpers_js()}
    const data = JSON.parse(document.getElementById("data").textContent);
    let pubs = data.related_datasets.publications || [];
    let active = "all";
    const allLabs = uniqueLabs(pubs, p => p.laboratories);
    const allYears = uniqueYears(pubs, p => [p.producedDateY_i]);

    function sortRows(rows) {{
      const mode = document.getElementById("sort").value;
      return rows.slice().sort((a, b) => {{
        if (mode === "hal_desc") return cmpIsoDesc(a.modifiedDate_tdate, b.modifiedDate_tdate) || cmpStr(a.title_s, b.title_s);
        if (mode === "hal_asc") return cmpIsoAsc(a.modifiedDate_tdate, b.modifiedDate_tdate) || cmpStr(a.title_s, b.title_s);
        if (mode === "year_desc") return (Number(b.producedDateY_i)||0) - (Number(a.producedDateY_i)||0) || cmpStr(a.title_s, b.title_s);
        if (mode === "repo_asc") return cmpStr((a.repositories||[])[0], (b.repositories||[])[0]) || cmpStr(a.title_s, b.title_s);
        return cmpStr(a.title_s, b.title_s);
      }});
    }}

    function render() {{
      paintLabControls(allLabs);
      paintYearControls(allYears);
      const q = document.getElementById("q").value.trim().toLowerCase();
      const labFilter = activeLabFilter();
      const yearFilter = activeYearFilter();
      const filtered = pubs.filter(p => {{
        if (active !== "all" && !(p.repositories || []).includes(active)) return false;
        if (!labsMatch(p.laboratories, labFilter)) return false;
        if (!yearsMatch([p.producedDateY_i], yearFilter)) return false;
        if (!q) return true;
        const blob = [p.title_s, p.halId_s, p.doiId_s, p.producedDateY_i, ...(p.repositories||[]), ...(p.laboratories||[]),
          ...(p.datasets||[]).map(d => `${{d.doi}} ${{d.repository}} ${{d.dataset_title || ""}}`)].join(" ").toLowerCase();
        return blob.includes(q);
      }});
      const rows = sortRows(filtered);
      document.getElementById("count").textContent = `${{rows.length}} of ${{pubs.length}} publications`;
      const list = document.getElementById("list");
      if (!rows.length) {{ list.innerHTML = `<div class="empty">No matches.</div>`; return; }}
      list.innerHTML = rows.map(p => {{
        const badges = (p.repositories||[]).map(r => `<span class="badge">${{esc(r)}}</span>`).join("");
        const misfiledBadge = (p.datasets||[]).some(d => d.misfiled)
          ? `<span class="badge" title="Dataset DOI appears only outside relatedData_s">misfiled field</span>`
          : "";
        const datasets = (p.datasets||[]).map(d => {{
          const href = d.landing_url || (d.doi ? `https://doi.org/${{d.doi}}` : "#");
          const repo = d.repository || "Unknown";
          const field = d.field || d.source_field || "relatedData_s";
          const fieldNote = d.misfiled
            ? `<div class="doi-annot" style="color:var(--accent-hover)">HAL field <code>${{esc(field)}}</code> only (expected <code>relatedData_s</code>)</div>`
            : (field && field !== "relatedData_s"
              ? `<div class="doi-annot">Also listed in HAL <code>${{esc(field)}}</code>${{d.also_in_relatedData_s ? " (already in relatedData_s)" : ""}}</div>`
              : `<div class="doi-annot">HAL field <code>${{esc(field)}}</code></div>`);
          return `<div class="ev"><dt>Dataset</dt><dd>
            <div class="doi-annot">Link to the dataset on ${{esc(repo)}}</div>
            ${{fieldNote}}
            <a href="${{esc(href)}}" target="_blank" rel="noopener"><code>${{esc(d.doi)}}</code></a>
            ${{d.dataset_title ? `<div class="muted" style="margin-top:0.25rem">${{esc(d.dataset_title)}}</div>` : ""}}
            ${{d.landing_host ? `<div class="muted" style="margin-top:0.15rem">${{esc(d.landing_host)}}</div>` : ""}}
          </dd></div>`;
        }}).join("");
        const halMod = p.modifiedDate_tdate
          ? `<span class="muted"><time datetime="${{esc(p.modifiedDate_tdate)}}">HAL updated ${{formatStamp(p.modifiedDate_tdate)}}</time></span>`
          : "";
        const yearBadge = p.producedDateY_i ? `<span class="badge">${{esc(p.producedDateY_i)}}</span>` : "";
        return `<article class="result">
          <div class="title-row">
            <div>
              <span class="doi-annot">HAL publication with related dataset(s)</span>
              <h2 class="title"><a href="${{esc(p.uri_s || "#")}}" target="_blank" rel="noopener">${{esc(p.title_s || "(untitled)")}}</a></h2>
            </div>
            <div class="badges">${{yearBadge}}${{badges}}${{misfiledBadge}}</div>
          </div>
          <div class="sub">
            <a href="${{esc(p.uri_s || "#")}}" target="_blank" rel="noopener"><code>${{esc(p.halId_s)}}</code></a>
            <span>${{esc(p.docType_s || "")}}</span>
            ${{p.doiId_s ? `<span>pub DOI <a href="https://doi.org/${{esc(p.doiId_s)}}" target="_blank" rel="noopener"><code>${{esc(p.doiId_s)}}</code></a></span>` : ""}}
            <span>${{(p.datasets||[]).length}} dataset(s)</span>
            ${{halMod}}
          </div>
          ${{yearLine([p.producedDateY_i])}}
          ${{labsLine(p.laboratories)}}
          <div class="evidence">${{datasets}}</div>
        </article>`;
      }}).join("");
    }}

    const by = data.related_datasets.by_repository || {{}};
    document.getElementById("stats").innerHTML = [
      {{ v: data.related_datasets.publication_count, l: "Publications with related dataset" }},
      {{ v: by["Recherche Data Gouv"] || 0, l: "→ Recherche Data Gouv" }},
      {{ v: by["NAKALA"] || 0, l: "→ NAKALA" }},
      {{ v: Object.values(by).reduce((a,b)=>a+b,0), l: "Repository links (sum)" }},
    ].map(x => `<div class="stat"><strong>${{x.v}}</strong><span>${{x.l}}</span></div>`).join("");

    const repos = ["all", ...Object.keys(by)];
    const filters = document.getElementById("filters");
    function paint() {{
      filters.innerHTML = repos.map(r => `
        <button type="button" class="chip" data-v="${{esc(r)}}" aria-pressed="${{active===r}}">${{esc(r==="all"?"All repositories":r)}}</button>
      `).join("");
      filters.querySelectorAll("button").forEach(btn => btn.addEventListener("click", () => {{
        active = btn.dataset.v; paint(); render();
      }}));
    }}
    paint();
    paintLabControls(allLabs);
    paintYearControls(allYears);
    wireLabControls(render);
    document.getElementById("q").addEventListener("input", render);
    document.getElementById("sort").addEventListener("change", render);
    render();
  </script>
</body>
</html>
"""


def render_census(census_json: str, *, generated_at: str | None = None) -> str:
    sort_opts = """
            <option value="retrieved_desc" selected>Newest retrieved</option>
            <option value="retrieved_asc">Oldest retrieved</option>
            <option value="hal_desc">Newest HAL update</option>
            <option value="year_desc">Publication year (newest)</option>
            <option value="repo_asc">Repository A–Z</option>
            <option value="doi_asc">Dataset DOI A–Z</option>
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>hal-unica · All repositories</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700&display=swap" rel="stylesheet" />
  <style>{SHARED_CSS}</style>
</head>
<body>
  <main class="wrap">
    {_nav("census")}
    <div class="eyebrow">Full relatedData census</div>
    <h1>All linked repositories</h1>
    <p class="lede">
      Each related dataset DOI with its repository landing page, plus the HAL
      publication(s) that declare the link (title + HAL notice URL).
    </p>
    <div class="stats" id="stats"></div>
    <section class="panel">
      <h2>Repositories (by related DOI)</h2>
      <div class="bars" id="repos"></div>
    </section>
    <section class="panel">
      <input id="q" class="search" type="search" placeholder="Filter dataset DOI, repository, publication, lab…" autocomplete="off" />
      <div class="filters" id="filters"></div>
      {_list_toolbar_html(sort_options_html=sort_opts)}
      <div class="list" id="list"></div>
    </section>
    {_footer(generated_at, 'CSV: <a href="./data/census/dataset_to_publications.csv"><code>dataset_to_publications.csv</code></a>')}
  </main>
  <script id="data" type="application/json">{census_json}</script>
  <script>
    {_shared_list_helpers_js()}
    const data = JSON.parse(document.getElementById("data").textContent);
    const s = data.summary;
    const idx = data.dataset_index || {{}};
    const datasets = data.datasets || [];
    let active = "all";
    const allLabs = uniqueLabs(datasets, d => (d.publications || []).flatMap(p => p.laboratories || []));
    const allYears = uniqueYears(datasets, d => (d.publications || []).map(p => p.producedDateY_i));

    const byRepo = idx.by_repository || datasets.reduce((acc, d) => {{
      const r = d.repository || "Unknown";
      acc[r] = (acc[r] || 0) + 1;
      return acc;
    }}, {{}});
    const uniqueDatasets = idx.unique_datasets || datasets.length;
    const linkCount = idx.dataset_publication_links || datasets.reduce((n, d) => n + (d.publications || []).length, 0);
    const pubsWithDatasets = s.publications_with_dataset_repo_landing
      || new Set(datasets.flatMap(d => (d.publications || []).map(p => p.halId_s).filter(Boolean))).size;

    document.getElementById("stats").innerHTML = [
      {{ v: pubsWithDatasets, l: "HAL notices linking a dataset" }},
      {{ v: uniqueDatasets, l: "Unique dataset DOIs" }},
      {{ v: Object.keys(byRepo).length, l: "Distinct data repositories" }},
      {{ v: linkCount, l: "Dataset↔publication links" }},
    ].map(x => `<div class="stat"><strong>${{x.v}}</strong><span>${{x.l}}</span></div>`).join("");

    const reposEntries = Object.entries(byRepo).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    const maxRepo = Math.max(1, ...reposEntries.map(([,c]) => c));
    document.getElementById("repos").innerHTML = reposEntries.map(([name, count]) => `
      <div class="bar-row">
        <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis" title="${{name.replace(/"/g,'&quot;')}}">${{name}}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${{100*count/maxRepo}}%"></div></div>
        <span>${{count}}</span>
      </div>`).join("");

    const repoFilters = ["all", ...reposEntries.map(([name]) => name)];
    function paintFilters() {{
      document.getElementById("filters").innerHTML = repoFilters.map(r => `
        <button type="button" class="chip" data-v="${{esc(r)}}" aria-pressed="${{active===r}}">${{esc(r==="all"?"All repositories":r)}}</button>
      `).join("");
      document.querySelectorAll("#filters button").forEach(btn => btn.addEventListener("click", () => {{
        active = btn.dataset.v; paintFilters(); render();
      }}));
    }}

    function itemLabs(d) {{
      return [...new Set((d.publications || []).flatMap(p => p.laboratories || []).filter(Boolean))];
    }}
    function itemYears(d) {{
      return (d.publications || []).map(p => p.producedDateY_i).filter(y => y != null && y !== "");
    }}

    function sortRows(rows) {{
      const mode = document.getElementById("sort").value;
      return rows.slice().sort((a, b) => {{
        if (mode === "retrieved_desc") return cmpIsoDesc(a.retrieved_at, b.retrieved_at) || cmpStr(a.dataset_doi, b.dataset_doi);
        if (mode === "retrieved_asc") return cmpIsoAsc(a.retrieved_at, b.retrieved_at) || cmpStr(a.dataset_doi, b.dataset_doi);
        if (mode === "hal_desc") return cmpIsoDesc(a.hal_modified_at, b.hal_modified_at) || cmpStr(a.dataset_doi, b.dataset_doi);
        if (mode === "year_desc") {{
          const ya = Math.max(0, ...itemYears(a).map(Number).filter(Number.isFinite));
          const yb = Math.max(0, ...itemYears(b).map(Number).filter(Number.isFinite));
          return yb - ya || cmpStr(a.dataset_doi, b.dataset_doi);
        }}
        if (mode === "doi_asc") return cmpStr(a.dataset_doi, b.dataset_doi);
        return cmpStr(a.repository, b.repository) || cmpStr(a.dataset_doi, b.dataset_doi);
      }});
    }}

    function render() {{
      paintLabControls(allLabs);
      paintYearControls(allYears);
      const q = document.getElementById("q").value.trim().toLowerCase();
      const labFilter = activeLabFilter();
      const yearFilter = activeYearFilter();
      const filtered = datasets.filter(d => {{
        if (active !== "all" && d.repository !== active) return false;
        if (!labsMatch(itemLabs(d), labFilter)) return false;
        if (!yearsMatch(itemYears(d), yearFilter)) return false;
        if (!q) return true;
        const blob = [d.dataset_doi, d.repository, d.landing_host, d.dataset_title, d.retrieved_at,
          ...itemLabs(d), ...itemYears(d),
          ...(d.publications||[]).map(p => `${{p.halId_s}} ${{p.title_s}} ${{p.doiId_s}}`)].join(" ").toLowerCase();
        return blob.includes(q);
      }});
      const rows = sortRows(filtered);
      document.getElementById("count").textContent = `${{rows.length}} of ${{datasets.length}} datasets`;
      document.getElementById("list").innerHTML = rows.map(d => {{
        const href = d.landing_url || `https://doi.org/${{d.dataset_doi}}`;
        const pubs = (d.publications || []).map(p => {{
          const pubDoi = p.doiId_s
            ? ` · <a href="https://doi.org/${{esc(p.doiId_s)}}" target="_blank" rel="noopener">DOI <code>${{esc(p.doiId_s)}}</code></a>`
            : "";
          const field = p.source_field || "";
          const fieldNote = p.misfiled_dataset_link
            ? `<div class="doi-annot" style="color:var(--accent-hover)">HAL field <code>${{esc(field)}}</code> only (expected <code>relatedData_s</code>)</div>`
            : (field && field !== "relatedData_s"
              ? `<div class="doi-annot">Also listed in HAL <code>${{esc(field)}}</code>${{p.also_in_relatedData_s ? " (already in relatedData_s)" : ""}}</div>`
              : (field ? `<div class="doi-annot">HAL field <code>${{esc(field)}}</code></div>` : ""));
          const pubYear = p.producedDateY_i
            ? `<div class="muted" style="margin-top:0.15rem;font-size:0.8rem">Publication year: ${{esc(p.producedDateY_i)}}</div>`
            : "";
          return `<div class="ev"><dt>Publication</dt><dd>
            <a href="${{esc(p.uri_s || "#")}}" target="_blank" rel="noopener">${{esc(p.title_s || "(untitled)")}}</a>
            ${{fieldNote}}
            ${{pubYear}}
            ${{labsLine(p.laboratories)}}
            <div class="muted" style="margin-top:0.25rem">
              <a href="${{esc(p.uri_s || "#")}}" target="_blank" rel="noopener"><code>${{esc(p.halId_s)}}</code></a>
              ${{p.docType_s ? " · " + esc(p.docType_s) : ""}}${{pubDoi}}
            </div>
          </dd></div>`;
        }}).join("");
        const repo = d.repository || "Unknown";
        const sourceFields = (d.source_fields || []).join(", ");
        const misfiledBadge = d.has_misfiled_source
          ? `<span class="badge" title="Dataset DOI appears only outside relatedData_s">misfiled field</span>`
          : "";
        const retrieved = d.retrieved_at
          ? `<span title="First seen in this census index"><time datetime="${{esc(d.retrieved_at)}}">Retrieved ${{formatStamp(d.retrieved_at)}}</time></span>`
          : "";
        const halMod = d.hal_modified_at
          ? `<span class="muted" title="Latest HAL modifiedDate among linked notices"><time datetime="${{esc(d.hal_modified_at)}}">HAL updated ${{formatStamp(d.hal_modified_at)}}</time></span>`
          : "";
        const cardLabs = itemLabs(d);
        const years = itemYears(d);
        const yearBadge = years.length
          ? `<span class="badge" title="Publication year(s) of linked HAL notices">${{esc([...new Set(years.map(Number))].sort((a,b)=>b-a).join(" · "))}}</span>`
          : "";
        return `<article class="result">
          <div class="title-row">
            <div>
              <span class="doi-annot">Link to the dataset on ${{esc(repo)}}</span>
              ${{sourceFields ? `<span class="doi-annot">HAL source field(s): <code>${{esc(sourceFields)}}</code></span>` : ""}}
              <h2 class="title"><a href="${{esc(href)}}" target="_blank" rel="noopener"><code>${{esc(d.dataset_doi)}}</code></a></h2>
            </div>
            <div class="badges">${{yearBadge}}<span class="badge">${{esc(repo)}}</span>${{misfiledBadge}}</div>
          </div>
          <div class="sub">
            <span>${{esc(d.dataset_title || "")}}</span>
            <span class="muted">${{esc(d.landing_host || "")}}</span>
            <span>${{(d.publications||[]).length}} publication(s)</span>
            ${{retrieved}}
            ${{halMod}}
          </div>
          ${{yearLine(years)}}
          ${{labsLine(cardLabs)}}
          <div class="evidence">${{pubs || '<div class="muted">No linked publication in census.</div>'}}</div>
        </article>`;
      }}).join("") || `<div class="empty">No matches.</div>`;
    }}
    paintFilters();
    paintLabControls(allLabs);
    paintYearControls(allYears);
    wireLabControls(render);
    document.getElementById("q").addEventListener("input", render);
    document.getElementById("sort").addEventListener("change", render);
    render();
  </script>
</body>
</html>
"""





def render_software(software_json: str, *, generated_at: str | None = None) -> str:
    sort_opts = """
            <option value="retrieved_desc" selected>Newest retrieved</option>
            <option value="retrieved_asc">Oldest retrieved</option>
            <option value="hal_desc">Newest HAL update</option>
            <option value="title_asc">Title A–Z</option>
            <option value="year_desc">Year (newest)</option>
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>hal-unica · Software</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700&display=swap" rel="stylesheet" />
  <style>{SHARED_CSS}</style>
</head>
<body>
  <main class="wrap">
    {_nav("software")}
    <div class="eyebrow">HAL SOFTWARE deposits</div>
    <h1>Software &amp; source code</h1>
    <p class="lede">
      UniCA HAL notices with <code>docType_s=SOFTWARE</code>, including code repository
      URLs, Software Heritage (SWHID) archives, HAL files, and related publications
      when declared.
    </p>
    <div class="stats" id="stats"></div>
    <section class="panel">
      <input id="q" class="search" type="search" placeholder="Search software title, HAL id, language, Git URL, lab…" autocomplete="off" />
      {_list_toolbar_html(sort_options_html=sort_opts)}
      <div class="list" id="list"></div>
    </section>
    {_footer(
      generated_at,
      'Downloads: <a href="./data/census/software_deposits.csv"><code>software_deposits.csv</code></a> · '
      '<a href="./data/census/software_deposits.jsonl"><code>software_deposits.jsonl</code></a>',
    )}
  </main>
  <script id="data" type="application/json">{software_json}</script>
  <script>
    {_shared_list_helpers_js()}
    const data = JSON.parse(document.getElementById("data").textContent);
    const rows = data.deposits || [];
    const s = data.summary || {{}};
    const allLabs = uniqueLabs(rows, r => r.laboratories);
    const allYears = uniqueYears(rows, r => [r.producedDateY_i]);

    function pubLink(id) {{
      if (!id) return "";
      if (/^10\\./.test(id)) return `https://doi.org/${{id}}`;
      if (/^https?:/.test(id)) return id;
      return `https://hal.science/${{id}}`;
    }}

    document.getElementById("stats").innerHTML = [
      {{ v: s.software_deposits || rows.length, l: "SOFTWARE deposits" }},
      {{ v: s.with_swhid || 0, l: "With Software Heritage SWHID" }},
      {{ v: s.with_code_repository || 0, l: "With code repository URL" }},
      {{ v: s.with_related_publication || 0, l: "With related publication" }},
    ].map(x => `<div class="stat"><strong>${{x.v}}</strong><span>${{x.l}}</span></div>`).join("");

    function sortRows(list) {{
      const mode = document.getElementById("sort").value;
      return list.slice().sort((a, b) => {{
        if (mode === "retrieved_desc") return cmpIsoDesc(a.retrieved_at, b.retrieved_at) || cmpStr(a.title_s, b.title_s);
        if (mode === "retrieved_asc") return cmpIsoAsc(a.retrieved_at, b.retrieved_at) || cmpStr(a.title_s, b.title_s);
        if (mode === "hal_desc") return cmpIsoDesc(a.modifiedDate_tdate, b.modifiedDate_tdate) || cmpStr(a.title_s, b.title_s);
        if (mode === "year_desc") return (Number(b.producedDateY_i)||0) - (Number(a.producedDateY_i)||0) || cmpStr(a.title_s, b.title_s);
        return cmpStr(a.title_s, b.title_s);
      }});
    }}

    function render() {{
      paintLabControls(allLabs);
      paintYearControls(allYears);
      const q = document.getElementById("q").value.trim().toLowerCase();
      const labFilter = activeLabFilter();
      const yearFilter = activeYearFilter();
      const filtered = rows.filter(r => {{
        if (!labsMatch(r.laboratories, labFilter)) return false;
        if (!yearsMatch([r.producedDateY_i], yearFilter)) return false;
        if (!q) return true;
        const blob = [r.title_s, r.halId_s, r.doiId_s, r.producedDateY_i, ...(r.laboratories||[]), ...(r.authFullName_s||[]),
          ...(r.softCodeRepository_s||[]), ...(r.swhidId_s||[]),
          ...(r.softProgrammingLanguage_s||[]), ...(r.relatedPublication_s||[]), ...(r.relatedData_s||[])].join(" ").toLowerCase();
        return blob.includes(q);
      }});
      const list = sortRows(filtered);
      document.getElementById("count").textContent = `${{list.length}} of ${{rows.length}} deposits`;
      document.getElementById("list").innerHTML = list.map(r => {{
        const langs = (r.softProgrammingLanguage_s||[]).map(l => `<span class="badge">${{esc(l)}}</span>`).join("");
        const repos = (r.softCodeRepository_s||[]).map(u =>
          `<div class="ev"><dt>Code repo</dt><dd><a href="${{esc(u)}}" target="_blank" rel="noopener">${{esc(u)}}</a></dd></div>`
        ).join("");
        const swh = (r.swhidId_s||[]).map((id, i) => {{
          const browse = (r.swh_browse_urls&&r.swh_browse_urls[i]) || ("https://archive.softwareheritage.org/browse/" + id.split(";")[0]);
          return `<div class="ev"><dt>SWHID</dt><dd><a href="${{esc(browse)}}" target="_blank" rel="noopener"><code>${{esc(id.split(";")[0])}}</code></a></dd></div>`;
        }}).join("");
        const pubs = (r.relatedPublication_s||[]).map(id => {{
          const href = pubLink(id);
          return `<div class="ev"><dt>Related pub</dt><dd><a href="${{esc(href)}}" target="_blank" rel="noopener"><code>${{esc(id)}}</code></a></dd></div>`;
        }}).join("");
        const dataLinks = (r.relatedData_s||[]).map(id => {{
          const href = pubLink(id);
          return `<div class="ev"><dt>Related data</dt><dd><a href="${{esc(href)}}" target="_blank" rel="noopener"><code>${{esc(id)}}</code></a></dd></div>`;
        }}).join("");
        const files = (r.files_s||[]).slice(0,3).map(u =>
          `<div class="ev"><dt>HAL file</dt><dd><a href="${{esc(u)}}" target="_blank" rel="noopener">${{esc(u.split("/").pop())}}</a></dd></div>`
        ).join("");
        const authors = (r.authFullName_s||[]).slice(0, 8);
        const authorLine = authors.length
          ? `<span class="muted" style="font-size:0.8rem">${{esc(authors.join(", "))}}${{(r.authFullName_s||[]).length > 8 ? "…" : ""}}</span>`
          : "";
        const retrieved = r.retrieved_at
          ? `<span><time datetime="${{esc(r.retrieved_at)}}">Retrieved ${{formatStamp(r.retrieved_at)}}</time></span>`
          : "";
        const halMod = r.modifiedDate_tdate
          ? `<span class="muted"><time datetime="${{esc(r.modifiedDate_tdate)}}">HAL updated ${{formatStamp(r.modifiedDate_tdate)}}</time></span>`
          : "";
        const yearBadge = r.producedDateY_i ? `<span class="badge">${{esc(r.producedDateY_i)}}</span>` : "";
        return `<article class="result">
          <div class="title-row">
            <div>
              <span class="doi-annot">HAL SOFTWARE deposit</span>
              <h2 class="title"><a href="${{esc(r.uri_s || "#")}}" target="_blank" rel="noopener">${{esc(r.title_s || "(untitled)")}}</a></h2>
            </div>
            <div class="badges">${{yearBadge}}${{langs || '<span class="badge">SOFTWARE</span>'}}</div>
          </div>
          <div class="sub">
            <a href="${{esc(r.uri_s || "#")}}" target="_blank" rel="noopener"><code>${{esc(r.halId_s)}}</code></a>
            ${{r.doiId_s ? `<a href="https://doi.org/${{esc(r.doiId_s)}}" target="_blank" rel="noopener"><code>${{esc(r.doiId_s)}}</code></a>` : ""}}
            <span>${{(r.softCodeRepository_s||[]).length}} repo(s)</span>
            <span>${{(r.swhidId_s||[]).length}} SWHID(s)</span>
            ${{retrieved}}
            ${{halMod}}
          </div>
          ${{yearLine([r.producedDateY_i])}}
          ${{authorLine}}
          ${{labsLine(r.laboratories)}}
          <div class="evidence">${{repos}}${{swh}}${{pubs}}${{dataLinks}}${{files || (r.fileMain_s ? `<div class="ev"><dt>HAL file</dt><dd><a href="${{esc(r.fileMain_s)}}" target="_blank" rel="noopener">document</a></dd></div>` : "")}}</div>
        </article>`;
      }}).join("") || `<div class="empty">No matches.</div>`;
    }}
    paintLabControls(allLabs);
    paintYearControls(allYears);
    wireLabControls(render);
    document.getElementById("q").addEventListener("input", render);
    document.getElementById("sort").addEventListener("change", render);
    render();
  </script>
</body>
</html>
"""




def render_corrections(corrections_json: str, *, generated_at: str | None = None) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>hal-unica · To Be Corrected</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700&display=swap" rel="stylesheet" />
  <style>{SHARED_CSS}</style>
</head>
<body>
  <main class="wrap">
    {_nav("corrections")}
    <div class="eyebrow">Field provenance · correction queue</div>
    <h1>To Be Corrected</h1>
    <p class="lede">
      Dataset DOIs that resolve to a data repository but appear <strong>only</strong> in a HAL
      field other than <code>relatedData_s</code> (often <code>relatedPublication_s</code> or
      <code>seeAlso_s</code>). If the same DOI is already present in <code>relatedData_s</code>,
      an extra mention elsewhere is treated as supplementary and is <em>not</em> listed here.
    </p>
    <div class="stats" id="stats"></div>
    <section class="panel">
      <input id="q" class="search" type="search" placeholder="Filter HAL id, title, DOI, repository, source field…" autocomplete="off" />
      <div class="filters" id="filters"></div>
      <div class="meta-row"><div id="count"></div><div>Expected field: <code>relatedData_s</code></div></div>
      <div class="list" id="list"></div>
    </section>
    {_footer(
      generated_at,
      'CSV: <a href="./data/census/misfiled_dataset_links.csv"><code>misfiled_dataset_links.csv</code></a>',
    )}
  </main>
  <script id="data" type="application/json">{corrections_json}</script>
  <script>
    const data = JSON.parse(document.getElementById("data").textContent);
    const rows = data.rows || [];
    const s = data.summary || {{}};
    let active = "all";

    function esc(s) {{
      return String(s ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    }}

    document.getElementById("stats").innerHTML = [
      {{ v: s.misfiled_links || rows.length, l: "Misfiled dataset links" }},
      {{ v: s.publications || 0, l: "Distinct HAL notices" }},
      {{ v: Object.keys(s.by_source_field || {{}}).length, l: "Incorrect source fields" }},
      {{ v: Object.keys(s.by_repository || {{}}).length, l: "Repositories involved" }},
    ].map(x => `<div class="stat"><strong>${{x.v}}</strong><span>${{x.l}}</span></div>`).join("");

    const fieldFilters = ["all", ...Object.keys(s.by_source_field || {{}})];
    function paintFilters() {{
      document.getElementById("filters").innerHTML = fieldFilters.map(f => `
        <button type="button" class="chip" data-v="${{esc(f)}}" aria-pressed="${{active===f}}">${{esc(f==="all"?"All source fields":f)}}</button>
      `).join("");
      document.querySelectorAll("#filters button").forEach(btn => btn.addEventListener("click", () => {{
        active = btn.dataset.v; paintFilters(); render();
      }}));
    }}

    function render() {{
      const q = document.getElementById("q").value.trim().toLowerCase();
      const filtered = rows.filter(r => {{
        if (active !== "all" && r.source_field !== active) return false;
        if (!q) return true;
        const blob = [r.halId_s, r.hal_title, r.dataset_doi, r.repository, r.source_field,
          r.dataset_title, r.correction_note, r.laboratories].join(" ").toLowerCase();
        return blob.includes(q);
      }});
      document.getElementById("count").textContent = `${{filtered.length}} of ${{rows.length}} links`;
      document.getElementById("list").innerHTML = filtered.map(r => {{
        const href = r.landing_url || (r.dataset_doi ? `https://doi.org/${{r.dataset_doi}}` : "#");
        const repo = r.repository || "Unknown";
        const labs = String(r.laboratories || "").split("|").map(s => s.trim()).filter(Boolean);
        const labsLine = labs.length
          ? `<div class="muted" style="margin-top:0.2rem;font-size:0.8rem">Labs: ${{esc(labs.join(" · "))}}</div>`
          : "";
        return `<article class="result">
          <div class="title-row">
            <div>
              <span class="doi-annot">Link to the dataset on ${{esc(repo)}}</span>
              <span class="doi-annot" style="color:var(--accent-hover)">HAL field <code>${{esc(r.source_field || "")}}</code> only → expected <code>${{esc(r.expected_field || "relatedData_s")}}</code></span>
              <h2 class="title"><a href="${{esc(href)}}" target="_blank" rel="noopener"><code>${{esc(r.dataset_doi)}}</code></a></h2>
            </div>
            <div class="badges">
              <span class="badge">${{esc(repo)}}</span>
              <span class="badge">${{esc(r.source_field || "")}}</span>
            </div>
          </div>
          <div class="sub">
            <span>${{esc(r.dataset_title || "")}}</span>
          </div>
          <div class="evidence">
            <div class="ev"><dt>Publication</dt><dd>
              <a href="${{esc(r.hal_uri || "#")}}" target="_blank" rel="noopener">${{esc(r.hal_title || "(untitled)")}}</a>
              ${{labsLine}}
              <div class="muted" style="margin-top:0.25rem">
                <a href="${{esc(r.hal_uri || "#")}}" target="_blank" rel="noopener"><code>${{esc(r.halId_s)}}</code></a>
                ${{r.hal_docType ? " · " + esc(r.hal_docType) : ""}}
                ${{r.publication_doi ? ` · DOI <a href="https://doi.org/${{esc(r.publication_doi)}}" target="_blank" rel="noopener"><code>${{esc(r.publication_doi)}}</code></a>` : ""}}
              </div>
            </dd></div>
            <div class="ev"><dt>Action</dt><dd>${{esc(r.correction_note || "Move this dataset DOI to relatedData_s on HAL.")}}</dd></div>
          </div>
        </article>`;
      }}).join("") || `<div class="empty">No matches.</div>`;
    }}
    paintFilters();
    document.getElementById("q").addEventListener("input", render);
    render();
  </script>
</body>
</html>
"""


def render_documentation(
    manifest: dict[str, Any],
    summary: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> str:
    artifacts = manifest.get("artifacts") or {}
    method = manifest.get("method") or []
    method_li = "".join(f"<li>{m}</li>" for m in method)
    art_rows = "".join(
        f"<tr><td><code>{k}</code></td><td><a href=\"./data/census/{Path(v).name}\"><code>{Path(v).name}</code></a></td></tr>"
        for k, v in artifacts.items()
        if Path(v).name
    )
    repo_rows = "".join(
        f"<tr><td>{repo}</td><td style=\"text-align:right\">{count}</td></tr>"
        for repo, count in (summary.get("by_repository") or {}).items()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>hal-unica · Documentation</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Syne:wght@600;700&display=swap" rel="stylesheet" />
  <style>{SHARED_CSS}
  table.doc {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
  table.doc th, table.doc td {{ padding: 0.5rem 0.4rem; border-bottom: 1px solid var(--line); text-align: left; }}
  ol.method {{ margin: 0; padding-left: 1.2rem; color: var(--ink-soft); line-height: 1.55; }}
  </style>
</head>
<body>
  <main class="wrap">
    {_nav("docs")}
    <div class="eyebrow">Supporting files</div>
    <h1>Documentation</h1>
    <p class="lede">
      How the census is built, and downloadable files that map each related DOI
      to its repository (not only the summary charts).
    </p>

    <section class="panel">
      <h2>Method</h2>
      <ol class="method">{method_li}</ol>
      <p class="muted" style="margin:0.85rem 0 0">
        HAL query: <code>{manifest.get("hal_query")}</code> on
        <code>{manifest.get("hal_api")}</code>.
        DOI API: <code>{manifest.get("datacite_api")}</code>.
        Run: <code>{manifest.get("started_at")}</code> → <code>{manifest.get("finished_at")}</code>.
      </p>
    </section>

    <section class="panel">
      <h2>Artifacts (download)</h2>
      <table class="doc">
        <thead><tr><th>Role</th><th>File</th></tr></thead>
        <tbody>{art_rows}</tbody>
      </table>
      <p class="muted" style="margin:0.85rem 0 0">
        Start with
        <a href="./data/census/dataset_to_publications.csv"><code>dataset_to_publications.csv</code></a>
        (dataset → publications),
        <a href="./data/census/doi_to_repository.csv"><code>doi_to_repository.csv</code></a>
        (DOI → repository),
        <a href="./data/census/software_deposits.csv"><code>software_deposits.csv</code></a>
        (SOFTWARE + SWHID + code repos), and
        <a href="./data/census/doi_hal_repository_map.csv"><code>doi_hal_repository_map.csv</code></a>,
        and the correction queue
        <a href="./data/census/misfiled_dataset_links.csv"><code>misfiled_dataset_links.csv</code></a>
        (dataset DOIs filed outside <code>relatedData_s</code>).
        Methodology:
        <a href="./data/census/METHODOLOGY.md"><code>METHODOLOGY.md</code></a>.
      </p>
    </section>

    <section class="panel">
      <h2>Repository totals (this census)</h2>
      <table class="doc">
        <thead><tr><th>Repository</th><th>Related DOI count</th></tr></thead>
        <tbody>{repo_rows}</tbody>
      </table>
    </section>

    {_footer(
      generated_at or manifest.get("generated_at") or manifest.get("finished_at"),
      'Source repository: <a href="https://github.com/xiaoouwang/hal-unica">github.com/xiaoouwang/hal-unica</a>',
    )}
  </main>
</body>
</html>
"""


def write_site(
    *,
    harvest_path: Path | None,
    links_path: Path,
    output_dir: Path,
    collection: str = "UNIV-COTEDAZUR",
    census_dir: Path | None = None,
    stats_fallback: Path | None = None,
) -> Path:
    payload = build_site_payload(
        harvest_path=harvest_path,
        links_path=links_path,
        collection=collection,
        stats_fallback=stats_fallback,
        census_dir=census_dir,
    )
    payload_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "stats.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (data_dir / "related-publications.json").write_text(
        json.dumps(payload["related_datasets"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    generated_at = payload.get("generated_at")
    (output_dir / "index.html").write_text(
        render_index(payload_json, generated_at=generated_at), encoding="utf-8"
    )
    (output_dir / "related-datasets.html").write_text(
        render_related(payload_json, generated_at=generated_at), encoding="utf-8"
    )

    if census_dir and census_dir.exists():
        import shutil

        dest = data_dir / "census"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(census_dir, dest)

        summary = json.loads((dest / "summary.json").read_text(encoding="utf-8"))
        datasets: list[dict[str, Any]] = []
        ds_file = dest / "dataset_to_publications.jsonl"
        if ds_file.exists():
            for line in ds_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    datasets.append(json.loads(line))
        ds_summary = {}
        ds_sum_path = dest / "dataset_to_publications_summary.json"
        if ds_sum_path.exists():
            ds_summary = json.loads(ds_sum_path.read_text(encoding="utf-8"))
        census_payload = {
            "generated_at": generated_at,
            "summary": summary,
            "datasets": datasets,
            "dataset_index": ds_summary,
        }
        census_json = json.dumps(census_payload, ensure_ascii=False).replace("<", "\\u003c")
        (output_dir / "all-repositories.html").write_text(
            render_census(census_json, generated_at=generated_at), encoding="utf-8"
        )

        # Correction queue page (misfiled dataset links)
        import csv as _csv

        misfiled_rows: list[dict[str, Any]] = []
        misfiled_path = dest / "misfiled_dataset_links.csv"
        if misfiled_path.exists():
            with misfiled_path.open(encoding="utf-8", newline="") as fh:
                misfiled_rows = list(_csv.DictReader(fh))
        by_src: Counter[str] = Counter()
        by_repo_m: Counter[str] = Counter()
        pubs_m: set[str] = set()
        for row in misfiled_rows:
            if row.get("source_field"):
                by_src[row["source_field"]] += 1
            if row.get("repository"):
                by_repo_m[row["repository"]] += 1
            if row.get("halId_s"):
                pubs_m.add(row["halId_s"])
        corrections_payload = {
            "generated_at": generated_at,
            "rows": misfiled_rows,
            "summary": {
                "misfiled_links": len(misfiled_rows),
                "publications": len(pubs_m),
                "by_source_field": dict(sorted(by_src.items(), key=lambda kv: (-kv[1], kv[0]))),
                "by_repository": dict(sorted(by_repo_m.items(), key=lambda kv: (-kv[1], kv[0]))),
            },
        }
        corrections_json = json.dumps(corrections_payload, ensure_ascii=False).replace(
            "<", "\\u003c"
        )
        (output_dir / "to-be-corrected.html").write_text(
            render_corrections(corrections_json, generated_at=generated_at),
            encoding="utf-8",
        )

        soft_rows: list[dict[str, Any]] = []
        soft_file = dest / "software_deposits.jsonl"
        if soft_file.exists():
            for line in soft_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    soft_rows.append(json.loads(line))
        soft_summary = {}
        soft_sum = dest / "software_summary.json"
        if soft_sum.exists():
            soft_summary = json.loads(soft_sum.read_text(encoding="utf-8"))
        if soft_rows or soft_summary:
            soft_json = json.dumps(
                {
                    "generated_at": generated_at,
                    "deposits": soft_rows,
                    "summary": soft_summary,
                },
                ensure_ascii=False,
            ).replace("<", "\\u003c")
            (output_dir / "software.html").write_text(
                render_software(soft_json, generated_at=generated_at), encoding="utf-8"
            )

        manifest = {}
        man_path = dest / "run_manifest.json"
        if man_path.exists():
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
            manifest["artifacts"] = {
                k: f"data/census/{Path(v).name}"
                for k, v in (manifest.get("artifacts") or {}).items()
            }
        # Ensure new artifacts appear even if not in old manifest
        for name in (
            "dataset_to_publications.csv",
            "dataset_to_publications.jsonl",
            "software_deposits.csv",
            "software_deposits.jsonl",
            "software_summary.json",
            "misfiled_dataset_links.csv",
        ):
            if (dest / name).exists():
                manifest.setdefault("artifacts", {})[name] = f"data/census/{name}"
        (output_dir / "documentation.html").write_text(
            render_documentation(
                manifest, summary, generated_at=generated_at
            ),
            encoding="utf-8",
        )

    return output_dir
