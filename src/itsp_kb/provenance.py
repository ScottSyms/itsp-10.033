"""Source snapshotting, hashing, and provenance (spec S3.3, S3.4, S14)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from itsp_kb.config import DEFAULT_DATA_ROOT


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


def utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def raw_source_dir(source_id: str, retrieval_date: str, data_root: Path = DEFAULT_DATA_ROOT) -> Path:
    return data_root / "raw" / source_id / retrieval_date


def latest_raw_snapshot_dir(source_id: str, data_root: Path = DEFAULT_DATA_ROOT) -> Path | None:
    base = data_root / "raw" / source_id
    if not base.exists():
        return None
    dated = sorted((d for d in base.iterdir() if d.is_dir() and d.name != ".gitkeep"), reverse=True)
    return dated[0] if dated else None


def write_snapshot(
    *,
    source_id: str,
    publication: str,
    url: str,
    content: bytes,
    content_filename: str,
    configured_ref: str | None = None,
    resolved_commit: str | None = None,
    http_status: int | None = None,
    content_type: str | None = None,
    headers: dict[str, Any] | None = None,
    extra_fetch_fields: dict[str, Any] | None = None,
    data_root: Path = DEFAULT_DATA_ROOT,
    subdir: str | None = None,
) -> Path:
    """Write `data/raw/<source-id>/<date>[/<subdir>]/{content, fetch.json, sha256.txt, headers.json}`.

    `subdir` is used for multi-page sources (e.g. one ITSP.10.033 family per
    page) so each page gets its own fetch.json/sha256.txt rather than
    multiple pages overwriting a single shared metadata file.
    """
    date = today_str()
    out_dir = raw_source_dir(source_id, date, data_root=data_root)
    if subdir:
        out_dir = out_dir / subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / content_filename).write_bytes(content)

    digest = sha256_hex(content)
    (out_dir / "sha256.txt").write_text(f"{digest}  {content_filename}\n", encoding="utf-8")

    fetch_meta: dict[str, Any] = {
        "source_id": source_id,
        "publication": publication,
        "url": url,
        "configured_ref": configured_ref,
        "resolved_commit": resolved_commit,
        "retrieved_at": utcnow_iso(),
        "http_status": http_status,
        "content_type": content_type,
        "sha256": digest,
    }
    if extra_fetch_fields:
        fetch_meta.update(extra_fetch_fields)
    (out_dir / "fetch.json").write_text(json.dumps(fetch_meta, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    if headers is not None:
        (out_dir / "headers.json").write_text(json.dumps(headers, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return out_dir


def read_fetch_meta(snapshot_dir: Path) -> dict[str, Any]:
    return json.loads((snapshot_dir / "fetch.json").read_text(encoding="utf-8"))
