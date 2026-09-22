"""`itsp-kb build`: the complete deterministic pipeline (spec S25 Phase 6,
S15). Runs fetch -> import-nist -> parse-canada -> reconcile -> parse-profile
-> validate -> export -> render-embeddings -> manifest, and keeps going even
when a fetch is skipped (offline) as long as prior snapshots exist.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from itsp_kb.config import DEFAULT_DATA_ROOT, load_registry
from itsp_kb.exporters.embeddings import render_embedding_records
from itsp_kb.exporters.run import run_all_exports
from itsp_kb.fetch import fetch_all
from itsp_kb.models.catalogue import SCHEMA_VERSION
from itsp_kb.parsers.itsp_10_033 import parse_all_families
from itsp_kb.parsers.itsp_10_033_01 import parse_and_join_profile
from itsp_kb.parsers.nist_oscal import import_nist_oscal
from itsp_kb.provenance import build_manifest
from itsp_kb.reconcile import run_reconciliation
from itsp_kb.validate import validate_all

logger = logging.getLogger(__name__)


def _extractor_version() -> str:
    try:
        return version("itsp-kb")
    except PackageNotFoundError:
        return "0.0.0+dev"


def run_build(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    strict: bool = False,
    offline: bool = False,
    force_fetch: bool = False,
    nist_ref: str | None = None,
    allow_newer_oscal: bool = False,
) -> None:
    registry = load_registry()

    logger.info("build: fetch (offline=%s)", offline)
    fetch_all(registry, offline=offline, force=force_fetch, nist_ref=nist_ref, data_root=data_root, strict=strict)

    logger.info("build: import-nist")
    import_nist_oscal(data_root=data_root, strict=strict, allow_newer_oscal=allow_newer_oscal)

    logger.info("build: parse-canada")
    parse_all_families(data_root=data_root, strict=strict)

    logger.info("build: reconcile")
    run_reconciliation(data_root=data_root, strict=strict)

    logger.info("build: parse-profile medium")
    parse_and_join_profile(profile_id="medium", data_root=data_root, strict=strict)

    logger.info("build: validate")
    report = validate_all(data_root=data_root, strict=strict)
    for w in report.warnings:
        logger.warning(w)
    for e in report.errors:
        logger.error(e)
    if strict and not report.passed:
        raise RuntimeError(f"Validation failed with {len(report.errors)} error(s) in strict mode.")

    logger.info("build: export")
    run_all_exports(data_root=data_root, strict=strict)
    render_embedding_records(view="requirement_only", data_root=data_root)

    logger.info("build: manifest")
    manifest = build_manifest(
        data_root=data_root,
        extractor_version=_extractor_version(),
        schema_version=SCHEMA_VERSION,
        validation_passed=report.passed,
        validation_warnings=report.warnings,
    )
    _write_manifest(manifest, registry, data_root=data_root)

    logger.info(
        "build complete: %d records, validation passed=%s",
        manifest["record_counts"]["canadian_base_records"] + manifest["record_counts"]["canadian_enhancements"],
        report.passed,
    )


def _write_manifest(manifest: dict, registry, *, data_root: Path) -> None:
    import orjson

    out_dir = data_root / "output" / "manifests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "build.json").write_bytes(orjson.dumps(manifest, option=orjson.OPT_INDENT_2))
    (out_dir / "sources.json").write_bytes(
        orjson.dumps({k: v.model_dump(mode="json") for k, v in registry.sources.items()}, option=orjson.OPT_INDENT_2)
    )
