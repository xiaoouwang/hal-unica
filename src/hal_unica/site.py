"""Build the public GitHub Pages site (stats + related-dataset publications)."""

from __future__ import annotations

import json
from collections import Counter
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
                "repositories": repos,
                "datasets": [
                    {
                        "doi": e.value,
                        "repository": e.repository,
                        "publisher": e.publisher,
                        "landing_url": e.landing_url,
                        "landing_host": e.landing_host,
                        "field": e.field,
                        "misfiled": e.field != "relatedData_s",
                    }
                    for e in related
                ],
            }
        )
    out.sort(key=lambda r: (r.get("title_s") or "").lower())
    return out


def build_site_payload(
    *,
    harvest_path: Path | None,
    links_path: Path,
    collection: str = "UNIV-COTEDAZUR",
    stats_fallback: Path | None = None,
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

    return {
        "generated_at": _utc_now(),
        "collection": collection,
        "collection_url": f"https://hal.science/{collection}",
        "harvest": harvest,
        "data_links": {
            "total_hits": link_summary["total_hits"],
            "by_platform": link_summary.get("by_platform") or {},
            "by_repository": link_summary.get("by_repository") or {},
            "by_object_kind": link_summary.get("by_object_kind") or {},
        },
        "related_datasets": {
            "publication_count": len(related),
            "by_repository": dict(
                sorted(related_repos.items(), key=lambda kv: (-kv[1], kv[0]))
            ),
            "publications": related,
        },
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
.search {
  width: 100%; border: 1px solid var(--line); border-radius: 10px;
  padding: 0.85rem 1.1rem; font: inherit; background: var(--surface); outline: none; margin-bottom: 0.75rem;
}
.search:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(42,38,34,0.1); }
.filters { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }
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
      <a class="brand" href="./index.html">hal-unica</a>
      {link("./index.html", "Statistics", "stats")}
      {link("./related-datasets.html", "Nakala / RDG", "related")}
      {link("./all-repositories.html", "All repositories", "census")}
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
  <title>hal-unica · Statistics</title>
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
      plus links from those notices to NAKALA and Research Data Gouv.
    </p>
    <div class="stats" id="stats"></div>

    <section class="panel">
      <h2>Document types in HAL</h2>
      <div class="bars" id="docTypes"></div>
    </section>

    <section class="panel">
      <h2>Where linked data live</h2>
      <p class="muted" style="margin-top:0">Fine-grained repositories after DataCite resolution (all link signals).</p>
      <div class="bars" id="repos" style="margin-top:0.85rem"></div>
    </section>

    <section class="panel">
      <h2>Publications with a related dataset</h2>
      <p class="muted" id="relatedBlurb" style="margin:0"></p>
      <p style="margin:0.85rem 0 0">
        <a href="./related-datasets.html">Nakala / Recherche Data Gouv →</a>
        &nbsp;·&nbsp;
        <a href="./all-repositories.html">All repositories (+ publications) →</a>
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
    document.getElementById("collectionLink").href = data.collection_url;
    document.getElementById("collectionLink").textContent = data.collection;
    const extra = document.getElementById("footerExtra");
    if (extra) {{
      extra.textContent = `${{data.collection}} · years ${{h.year_min}}–${{h.year_max}}`;
    }}
      document.getElementById("stats").innerHTML = [
        {{ v: h.documents.toLocaleString("en"), l: "HAL documents (latest version)" }},
        {{ v: h.with_doi.toLocaleString("en"), l: `With DOI (${{Math.round(h.doi_share*100)}}%)` }},
        {{ v: h.software_deposits || 0, l: "SOFTWARE deposits" }},
        {{ v: rd.publication_count, l: "Pubs with related dataset (Nakala/RDG)" }},
      ].map(x => `<div class="stat"><strong>${{x.v}}</strong><span>${{x.l}}</span></div>`).join("");

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

    const rb = Object.entries(rd.by_repository || {{}}).map(([k,v]) => `${{v}} on ${{k}}`).join(" · ");
    document.getElementById("relatedBlurb").textContent =
      `${{rd.publication_count}} UniCA HAL publications declare relatedData landing on a data repository. ${{rb}}.`;
  </script>
</body>
</html>
"""


def render_related(payload_json: str, *, generated_at: str | None = None) -> str:
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
      <input id="q" class="search" type="search" placeholder="Search title, HAL id, dataset DOI…" autocomplete="off" />
      <div class="filters" id="filters"></div>
      <div class="meta-row"><div id="count"></div><div>Datasets shown inline for each publication</div></div>
      <div class="list" id="list"></div>
    </section>
    {_footer(generated_at, "Source: HAL <code>relatedData_s</code> + DataCite landing resolution.")}
  </main>
  <script id="data" type="application/json">{payload_json}</script>
  <script>
    const data = JSON.parse(document.getElementById("data").textContent);
    let pubs = data.related_datasets.publications || [];
    let active = "all";

    function esc(s) {{
      return String(s ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    }}

    function render() {{
      const q = document.getElementById("q").value.trim().toLowerCase();
      const rows = pubs.filter(p => {{
        if (active !== "all" && !(p.repositories || []).includes(active)) return false;
        if (!q) return true;
        const blob = [p.title_s, p.halId_s, p.doiId_s, ...(p.repositories||[]),
          ...(p.datasets||[]).map(d => `${{d.doi}} ${{d.repository}}`)].join(" ").toLowerCase();
        return blob.includes(q);
      }});
      document.getElementById("count").textContent = `${{rows.length}} of ${{pubs.length}} publications`;
      const list = document.getElementById("list");
      if (!rows.length) {{ list.innerHTML = `<div class="empty">No matches.</div>`; return; }}
      list.innerHTML = rows.map(p => {{
        const badges = (p.repositories||[]).map(r => `<span class="badge">${{esc(r)}}</span>`).join("");
        const datasets = (p.datasets||[]).map(d => {{
          const href = d.landing_url || (d.doi ? `https://doi.org/${{d.doi}}` : "#");
          const repo = d.repository || "Unknown";
          const field = d.field || d.source_field || "relatedData_s";
          const misfiled = field !== "relatedData_s";
          const fieldNote = misfiled
            ? `<div class="doi-annot" style="color:var(--accent-hover)">HAL field <code>${{esc(field)}}</code> (expected <code>relatedData_s</code> — ask depositor to correct)</div>`
            : `<div class="doi-annot">HAL field <code>${{esc(field)}}</code></div>`;
          return `<div class="ev"><dt>Dataset</dt><dd>
            <div class="doi-annot">Link to the dataset on ${{esc(repo)}}</div>
            ${{fieldNote}}
            <a href="${{esc(href)}}" target="_blank" rel="noopener"><code>${{esc(d.doi)}}</code></a>
            ${{d.landing_host ? `<div class="muted" style="margin-top:0.25rem">${{esc(d.landing_host)}}</div>` : ""}}
          </dd></div>`;
        }}).join("");
        return `<article class="result">
          <div class="title-row"><h2 class="title">${{esc(p.title_s || "(untitled)")}}</h2><div class="badges">${{badges}}</div></div>
          <div class="sub">
            <a href="${{esc(p.uri_s || "#")}}" target="_blank" rel="noopener"><code>${{esc(p.halId_s)}}</code></a>
            <span>${{esc(p.docType_s || "")}}</span>
            ${{p.doiId_s ? `<span>pub DOI <a href="https://doi.org/${{esc(p.doiId_s)}}" target="_blank" rel="noopener"><code>${{esc(p.doiId_s)}}</code></a></span>` : ""}}
          </div>
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
    document.getElementById("q").addEventListener("input", render);
    render();
  </script>
</body>
</html>
"""


def render_census(census_json: str, *, generated_at: str | None = None) -> str:
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
      <input id="q" class="search" type="search" placeholder="Filter dataset DOI, repository, publication…" autocomplete="off" />
      <div class="filters" id="filters"></div>
      <div class="meta-row"><div id="count"></div><div>Related publications shown inline</div></div>
      <div class="list" id="list"></div>
    </section>
    {_footer(generated_at, 'CSV: <a href="./data/census/dataset_to_publications.csv"><code>dataset_to_publications.csv</code></a>')}
  </main>
  <script id="data" type="application/json">{census_json}</script>
  <script>
    const data = JSON.parse(document.getElementById("data").textContent);
    const s = data.summary;
    const datasets = data.datasets || [];
    let active = "all";

    function esc(s) {{
      return String(s ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    }}

    document.getElementById("stats").innerHTML = [
      {{ v: s.hal_publications_with_relatedData, l: "HAL notices with relatedData" }},
      {{ v: s.unique_dois_resolved, l: "Unique related DOIs" }},
      {{ v: Object.keys(s.by_repository || {{}}).length, l: "Distinct repositories" }},
      {{ v: (data.dataset_index && data.dataset_index.dataset_publication_links) || datasets.length, l: "Dataset↔publication links" }},
    ].map(x => `<div class="stat"><strong>${{x.v}}</strong><span>${{x.l}}</span></div>`).join("");

    const reposEntries = Object.entries(s.by_repository || {{}});
    const maxRepo = Math.max(1, ...reposEntries.map(([,c]) => c));
    document.getElementById("repos").innerHTML = reposEntries.map(([name, count]) => `
      <div class="bar-row">
        <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis" title="${{name.replace(/"/g,'&quot;')}}">${{name}}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${{100*count/maxRepo}}%"></div></div>
        <span>${{count}}</span>
      </div>`).join("");

    const repoFilters = ["all", ...Object.keys(s.by_repository || {{}})];
    function paintFilters() {{
      document.getElementById("filters").innerHTML = repoFilters.map(r => `
        <button type="button" class="chip" data-v="${{esc(r)}}" aria-pressed="${{active===r}}">${{esc(r==="all"?"All repositories":r)}}</button>
      `).join("");
      document.querySelectorAll("#filters button").forEach(btn => btn.addEventListener("click", () => {{
        active = btn.dataset.v; paintFilters(); render();
      }}));
    }}

    function render() {{
      const q = document.getElementById("q").value.trim().toLowerCase();
      const rows = datasets.filter(d => {{
        if (active !== "all" && d.repository !== active) return false;
        if (!q) return true;
        const blob = [d.dataset_doi, d.repository, d.landing_host, d.dataset_title,
          ...(d.publications||[]).map(p => `${{p.halId_s}} ${{p.title_s}} ${{p.doiId_s}}`)].join(" ").toLowerCase();
        return blob.includes(q);
      }});
      document.getElementById("count").textContent = `${{rows.length}} of ${{datasets.length}} datasets`;
      document.getElementById("list").innerHTML = rows.map(d => {{
        const href = d.landing_url || `https://doi.org/${{d.dataset_doi}}`;
        const pubs = (d.publications || []).map(p => {{
          const pubDoi = p.doiId_s
            ? ` · <a href="https://doi.org/${{esc(p.doiId_s)}}" target="_blank" rel="noopener">DOI <code>${{esc(p.doiId_s)}}</code></a>`
            : "";
          const field = p.source_field || "";
          const fieldNote = field
            ? (p.misfiled_dataset_link || field !== "relatedData_s"
              ? `<div class="doi-annot" style="color:var(--accent-hover)">HAL field <code>${{esc(field)}}</code> (expected <code>relatedData_s</code>)</div>`
              : `<div class="doi-annot">HAL field <code>${{esc(field)}}</code></div>`)
            : "";
          return `<div class="ev"><dt>Publication</dt><dd>
            <a href="${{esc(p.uri_s || "#")}}" target="_blank" rel="noopener">${{esc(p.title_s || "(untitled)")}}</a>
            ${{fieldNote}}
            <div class="muted" style="margin-top:0.25rem">
              <a href="${{esc(p.uri_s || "#")}}" target="_blank" rel="noopener"><code>${{esc(p.halId_s)}}</code></a>
              ${{p.docType_s ? " · " + esc(p.docType_s) : ""}}${{pubDoi}}
            </div>
          </dd></div>`;
        }}).join("");
        const repo = d.repository || "Unknown";
        const sourceFields = (d.source_fields || []).join(", ");
        const misfiledBadge = d.has_misfiled_source
          ? `<span class="badge" title="Dataset DOI was not filed in relatedData_s">misfiled field</span>`
          : "";
        return `<article class="result">
          <div class="title-row">
            <div>
              <span class="doi-annot">Link to the dataset on ${{esc(repo)}}</span>
              ${{sourceFields ? `<span class="doi-annot">HAL source field(s): <code>${{esc(sourceFields)}}</code></span>` : ""}}
              <h2 class="title"><a href="${{esc(href)}}" target="_blank" rel="noopener"><code>${{esc(d.dataset_doi)}}</code></a></h2>
            </div>
            <div class="badges"><span class="badge">${{esc(repo)}}</span>${{misfiledBadge}}</div>
          </div>
          <div class="sub">
            <span>${{esc(d.dataset_title || "")}}</span>
            <span class="muted">${{esc(d.landing_host || "")}}</span>
            <span>${{(d.publications||[]).length}} publication(s)</span>
          </div>
          <div class="evidence">${{pubs || '<div class="muted">No linked publication in census.</div>'}}</div>
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


def render_software(software_json: str, *, generated_at: str | None = None) -> str:
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
      <input id="q" class="search" type="search" placeholder="Search software title, HAL id, language, Git URL…" autocomplete="off" />
      <div class="meta-row"><div id="count"></div><div>Code repos, SWHIDs and related pubs shown inline</div></div>
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
    const data = JSON.parse(document.getElementById("data").textContent);
    const rows = data.deposits || [];
    const s = data.summary || {{}};

    function esc(s) {{
      return String(s ?? "").replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    }}
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

    function render() {{
      const q = document.getElementById("q").value.trim().toLowerCase();
      const filtered = rows.filter(r => {{
        if (!q) return true;
        const blob = [r.title_s, r.halId_s, r.doiId_s,
          ...(r.softCodeRepository_s||[]), ...(r.swhidId_s||[]),
          ...(r.softProgrammingLanguage_s||[]), ...(r.relatedPublication_s||[])].join(" ").toLowerCase();
        return blob.includes(q);
      }});
      document.getElementById("count").textContent = `${{filtered.length}} of ${{rows.length}}`;
      document.getElementById("list").innerHTML = filtered.map(r => {{
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
        const files = (r.files_s||[]).slice(0,3).map(u =>
          `<div class="ev"><dt>HAL file</dt><dd><a href="${{esc(u)}}" target="_blank" rel="noopener">${{esc(u.split("/").pop())}}</a></dd></div>`
        ).join("");
        return `<article class="result">
          <div class="title-row">
            <h2 class="title">${{esc(r.title_s || "(untitled)")}}</h2>
            <div class="badges">${{langs || '<span class="badge">SOFTWARE</span>'}}</div>
          </div>
          <div class="sub">
            <a href="${{esc(r.uri_s || "#")}}" target="_blank" rel="noopener"><code>${{esc(r.halId_s)}}</code></a>
            ${{r.doiId_s ? `<a href="https://doi.org/${{esc(r.doiId_s)}}" target="_blank" rel="noopener"><code>${{esc(r.doiId_s)}}</code></a>` : ""}}
            <span>${{(r.softCodeRepository_s||[]).length}} repo(s)</span>
            <span>${{(r.swhidId_s||[]).length}} SWHID(s)</span>
          </div>
          <div class="evidence">${{repos}}${{swh}}${{pubs}}${{files || (r.fileMain_s ? `<div class="ev"><dt>HAL file</dt><dd><a href="${{esc(r.fileMain_s)}}" target="_blank" rel="noopener">document</a></dd></div>` : "")}}</div>
        </article>`;
      }}).join("") || `<div class="empty">No matches.</div>`;
    }}
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
