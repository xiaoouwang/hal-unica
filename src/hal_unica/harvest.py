from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .client import HalClient
from .fields import DEFAULT_FL, OPTIONAL_FILE_META_FL
from .timeutil import effective_since, format_hal_date, read_watermark, utc_now


def _utc_now() -> str:
    return format_hal_date(utc_now())


@dataclass
class HarvestResult:
    collection: str
    started_at: str
    finished_at: str
    num_found_api: int
    written: int
    inserted: int
    updated: int
    skipped_duplicate_hal_id: int
    output_path: str
    watermark_modified: str | None
    since: str | None = None
    upsert: bool = False
    latest_only: bool = True
    metadata_only: bool = True


def _hal_id(doc: dict[str, Any]) -> str | None:
    value = doc.get("halId_s")
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _modified(doc: dict[str, Any]) -> str | None:
    value = doc.get("modifiedDate_tdate")
    if isinstance(value, list):
        return value[0] if value else None
    return value


def load_jsonl_by_hal_id(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Load JSONL preserving first-seen order of halId keys; docs without id last."""
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    orphans: list[dict[str, Any]] = []
    if not path.exists():
        return by_id, order
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            hid = _hal_id(doc)
            if not hid:
                orphans.append(doc)
                continue
            if hid not in by_id:
                order.append(hid)
            by_id[hid] = doc
    # Keep orphan docs as synthetic keys so they are not dropped on rewrite
    for i, doc in enumerate(orphans):
        key = f"__orphan_{i}"
        order.append(key)
        by_id[key] = doc
    return by_id, order


def _atomic_write_jsonl(path: Path, docs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        for doc in docs:
            tmp.write(json.dumps(doc, ensure_ascii=False) + "\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def harvest_metadata(
    *,
    client: HalClient,
    output_path: Path,
    rows: int = 1000,
    max_docs: int | None = None,
    since: str | None = None,
    lookback_days: float | None = None,
    from_watermark: bool = False,
    safety_hours: float = 1.0,
    include_file_urls: bool = True,
    resume: bool = False,
    upsert: bool | None = None,
) -> HarvestResult:
    """
    Full or incremental metadata harvest.

    HAL's collection search index already contains one document per halId
    (the current / latest version). We still dedupe on halId_s as a safety net.

    When ``since`` / lookback / watermark is set, ``upsert`` defaults to True:
    changed records replace existing rows instead of wiping the corpus.
    """
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    previous_watermark = read_watermark(meta_path)
    watermark = previous_watermark if from_watermark else None
    resolved_since = effective_since(
        since=since,
        lookback_days=lookback_days,
        watermark=watermark,
        safety_hours=safety_hours,
    )

    # Upsert is the safe default for any time-windowed pull against an existing file.
    if upsert is None:
        upsert = bool(resolved_since) and not resume

    fl = list(DEFAULT_FL)
    if include_file_urls:
        fl.extend(OPTIONAL_FILE_META_FL)

    fq: list[str] = []
    if resolved_since:
        fq.append(f"modifiedDate_tdate:[{resolved_since} TO *]")

    started = _utc_now()
    num_found = client.count(fq=fq or None)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    inserted = 0
    updated = 0
    skipped = 0
    max_modified: str | None = None

    if upsert:
        by_id, order = load_jsonl_by_hal_id(output_path)
        existing_ids = set(by_id)
        for doc in client.iter_docs(fq=fq or None, fl=fl, rows=rows, max_docs=max_docs):
            hid = _hal_id(doc)
            mod = _modified(doc)
            if mod and (max_modified is None or mod > max_modified):
                max_modified = mod
            if not hid:
                # Append anonymous docs (rare)
                key = f"__orphan_new_{written}"
                order.append(key)
                by_id[key] = doc
                inserted += 1
                written += 1
                continue
            if hid in existing_ids and hid in by_id:
                by_id[hid] = doc
                updated += 1
            else:
                by_id[hid] = doc
                order.append(hid)
                existing_ids.add(hid)
                inserted += 1
            written += 1
        docs = [by_id[k] for k in order if k in by_id]
        _atomic_write_jsonl(output_path, docs)
    else:
        mode = "a" if resume and output_path.exists() else "w"
        seen: set[str] = set()
        if resume and output_path.exists():
            with output_path.open(encoding="utf-8") as existing:
                for line in existing:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        hid = _hal_id(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if hid:
                        seen.add(hid)

        with output_path.open(mode, encoding="utf-8") as out:
            for doc in client.iter_docs(fq=fq or None, fl=fl, rows=rows, max_docs=max_docs):
                hid = _hal_id(doc)
                if hid:
                    if hid in seen:
                        skipped += 1
                        continue
                    seen.add(hid)
                mod = _modified(doc)
                if mod and (max_modified is None or mod > max_modified):
                    max_modified = mod
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                written += 1
                inserted += 1

    # Advance watermark to the max of previous sidecar and this run
    if previous_watermark and (
        max_modified is None or previous_watermark > max_modified
    ):
        max_modified = previous_watermark
    finished = _utc_now()
    result = HarvestResult(
        collection=client.collection,
        started_at=started,
        finished_at=finished,
        num_found_api=num_found,
        written=written,
        inserted=inserted,
        updated=updated,
        skipped_duplicate_hal_id=skipped,
        output_path=str(output_path),
        watermark_modified=max_modified,
        since=resolved_since,
        upsert=upsert,
    )

    meta_path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return result
