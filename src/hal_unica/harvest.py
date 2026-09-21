from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import HalClient
from .fields import DEFAULT_FL, OPTIONAL_FILE_META_FL


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class HarvestResult:
    collection: str
    started_at: str
    finished_at: str
    num_found_api: int
    written: int
    skipped_duplicate_hal_id: int
    output_path: str
    watermark_modified: str | None
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


def harvest_metadata(
    *,
    client: HalClient,
    output_path: Path,
    rows: int = 1000,
    max_docs: int | None = None,
    since: str | None = None,
    include_file_urls: bool = True,
    resume: bool = False,
) -> HarvestResult:
    """
    Full or incremental metadata harvest.

    HAL's collection search index already contains one document per halId
    (the current / latest version). We still dedupe on halId_s as a safety net.
    """
    fl = list(DEFAULT_FL)
    if include_file_urls:
        fl.extend(OPTIONAL_FILE_META_FL)

    fq: list[str] = []
    if since:
        # Solr date range; `since` should be ISO-8601 UTC, e.g. 2024-01-01T00:00:00Z
        fq.append(f"modifiedDate_tdate:[{since} TO *]")

    started = _utc_now()
    num_found = client.count(fq=fq or None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
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

    written = 0
    skipped = 0
    max_modified: str | None = None

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

    finished = _utc_now()
    result = HarvestResult(
        collection=client.collection,
        started_at=started,
        finished_at=finished,
        num_found_api=num_found,
        written=written,
        skipped_duplicate_hal_id=skipped,
        output_path=str(output_path),
        watermark_modified=max_modified,
    )

    sidecar = output_path.with_suffix(output_path.suffix + ".meta.json")
    sidecar.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return result
