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


def build_manifest(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    extractor_version: str,
    schema_version: str,
    validation_passed: bool,
    validation_warnings: list[str],
) -> dict[str, Any]:
    """The build manifest (spec S14.1). Counts are always calculated from the
    persisted output, never hard-coded."""
    import orjson

    def _load_jsonl(path: Path) -> list[dict]:
        if not path.exists():
            return []
        return [orjson.loads(line) for line in path.read_bytes().splitlines() if line]

    nist_records = _load_jsonl(data_root / "normalized" / "nist" / "records.jsonl")
    catalogue = _load_jsonl(data_root / "normalized" / "reconciliation" / "catalogue.jsonl")
    profile_rows = _load_jsonl(data_root / "output" / "profiles" / "medium.jsonl")
    edges = _load_jsonl(data_root / "output" / "relationships" / "edges.jsonl")

    record_counts = {
        "nist_records": len(nist_records),
        "canadian_base_records": sum(1 for r in catalogue if r.get("record_kind") == "base"),
        "canadian_enhancements": sum(1 for r in catalogue if r.get("record_kind") == "enhancement"),
        "verified_inherited": sum(1 for r in catalogue if r.get("reconciliation_status") == "verified_inherited"),
        "verified_modified": sum(1 for r in catalogue if r.get("reconciliation_status") == "verified_modified"),
        "verified_reclassified": sum(1 for r in catalogue if r.get("reconciliation_status") == "verified_reclassified"),
        "verified_canada_only": sum(1 for r in catalogue if r.get("reconciliation_status") == "verified_canada_only"),
        "unresolved": sum(1 for r in catalogue if r.get("reconciliation_status") == "unresolved"),
        "profile_rows": len(profile_rows),
        "edges": len(edges),
    }

    sources: dict[str, Any] = {}
    nist_meta_path = data_root / "normalized" / "nist" / "metadata.json"
    if nist_meta_path.exists():
        nist_meta = orjson.loads(nist_meta_path.read_bytes())
        sources["nist"] = {
            "metadata_version": nist_meta.get("metadata_version"),
            "oscal_version": nist_meta.get("oscal_version"),
            "git_commit": nist_meta.get("git_commit"),
            "source_sha256": nist_meta.get("source_sha256"),
        }
    for source_id, key in (("itsp_10_033", "itsp_10_033"), ("itsp_10_033_01", "itsp_10_033_01")):
        snap_dir = latest_raw_snapshot_dir(source_id, data_root=data_root)
        if snap_dir is None:
            continue
        if source_id == "itsp_10_033":
            # Multi-page source: hash across all family fetch.json files for one composite marker.
            hashes = []
            for sub in sorted(snap_dir.iterdir()):
                fj = sub / "fetch.json"
                if fj.exists():
                    hashes.append(json.loads(fj.read_text(encoding="utf-8"))["sha256"])
            sources[key] = {"source_sha256": sha256_text("".join(sorted(hashes)))}
        else:
            fj = snap_dir / "fetch.json"
            if fj.exists():
                sources[key] = {"source_sha256": json.loads(fj.read_text(encoding="utf-8"))["sha256"]}

    return {
        "build_id": utcnow_iso(),
        "schema_version": schema_version,
        "extractor_version": extractor_version,
        "sources": sources,
        "record_counts": record_counts,
        "validation": {"passed": validation_passed, "warnings": validation_warnings},
    }
