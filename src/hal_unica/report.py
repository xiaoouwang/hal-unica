"""Generate a self-contained HTML report for data-repo link hits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PLATFORM_META = {
    "nakala": {
        "label": "NAKALA",
        "blurb": "Huma-Num research data repository",
    },
    "rdg": {
        "label": "RDG prefix",
        "blurb": "DOI prefix 10.57745 (coarse)",
    },
    "rdg_network": {
        "label": "RDG network prefix",
        "blurb": "Partner DOI prefix e.g. 10.15454 (coarse)",
    },
}


def build_html(hits: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    payload = json.dumps({"summary": summary, "hits": hits}, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>UniCA · HAL data repository links</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --ink: #0c2438;
      --ink-soft: #3d5568;
      --paper: #f3f7f4;
      --sea: #0a6e7a;
      --sea-deep: #084b54;
      --foam: #d8efe8;
      --coral: #c45c3e;
      --line: rgba(12, 36, 56, 0.12);
      --shadow: rgba(8, 75, 84, 0.08);
      --radius: 14px;
      --font-display: "Fraunces", Georgia, serif;
      --font-body: "IBM Plex Sans", "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: var(--font-body);
      background:
        radial-gradient(1200px 600px at 10% -10%, #b8e0d8 0%, transparent 55%),
        radial-gradient(900px 500px at 100% 0%, #cfe3f0 0%, transparent 50%),
        linear-gradient(180deg, #eef5f2 0%, var(--paper) 32%, #e9f0ec 100%);
      min-height: 100vh;
    }}
    a {{ color: var(--sea-deep); }}
    a:hover {{ color: var(--coral); }}
    .wrap {{ width: min(1100px, calc(100% - 2rem)); margin: 0 auto; padding: 2.5rem 0 4rem; }}
    .hero {{ display: grid; gap: 1.1rem; padding: 0.5rem 0 1.75rem; animation: rise 0.7s ease both; }}
    .eyebrow {{
      font-size: 0.8rem; font-weight: 600; letter-spacing: 0.08em;
      text-transform: uppercase; color: var(--sea);
    }}
    h1 {{
      margin: 0; font-family: var(--font-display); font-weight: 650;
      font-size: clamp(2.1rem, 5vw, 3.3rem); line-height: 1.05;
      letter-spacing: -0.02em; max-width: 16ch;
    }}
    .lede {{ margin: 0; max-width: 44rem; font-size: 1.05rem; line-height: 1.55; color: var(--ink-soft); }}
    .stats {{
      display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0.75rem; margin-top: 0.35rem;
    }}
    @media (max-width: 720px) {{ .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    .stat {{
      background: rgba(255,255,255,0.55); border: 1px solid var(--line);
      border-radius: var(--radius); padding: 1rem 1.1rem; backdrop-filter: blur(6px);
    }}
    .stat strong {{ display: block; font-family: var(--font-display); font-size: 1.8rem; font-weight: 650; line-height: 1; }}
    .stat span {{ display: block; margin-top: 0.35rem; font-size: 0.8rem; color: var(--ink-soft); }}
    .panel {{
      background: rgba(255,255,255,0.72); border: 1px solid var(--line);
      border-radius: calc(var(--radius) + 4px); padding: 1rem; backdrop-filter: blur(8px);
      animation: rise 0.85s ease both;
    }}
    .controls {{ display: grid; gap: 0.85rem; }}
    .search {{
      width: 100%; border: 1px solid var(--line); border-radius: 999px;
      padding: 0.85rem 1.15rem; font: inherit; background: #fff; outline: none;
    }}
    .search:focus {{ border-color: var(--sea); box-shadow: 0 0 0 3px rgba(10,110,122,0.15); }}
    .filter-block {{ display: grid; gap: 0.4rem; }}
    .filter-label {{ font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--ink-soft); }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 0.45rem; }}
    .chip {{
      appearance: none; border: 1px solid var(--line); background: #fff;
      color: var(--ink-soft); border-radius: 999px; padding: 0.42rem 0.8rem;
      font: inherit; font-size: 0.84rem; font-weight: 500; cursor: pointer;
      transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
    }}
    .chip:hover {{ transform: translateY(-1px); }}
    .chip[aria-pressed="true"] {{ background: var(--sea); border-color: var(--sea); color: #fff; }}
    .chip.warn[aria-pressed="true"] {{ background: #8a5a2b; border-color: #8a5a2b; }}
    .meta-row {{
      display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
      margin: 1.2rem 0 0.75rem; color: var(--ink-soft); font-size: 0.92rem;
    }}
    .list {{ display: grid; gap: 0.65rem; }}
    details.result {{
      background: #fff; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden;
    }}
    details.result[open] {{ border-color: rgba(10,110,122,0.35); box-shadow: 0 10px 28px var(--shadow); }}
    summary {{ list-style: none; cursor: pointer; padding: 1rem 1.1rem; display: grid; gap: 0.55rem; }}
    summary::-webkit-details-marker {{ display: none; }}
    .title-row {{ display: flex; gap: 0.75rem; justify-content: space-between; align-items: start; }}
    .title {{ margin: 0; font-family: var(--font-display); font-size: 1.06rem; font-weight: 650; line-height: 1.3; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 0.35rem; flex-shrink: 0; justify-content: flex-end; max-width: 45%; }}
    .badge {{
      font-size: 0.7rem; font-weight: 600; letter-spacing: 0.02em;
      padding: 0.28rem 0.55rem; border-radius: 999px; background: var(--foam); color: var(--sea-deep);
    }}
    .badge.pub {{ background: #f3e6d6; color: #6b4520; }}
    .sub {{ display: flex; flex-wrap: wrap; gap: 0.55rem 1rem; font-size: 0.86rem; color: var(--ink-soft); }}
    .sub code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem;
      background: var(--paper); padding: 0.1rem 0.35rem; border-radius: 4px;
    }}
    .evidence {{
      border-top: 1px solid var(--line); padding: 0.85rem 1.1rem 1.1rem;
      display: grid; gap: 0.55rem; background: linear-gradient(180deg, #fbfcfb, #fff);
    }}
    .ev {{
      display: grid; grid-template-columns: 8.5rem 1fr; gap: 0.75rem;
      font-size: 0.9rem; padding: 0.55rem 0.65rem; border-radius: 10px; background: rgba(243,247,244,0.9);
    }}
    @media (max-width: 640px) {{
      .ev {{ grid-template-columns: 1fr; gap: 0.25rem; }}
      .badges {{ max-width: 100%; justify-content: flex-start; }}
    }}
    .ev dt {{ margin: 0; font-weight: 600; color: var(--sea-deep); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .ev dd {{ margin: 0; word-break: break-word; }}
    .muted {{ color: var(--ink-soft); }}
    .empty {{ padding: 2rem 1rem; text-align: center; color: var(--ink-soft); }}
    footer {{ margin-top: 2rem; font-size: 0.82rem; color: var(--ink-soft); line-height: 1.5; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ animation: none !important; transition: none !important; }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <header class="hero">
      <div class="eyebrow">Université Côte d’Azur · HAL</div>
      <h1>Data repository links</h1>
      <p class="lede">
        HAL notices linked to data repositories. Coarse DOI prefixes are refined with
        <strong>DataCite</strong> (publisher, landing host, repository name).
        Rows marked <em>HAL notice</em> share an INRAE DOI prefix but land on a publication page, not a data vault.
      </p>
      <div class="stats" id="stats"></div>
    </header>

    <section class="panel" aria-label="Filters">
      <div class="controls">
        <input id="q" class="search" type="search" placeholder="Search title, HAL id, DOI, repository…" autocomplete="off" />
        <div class="filter-block">
          <div class="filter-label">Repository (fine)</div>
          <div class="filters" id="repoFilters"></div>
        </div>
        <div class="filter-block">
          <div class="filter-label">Object kind</div>
          <div class="filters" id="kindFilters"></div>
        </div>
        <div class="filter-block">
          <div class="filter-label">DOI prefix (coarse)</div>
          <div class="filters" id="platformFilters"></div>
        </div>
      </div>
    </section>

    <div class="meta-row">
      <div id="count"></div>
      <div>Click a row for evidence + DataCite details</div>
    </div>
    <section class="list" id="list" aria-live="polite"></section>
    <footer>
      Built from <code>unica_data_repo_links.jsonl</code> with DataCite resolution.
      Coarse prefixes: NAKALA <code>10.34847</code>, RDG <code>10.57745</code>, INRAE network <code>10.15454</code>.
    </footer>
  </main>

  <script id="data" type="application/json">{payload}</script>
  <script>
    const PLATFORM_META = {json.dumps(PLATFORM_META)};
    const raw = JSON.parse(document.getElementById("data").textContent);
    const hits = raw.hits;
    const summary = raw.summary;

    const statsEl = document.getElementById("stats");
    const repoFiltersEl = document.getElementById("repoFilters");
    const kindFiltersEl = document.getElementById("kindFilters");
    const platformFiltersEl = document.getElementById("platformFilters");
    const listEl = document.getElementById("list");
    const countEl = document.getElementById("count");
    const qEl = document.getElementById("q");

    let activeRepo = "all";
    let activeKind = "all";
    let activePlatform = "all";

    const repos = ["all", ...Object.keys(summary.by_repository || {{}})];
    const kinds = ["all", ...Object.keys(summary.by_object_kind || {{}})];
    const platforms = ["all", "nakala", "rdg", "rdg_network"];

    const KIND_LABEL = {{
      dataset_repo: "Data repository landing",
      publication_landing: "Publication / HAL landing",
      other: "Other",
      unresolved: "Unresolved",
    }};

    function esc(s) {{
      return String(s ?? "").replace(/[&<>"']/g, (c) => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }})[c]);
    }}

    function doiUrl(value) {{
      const v = String(value || "");
      if (/^10\\./.test(v)) return `https://doi.org/${{encodeURI(v)}}`;
      if (/^https?:\\/\\//i.test(v)) return v;
      return null;
    }}

    function renderStats() {{
      const byRepo = summary.by_repository || {{}};
      const items = [
        {{ value: summary.total_hits, label: "Linked HAL records" }},
        {{ value: byRepo["NAKALA"] || 0, label: "NAKALA" }},
        {{ value: byRepo["Recherche Data Gouv"] || 0, label: "Recherche Data Gouv" }},
        {{ value: (summary.by_object_kind || {{}}).dataset_repo || 0, label: "Data-repo landings" }},
      ];
      statsEl.innerHTML = items.map((it) => `
        <div class="stat"><strong>${{it.value}}</strong><span>${{esc(it.label)}}</span></div>
      `).join("");
    }}

    function renderChipGroup(el, values, active, onPick, labelFn, warnFn) {{
      el.innerHTML = values.map((v) => {{
        const label = labelFn ? labelFn(v) : v;
        const pressed = active === v ? "true" : "false";
        const warn = warnFn && warnFn(v) ? " warn" : "";
        return `<button type="button" class="chip${{warn}}" data-value="${{esc(v)}}" aria-pressed="${{pressed}}">${{esc(label)}}</button>`;
      }}).join("");
      el.querySelectorAll("button").forEach((btn) => {{
        btn.addEventListener("click", () => onPick(btn.dataset.value));
      }});
    }}

    function renderFilters() {{
      renderChipGroup(repoFiltersEl, repos, activeRepo, (v) => {{ activeRepo = v; renderFilters(); renderList(); }},
        (v) => v === "all" ? "All repositories" : v);
      renderChipGroup(kindFiltersEl, kinds, activeKind, (v) => {{ activeKind = v; renderFilters(); renderList(); }},
        (v) => v === "all" ? "All kinds" : (KIND_LABEL[v] || v),
        (v) => v === "publication_landing");
      renderChipGroup(platformFiltersEl, platforms, activePlatform, (v) => {{ activePlatform = v; renderFilters(); renderList(); }},
        (v) => v === "all" ? "All prefixes" : (PLATFORM_META[v]?.label || v));
    }}

    function filtered() {{
      const q = qEl.value.trim().toLowerCase();
      return hits.filter((h) => {{
        if (activePlatform !== "all" && !(h.platforms || []).includes(activePlatform)) return false;
        if (activeRepo !== "all" && !(h.repositories || []).includes(activeRepo)) return false;
        if (activeKind !== "all") {{
          const kinds = (h.evidence || []).map((e) => e.object_kind).filter(Boolean);
          if (!kinds.includes(activeKind)) return false;
        }}
        if (!q) return true;
        const blob = [
          h.title_s, h.halId_s, h.doiId_s, h.docType_s,
          ...(h.platforms || []),
          ...(h.repositories || []),
          ...(h.evidence || []).map((e) => `${{e.value}} ${{e.kind}} ${{e.repository || ""}} ${{e.publisher || ""}} ${{e.landing_host || ""}}`)
        ].join(" ").toLowerCase();
        return blob.includes(q);
      }});
    }}

    function renderList() {{
      const rows = filtered();
      countEl.textContent = `${{rows.length}} of ${{hits.length}} records`;
      if (!rows.length) {{
        listEl.innerHTML = `<div class="empty">No records match these filters.</div>`;
        return;
      }}
      listEl.innerHTML = rows.map((h) => {{
        const repoBadges = (h.repositories || []).map((r) => {{
          const cls = /HAL notice/i.test(r) ? "badge pub" : "badge";
          return `<span class="${{cls}}">${{esc(r)}}</span>`;
        }}).join("");
        const evidence = (h.evidence || []).map((e) => {{
          const link = e.landing_url || doiUrl(e.value);
          const val = link
            ? `<a href="${{esc(link)}}" target="_blank" rel="noopener">${{esc(e.value)}}</a>`
            : esc(e.value);
          const meta = [
            e.repository ? `<div><strong>Repository:</strong> ${{esc(e.repository)}}</div>` : "",
            e.publisher ? `<div><strong>Publisher:</strong> ${{esc(e.publisher)}}</div>` : "",
            e.landing_host ? `<div><strong>Landing:</strong> ${{esc(e.landing_host)}}</div>` : "",
            e.object_kind ? `<div class="muted">${{esc(KIND_LABEL[e.object_kind] || e.object_kind)}}</div>` : "",
          ].join("");
          return `<div class="ev"><dt>${{esc(e.kind)}} · ${{esc(e.field)}}</dt><dd>${{val}}${{meta ? `<div style="margin-top:0.35rem">${{meta}}</div>` : ""}}</dd></div>`;
        }}).join("");
        const doi = h.doiId_s
          ? `<span>DOI <a href="https://doi.org/${{esc(h.doiId_s)}}" target="_blank" rel="noopener"><code>${{esc(h.doiId_s)}}</code></a></span>`
          : "";
        return `
          <details class="result">
            <summary>
              <div class="title-row">
                <h2 class="title">${{esc(h.title_s || "(untitled)")}}</h2>
                <div class="badges">${{repoBadges}}</div>
              </div>
              <div class="sub">
                <span><a href="${{esc(h.uri_s || "#")}}" target="_blank" rel="noopener"><code>${{esc(h.halId_s)}}</code></a></span>
                <span>${{esc(h.docType_s || "")}}</span>
                ${{doi}}
              </div>
            </summary>
            <div class="evidence">${{evidence}}</div>
          </details>`;
      }}).join("");
    }}

    qEl.addEventListener("input", renderList);
    renderStats();
    renderFilters();
    renderList();
  </script>
</body>
</html>
"""


def write_report(
    hits_path: Path,
    summary_path: Path | None,
    output_path: Path,
) -> Path:
    hits = [
        json.loads(line)
        for line in hits_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if summary_path and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        by_platform: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        by_repository: dict[str, int] = {}
        by_object_kind: dict[str, int] = {}
        for hit in hits:
            for p in hit.get("platforms") or []:
                by_platform[p] = by_platform.get(p, 0) + 1
            for repo in hit.get("repositories") or []:
                by_repository[repo] = by_repository.get(repo, 0) + 1
            kinds = {e.get("kind") for e in hit.get("evidence") or []}
            for k in kinds:
                if k:
                    by_kind[k] = by_kind.get(k, 0) + 1
            for e in hit.get("evidence") or []:
                ok = e.get("object_kind")
                if ok:
                    by_object_kind[ok] = by_object_kind.get(ok, 0) + 1
        summary = {
            "total_hits": len(hits),
            "by_platform": by_platform,
            "by_repository": by_repository,
            "by_object_kind": by_object_kind,
            "by_evidence_kind": by_kind,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(hits, summary), encoding="utf-8")
    return output_path
