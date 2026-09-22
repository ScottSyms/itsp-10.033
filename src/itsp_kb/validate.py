"""Standalone `itsp-kb validate` checks over whatever is currently on disk
(spec S16): NIST layer, canonical id, Canadian structural, reconciliation,
catalogue/profile completeness, and a few semantic safety heuristics.

This does not re-parse anything; it re-validates persisted output so it can
be run on its own against a build someone else produced, per spec S15.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.ids import CANADIAN_ANY_ID_RE, IdMappingError, parse_canadian_id
from itsp_kb.parsers.itsp_10_033 import load_normalized_canada
from itsp_kb.parsers.nist_oscal import KNOWN_FAMILY_IDS, load_normalized_nist
from itsp_kb.reconcile import load_catalogue

NAV_LEAKAGE_MARKERS = ("Top of page", "Table of Contents", "Skip to main content")

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def _load_validator(schema_filename: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / schema_filename).read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _validate_json_schema(report: ValidationReport, data_root: Path) -> None:
    import orjson

    checks = [
        ("normalized/reconciliation/catalogue.jsonl", "control.schema.json", "catalogue record"),
        ("normalized/nist/records.jsonl", "nist_record.schema.json", "NIST record"),
        ("output/reconciliation/records.jsonl", "reconciliation.schema.json", "reconciliation record"),
        ("output/profiles/medium.jsonl", "profile.schema.json", "profile record"),
    ]
    for rel_path, schema_name, label in checks:
        path = data_root / rel_path
        if not path.exists():
            continue
        validator = _load_validator(schema_name)
        for i, line in enumerate(path.read_bytes().splitlines()):
            if not line:
                continue
            obj = orjson.loads(line)
            errors = sorted(validator.iter_errors(obj), key=lambda e: e.path)
            for err in errors[:1]:  # one representative error per invalid row is enough signal
                report.errors.append(
                    f"Schema validation failed for {label} at line {i + 1} ({rel_path}): {err.message}"
                )


class ValidationReport(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _fail_or_warn(report: ValidationReport, message: str, *, strict: bool) -> None:
    if strict:
        report.errors.append(message)
    else:
        report.warnings.append(message)


def _validate_nist_layer(report: ValidationReport, data_root: Path, strict: bool) -> None:
    try:
        nist = load_normalized_nist(data_root=data_root)
    except FileNotFoundError:
        report.warnings.append("No normalized NIST dataset found; skipping NIST-layer checks.")
        return

    ids_seen = [r.upstream_id for r in nist.records]
    if len(ids_seen) != len(set(ids_seen)):
        report.errors.append("Duplicate upstream OSCAL control ids found in normalized NIST dataset.")

    by_id = {r.upstream_id: r for r in nist.records}
    for r in nist.records:
        for child_id in r.child_control_ids:
            if child_id not in by_id:
                report.errors.append(f"NIST record '{r.upstream_id}' references missing child '{child_id}'.")

    discovered_family_ids = {f.oscal_group_id for f in nist.families}
    missing = KNOWN_FAMILY_IDS - discovered_family_ids
    extra = discovered_family_ids - KNOWN_FAMILY_IDS
    if missing or extra:
        _fail_or_warn(
            report,
            f"NIST family set differs from expected SP 800-53 families: "
            f"missing={sorted(missing)} extra={sorted(extra)}",
            strict=strict,
        )


def _validate_catalogue(report: ValidationReport, data_root: Path, strict: bool) -> None:
    try:
        catalogue = load_catalogue(data_root=data_root)
    except FileNotFoundError:
        report.warnings.append("No reconciled catalogue found; skipping catalogue checks.")
        return

    ids_seen = [r.id for r in catalogue]
    if len(ids_seen) != len(set(ids_seen)):
        dupes = sorted({i for i in ids_seen if ids_seen.count(i) > 1})
        report.errors.append(f"Duplicate Canadian canonical ids in catalogue: {dupes}")

    by_id = {r.id: r for r in catalogue}
    discovered_families: set[str] = set()

    for r in catalogue:
        discovered_families.add(r.family_id)

        if not CANADIAN_ANY_ID_RE.match(r.id):
            report.errors.append(f"Record id '{r.id}' does not match the accepted canonical id pattern.")
            continue

        try:
            parsed = parse_canadian_id(r.id)
        except IdMappingError as e:
            report.errors.append(str(e))
            continue

        if parsed.family != r.family_id:
            report.errors.append(f"Record '{r.id}' family_id '{r.family_id}' disagrees with its id prefix.")

        if r.record_kind.value == "enhancement":
            if not r.parent_id or r.parent_id not in by_id:
                report.errors.append(f"Enhancement '{r.id}' has an unresolved parent_id '{r.parent_id}'.")
        else:
            for enh_id in r.enhancement_ids:
                if enh_id not in by_id:
                    report.errors.append(f"Base record '{r.id}' references missing enhancement '{enh_id}'.")

        if not r.is_withdrawn and not r.statement_text.strip() and r.requirement_kind.value != "unknown":
            _fail_or_warn(report, f"Active record '{r.id}' has an empty requirement statement.", strict=strict)

        if r.statement_text.count("[") != r.statement_text.count("]"):
            report.errors.append(f"Record '{r.id}' has unbalanced ODP bracket delimiters in its statement text.")

        for related_id in r.related:
            if not CANADIAN_ANY_ID_RE.match(related_id):
                report.errors.append(f"Record '{r.id}' has a related id '{related_id}' with an invalid format.")

        if r.sources.canada is None:
            report.errors.append(f"Record '{r.id}' has no Canadian source reference.")
        if r.nist_oscal_id and r.sources.nist is None:
            report.errors.append(f"Record '{r.id}' has nist_oscal_id set but no NIST source reference.")

        if not r.is_canadian_specific and r.nist_oscal_id is None and r.reconciliation_status.value != "unresolved":
            report.errors.append(f"Record '{r.id}' has no NIST mapping but is not marked unresolved or Canada-only.")

        if r.is_canadian_specific and r.nist_oscal_id is not None:
            report.errors.append(f"Canada-only record '{r.id}' unexpectedly has a NIST mapping.")

        if r.reconciliation_status.value == "unresolved" and not r.is_withdrawn:
            _fail_or_warn(report, f"Record '{r.id}' is unresolved.", strict=strict)

        if r.reconciliation_status.value == "verified_modified" and not r.canadian_delta.fields:
            report.warnings.append(f"Record '{r.id}' is verified_modified but has no recorded delta fields.")

        for marker in NAV_LEAKAGE_MARKERS:
            if marker in r.statement_text or (r.discussion and marker in r.discussion):
                report.errors.append(f"Record '{r.id}' appears to contain page-navigation text ('{marker}').")

    missing_families = KNOWN_FAMILY_IDS - {f.lower() for f in discovered_families}
    if missing_families:
        _fail_or_warn(
            report,
            f"Catalogue is missing expected families: {sorted(f.upper() for f in missing_families)}",
            strict=strict,
        )


def _validate_profile(report: ValidationReport, data_root: Path) -> None:
    profile_path = data_root / "output" / "profiles" / "medium.jsonl"
    if not profile_path.exists():
        report.warnings.append("No Medium-profile output found; skipping profile checks.")
        return
    import orjson

    rows = [orjson.loads(line) for line in profile_path.read_bytes().splitlines() if line]
    if not rows:
        report.errors.append("Medium-profile output exists but contains zero rows.")
    families = {r["family_id"] for r in rows}
    missing = KNOWN_FAMILY_IDS - {f.lower() for f in families}
    if missing:
        report.warnings.append(f"Medium profile is missing rows for families: {sorted(f.upper() for f in missing)}")


def _validate_canadian_parse_completeness(report: ValidationReport, data_root: Path, strict: bool) -> None:
    try:
        records = load_normalized_canada(data_root=data_root)
    except FileNotFoundError:
        report.warnings.append("No normalized Canadian dataset found; skipping parse-completeness checks.")
        return
    per_family: dict[str, int] = {}
    for r in records:
        per_family[r.family_id] = per_family.get(r.family_id, 0) + 1
    zero_record_families = KNOWN_FAMILY_IDS - {f.lower() for f in per_family}
    if zero_record_families:
        _fail_or_warn(
            report,
            f"No Canadian records parsed for families: {sorted(f.upper() for f in zero_record_families)}",
            strict=strict,
        )


def validate_all(*, data_root: Path = DEFAULT_DATA_ROOT, strict: bool = False) -> ValidationReport:
    report = ValidationReport(passed=True)
    _validate_nist_layer(report, data_root, strict)
    _validate_canadian_parse_completeness(report, data_root, strict)
    _validate_catalogue(report, data_root, strict)
    _validate_profile(report, data_root)
    _validate_json_schema(report, data_root)
    report.passed = len(report.errors) == 0
    return report
