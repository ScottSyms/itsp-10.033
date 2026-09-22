"""Reconcile the NIST upstream baseline against the parsed Canadian overlay
(spec S7.6-S7.14) and emit the final Canadian catalogue plus reconciliation
records.

Authority rule (spec S3.1, S7.9): Canadian text always wins in the final
dataset when the Cyber Centre restates a field. NIST is never copied into a
final field without a deterministic inheritance decision -- here, that
decision is "the comparison-normalized NIST and Canadian text are equal",
which is recorded as a field diff either way (`same`/`formatting_only` vs
`modified`), not silently assumed from matching ids.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import orjson
from pydantic import BaseModel

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.ids import parse_canadian_id
from itsp_kb.models.catalogue import CanadianDelta, CatalogueRecord
from itsp_kb.models.common import (
    FieldDiffKind,
    NistSourceRef,
    Origin,
    ReconciliationStatus,
    RecordKind,
    RecordSources,
    RequirementKind,
)
from itsp_kb.models.nist import NistUpstreamRecord
from itsp_kb.models.reconciliation import FieldDiff, ReconciliationRecord
from itsp_kb.parsers.itsp_10_033 import load_normalized_canada
from itsp_kb.parsers.nist_oscal import load_normalized_nist
from itsp_kb.provenance import sha256_text

logger = logging.getLogger(__name__)


class ReconciliationError(ValueError):
    def __init__(self, message: str, *, canadian_id: str | None = None):
        super().__init__(message)
        self.canadian_id = canadian_id


# --- Comparison normalization (spec S7.8) ---------------------------------------------------
#
# Allowed: collapse whitespace, normalize NBSP, normalize outline-marker punctuation, and
# collapse *both* the NIST `{{ insert: param, ID }}` template syntax and the Canadian
# `[Assignment: ...]`/`[Selection: ...]` bracket syntax to one placeholder token so ODP
# rendering differences don't register as a false "modified". Never paraphrases, drops modal
# verbs, reorders clauses, or removes meaningful list numbering.

_ODP_TOKEN = "‹ODP›"
_NIST_INSERT_RE = re.compile(r"\{\{\s*insert:\s*param,\s*[^}]+\}\}")
_CANADA_BRACKET_RE = re.compile(r"\[(?:Assignment|Selection)[^\]]*\]", re.IGNORECASE)
_OUTLINE_PREFIX_RE = re.compile(r"(?:^|\n)\([a-zA-Z0-9.]+\)\s*")
_WS_RE = re.compile(r"\s+")


def comparison_normalize(text: str) -> str:
    t = text.replace("\xa0", " ")
    t = _NIST_INSERT_RE.sub(_ODP_TOKEN, t)
    t = _CANADA_BRACKET_RE.sub(_ODP_TOKEN, t)
    t = _OUTLINE_PREFIX_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip().lower()
    return t


def _classify_diff(nist_raw: str, canada_raw: str) -> FieldDiffKind:
    if nist_raw.strip() == canada_raw.strip():
        return FieldDiffKind.SAME
    if comparison_normalize(nist_raw) == comparison_normalize(canada_raw):
        return FieldDiffKind.FORMATTING_ONLY
    return FieldDiffKind.MODIFIED


def _field_diff(field_name: str, nist_raw: str | None, canada_raw: str | None) -> FieldDiff:
    if nist_raw is None and canada_raw is None:
        return FieldDiff(field=field_name, kind=FieldDiffKind.SAME, normalization_equal=True)
    if nist_raw is None:
        return FieldDiff(
            field=field_name,
            kind=FieldDiffKind.CANADA_ONLY,
            canada_hash=sha256_text(canada_raw or ""),
            normalization_equal=False,
        )
    if canada_raw is None:
        return FieldDiff(
            field=field_name,
            kind=FieldDiffKind.NIST_ONLY,
            nist_hash=sha256_text(nist_raw),
            normalization_equal=False,
        )
    kind = _classify_diff(nist_raw, canada_raw)
    return FieldDiff(
        field=field_name,
        kind=kind,
        nist_hash=sha256_text(nist_raw),
        canada_hash=sha256_text(canada_raw),
        normalization_equal=kind in (FieldDiffKind.SAME, FieldDiffKind.FORMATTING_ONLY),
    )


# --- NIST-side text flattening (mirrors itsp_kb.parsers.html_utils' Canadian flattening) -----


def _oscal_statement_lines(parts: list, prefix: str = "") -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for p in parts:
        if p.name == "item":
            label = p.id.rsplit("_smt.", 1)[-1] if p.id and "_smt." in p.id else p.id or ""
            if p.prose:
                lines.append((label, p.prose))
            lines.extend(_oscal_statement_lines(p.parts, label))
        else:
            lines.extend(_oscal_statement_lines(p.parts, prefix))
    return lines


def nist_statement_text(record: NistUpstreamRecord) -> str:
    stmt_parts = [p for p in record.parts if p.name == "statement"]
    lines: list[tuple[str, str]] = []
    for sp in stmt_parts:
        if sp.prose:
            lines.append(("", sp.prose))
        lines.extend(_oscal_statement_lines(sp.parts))
    return "\n".join(f"({label}) {prose}" if label else prose for label, prose in lines if prose)


def nist_discussion_text(record: NistUpstreamRecord) -> str | None:
    guidance = [p for p in record.parts if p.name == "guidance"]
    parts_text = [p.prose for p in guidance if p.prose]
    return "\n\n".join(parts_text) or None


def nist_odp_count(record: NistUpstreamRecord) -> int:
    # NOTE: this counts every OSCAL `*_odp.NN` param, including ones an aggregator param
    # (a `prm` whose `props` list `aggregates` two or more `_odp.` ids) merges into a single
    # rendered bracket -- so this can slightly overcount relative to the number of distinct
    # `[Assignment: ...]`/`[Selection: ...]` brackets a reader actually sees, in both the NIST
    # and Canadian renderings. It's a deterministic, reproducible heuristic for flagging a
    # parameter-count mismatch worth reviewing (spec S5.10), not a claim of exact correspondence.
    return sum(1 for p in record.params if p.id and "_odp." in p.id)


def nist_related_ids(record: NistUpstreamRecord) -> set[str]:
    from itsp_kb.ids import IdMappingError, oscal_id_to_canonical_any

    ids: set[str] = set()
    for link in record.links:
        if link.rel != "related" or not link.href.startswith("#"):
            continue
        oscal_id = link.href[1:]
        try:
            ids.add(oscal_id_to_canonical_any(oscal_id))
        except IdMappingError:
            continue
    return ids


# --- Core reconciliation ---------------------------------------------------------------------


@dataclass
class ReconciledBundle:
    catalogue_records: list[CatalogueRecord] = field(default_factory=list)
    reconciliation_records: list[ReconciliationRecord] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def _diff_against_nist(
    *,
    canadian_id: str,
    title_canada: str,
    statement_canada: str,
    discussion_canada: str | None,
    related_canada: list[str],
    odp_count_canada: int,
    nist_record: NistUpstreamRecord,
) -> tuple[list[FieldDiff], CanadianDelta]:
    diffs: list[FieldDiff] = []
    delta = CanadianDelta()

    title_diff = _field_diff("title", nist_record.title, title_canada)
    diffs.append(title_diff)
    if title_diff.kind == FieldDiffKind.MODIFIED:
        delta.title_changed = True
        delta.fields.append("title")

    stmt_diff = _field_diff("statement_text", nist_statement_text(nist_record), statement_canada)
    diffs.append(stmt_diff)
    if stmt_diff.kind == FieldDiffKind.MODIFIED:
        delta.statement_changed = True
        delta.fields.append("statement_text")

    disc_diff = _field_diff("discussion", nist_discussion_text(nist_record), discussion_canada)
    diffs.append(disc_diff)
    if disc_diff.kind == FieldDiffKind.MODIFIED:
        delta.discussion_changed = True
        delta.fields.append("discussion")

    nist_odps = nist_odp_count(nist_record)
    params_diff = FieldDiff(
        field="odp_count",
        kind=FieldDiffKind.SAME if nist_odps == odp_count_canada else FieldDiffKind.MODIFIED,
        detail=f"nist={nist_odps} canada={odp_count_canada}",
        normalization_equal=nist_odps == odp_count_canada,
    )
    diffs.append(params_diff)
    if params_diff.kind == FieldDiffKind.MODIFIED:
        delta.parameters_changed = True
        delta.fields.append("odps")

    nist_rel = nist_related_ids(nist_record)
    canada_rel = set(related_canada)
    related_diff = FieldDiff(
        field="related",
        kind=FieldDiffKind.SAME if nist_rel == canada_rel else FieldDiffKind.MODIFIED,
        detail=f"nist_only={sorted(nist_rel - canada_rel)} canada_only={sorted(canada_rel - nist_rel)}"
        if nist_rel != canada_rel
        else None,
        normalization_equal=nist_rel == canada_rel,
    )
    diffs.append(related_diff)
    if related_diff.kind == FieldDiffKind.MODIFIED:
        delta.related_changed = True
        delta.fields.append("related")

    return diffs, delta


def _reconcile_one(
    *,
    canonical_id: str,
    family_id: str,
    family_name: str,
    number: str,
    name: str,
    requirement_kind: RequirementKind,
    is_canadian_specific: bool,
    is_withdrawn: bool,
    withdrawal_note: str | None,
    statements,
    statement_text: str,
    discussion: str | None,
    gc_discussion: str | None,
    related: list[str],
    references,
    odps,
    enhancement_ids: list[str],
    canada_source_ref,
    nist_by_canonical: dict[str, NistUpstreamRecord],
    strict: bool,
) -> tuple[CatalogueRecord, ReconciliationRecord]:
    nist_match = None if is_canadian_specific else nist_by_canonical.get(canonical_id)

    delta = CanadianDelta()
    field_diffs: list[FieldDiff] = []
    canada_only_fields: list[str] = []
    nist_only_fields: list[str] = []
    review_required = False

    if is_canadian_specific:
        origin = Origin.CANADA_ONLY
        status = ReconciliationStatus.VERIFIED_CANADA_ONLY
        canada_only_fields = ["title", "statement_text", "discussion", "related"]
    elif nist_match is None:
        origin = Origin.UNKNOWN
        status = ReconciliationStatus.UNRESOLVED
        review_required = True
        if strict and not is_withdrawn:
            raise ReconciliationError(
                f"'{canonical_id}' has no NIST OSCAL match and is not a 400-series Canada-only record",
                canadian_id=canonical_id,
            )
        else:
            logger.warning("'%s' has no NIST OSCAL match; marked unresolved", canonical_id)
    elif requirement_kind == RequirementKind.ACTIVITY:
        origin = Origin.NIST_RECLASSIFIED_ACTIVITY
        status = ReconciliationStatus.VERIFIED_RECLASSIFIED
        delta.requirement_kind_changed = True
        delta.fields.append("requirement_kind")
        field_diffs, _ = _diff_against_nist(
            canadian_id=canonical_id,
            title_canada=name,
            statement_canada=statement_text,
            discussion_canada=discussion,
            related_canada=related,
            odp_count_canada=len(odps),
            nist_record=nist_match,
        )
    else:
        field_diffs, delta = _diff_against_nist(
            canadian_id=canonical_id,
            title_canada=name,
            statement_canada=statement_text,
            discussion_canada=discussion,
            related_canada=related,
            odp_count_canada=len(odps),
            nist_record=nist_match,
        )
        # Title is intentionally excluded from the inherited-vs-modified decision: the Cyber
        # Centre systematically prefixes many titles with the family name (e.g. NIST "Policy
        # and Procedures" -> Canadian "Access control policy and procedures" for every family's
        # -01 control), which is a documented naming convention, not a case-by-case content
        # modification. The title diff is still recorded in `field_diffs`/`canadian_delta` for
        # transparency; it just doesn't by itself flip a record to verified_modified.
        any_change = (
            delta.statement_changed or delta.discussion_changed or delta.parameters_changed or delta.related_changed
        )
        if any_change:
            origin = Origin.NIST_MODIFIED_CANADA
            status = ReconciliationStatus.VERIFIED_MODIFIED
        else:
            origin = Origin.NIST_INHERITED
            status = ReconciliationStatus.VERIFIED_INHERITED

    if is_withdrawn and nist_match is not None:
        # The Canadian source has withdrawn/consolidated something the NIST baseline still
        # lists as active -- a real, explicit divergence, not something to paper over.
        delta.fields.append("withdrawn")
        origin = Origin.NIST_MODIFIED_CANADA
        status = ReconciliationStatus.VERIFIED_MODIFIED

    if gc_discussion:
        canada_only_fields.append("gc_discussion")

    reconciliation_record = ReconciliationRecord(
        canadian_id=canonical_id,
        nist_oscal_id=nist_match.upstream_id if nist_match else None,
        status=status,
        field_diffs=field_diffs,
        canada_only_fields=canada_only_fields,
        nist_only_fields=nist_only_fields,
        review_required=review_required,
    )

    sources = RecordSources(
        nist=(
            NistSourceRef(
                publication=nist_match.source.publication,
                metadata_version=nist_match.source.metadata_version,
                oscal_version=nist_match.source.oscal_version,
                git_commit=nist_match.source.git_commit,
                source_sha256=nist_match.source.source_sha256,
            )
            if nist_match
            else None
        ),
        canada=canada_source_ref,
    )

    record_kind = RecordKind.ENHANCEMENT if "(" in canonical_id else RecordKind.BASE
    parsed = parse_canadian_id(canonical_id)

    catalogue_record = CatalogueRecord(
        id=canonical_id,
        family_id=family_id,
        family_name=family_name,
        number=number,
        name=name,
        record_kind=record_kind,
        requirement_kind=requirement_kind,
        parent_id=parsed.base_id if record_kind == RecordKind.ENHANCEMENT else None,
        enhancement_number=parsed.enh_num,
        origin=origin,
        nist_oscal_id=nist_match.upstream_id if nist_match else None,
        reconciliation_status=status,
        is_canadian_specific=is_canadian_specific,
        is_withdrawn=is_withdrawn,
        withdrawal_note=withdrawal_note,
        statements=statements,
        statement_text=statement_text,
        discussion=discussion,
        gc_discussion=gc_discussion,
        odps=odps,
        related=related,
        references=references if record_kind == RecordKind.BASE else [],
        enhancement_ids=enhancement_ids,
        canadian_delta=delta,
        sources=sources,
    )
    catalogue_record.content_hash = sha256_text(
        orjson.dumps(catalogue_record.model_dump(mode="json", exclude={"content_hash"})).decode()
    )
    return catalogue_record, reconciliation_record


def run_reconciliation(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    family_filter: str | None = None,
    strict: bool = False,
) -> ReconciledBundle:
    nist_result = load_normalized_nist(data_root=data_root)
    nist_by_canonical: dict[str, NistUpstreamRecord] = {r.canonical_candidate_id: r for r in nist_result.records}

    canadian_records = load_normalized_canada(data_root=data_root)
    if family_filter:
        canadian_records = [r for r in canadian_records if r.family_id == family_filter]

    bundle = ReconciledBundle()
    seen_nist_targets: dict[str, str] = {}

    for canadian in canadian_records:
        catalogue_record, reconciliation_record = _reconcile_one(
            canonical_id=canadian.id,
            family_id=canadian.family_id,
            family_name=canadian.family_name,
            number=canadian.number,
            name=canadian.name,
            requirement_kind=canadian.requirement_kind,
            is_canadian_specific=canadian.is_canadian_specific,
            is_withdrawn=canadian.is_withdrawn,
            withdrawal_note=canadian.withdrawal_note,
            statements=canadian.statements,
            statement_text=canadian.statement_text,
            discussion=canadian.discussion,
            gc_discussion=canadian.gc_discussion,
            related=canadian.related,
            references=canadian.references,
            odps=canadian.odps,
            enhancement_ids=[e.id for e in canadian.enhancements],
            canada_source_ref=canadian.source,
            nist_by_canonical=nist_by_canonical,
            strict=strict,
        )
        _check_duplicate_mapping(catalogue_record, seen_nist_targets, strict=strict)
        bundle.catalogue_records.append(catalogue_record)
        bundle.reconciliation_records.append(reconciliation_record)

        for enh in canadian.enhancements:
            enh_record, enh_reconciliation = _reconcile_one(
                canonical_id=enh.id,
                family_id=canadian.family_id,
                family_name=canadian.family_name,
                number=canadian.number,
                name=enh.name,
                requirement_kind=canadian.requirement_kind,
                is_canadian_specific=enh.is_canadian_specific,
                is_withdrawn=False,
                withdrawal_note=None,
                statements=enh.statements,
                statement_text=enh.statement_text,
                discussion=enh.discussion,
                gc_discussion=enh.gc_discussion,
                related=enh.related,
                references=[],
                odps=enh.odps,
                enhancement_ids=[],
                canada_source_ref=canadian.source,
                nist_by_canonical=nist_by_canonical,
                strict=strict,
            )
            _check_duplicate_mapping(enh_record, seen_nist_targets, strict=strict)
            bundle.catalogue_records.append(enh_record)
            bundle.reconciliation_records.append(enh_reconciliation)

    bundle.counts = _compute_counts(bundle)
    _write_output(bundle, data_root=data_root)
    return bundle


def _check_duplicate_mapping(record: CatalogueRecord, seen: dict[str, str], *, strict: bool) -> None:
    if record.nist_oscal_id is None:
        return
    prior = seen.get(record.nist_oscal_id)
    if prior is not None and prior != record.id:
        msg = f"NIST id '{record.nist_oscal_id}' is mapped from both '{prior}' and '{record.id}'"
        if strict:
            raise ReconciliationError(msg, canadian_id=record.id)
        logger.warning(msg)
    seen[record.nist_oscal_id] = record.id


def _compute_counts(bundle: ReconciledBundle) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in bundle.catalogue_records:
        counts[r.reconciliation_status.value] = counts.get(r.reconciliation_status.value, 0) + 1
    return counts


def _write_jsonl(path: Path, models: Sequence[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for m in models:
            f.write(orjson.dumps(m.model_dump(mode="json")))
            f.write(b"\n")


def _write_output(bundle: ReconciledBundle, *, data_root: Path) -> None:
    recon_dir = data_root / "output" / "reconciliation"
    _write_jsonl(recon_dir / "records.jsonl", bundle.reconciliation_records)

    catalogue_dir = data_root / "normalized" / "reconciliation"
    _write_jsonl(catalogue_dir / "catalogue.jsonl", bundle.catalogue_records)

    report = _build_report(bundle)
    (recon_dir / "report.json").write_bytes(orjson.dumps(report, option=orjson.OPT_INDENT_2))
    (recon_dir / "report.md").write_text(_report_markdown(report), encoding="utf-8")


def _build_report(bundle: ReconciledBundle) -> dict:
    field_change_counts: dict[str, int] = {}
    for rec in bundle.reconciliation_records:
        for fd in rec.field_diffs:
            if fd.kind == FieldDiffKind.MODIFIED:
                field_change_counts[fd.field] = field_change_counts.get(fd.field, 0) + 1
    return {
        "counts": bundle.counts,
        "total_records": len(bundle.catalogue_records),
        "field_change_counts": field_change_counts,
        "unresolved_ids": [r.id for r in bundle.catalogue_records if r.reconciliation_status.value == "unresolved"],
    }


def _report_markdown(report: dict) -> str:
    lines = ["# ITSP.10.033 Reconciliation Report", ""]
    lines.append(f"Total records: {report['total_records']}")
    lines.append("")
    lines.append("## Reconciliation status")
    for status, count in sorted(report["counts"].items()):
        lines.append(f"- {status}: {count}")
    lines.append("")
    lines.append("## Field-level change counts (modified)")
    for f_name, count in sorted(report["field_change_counts"].items()):
        lines.append(f"- {f_name}: {count}")
    if report["unresolved_ids"]:
        lines.append("")
        lines.append("## Unresolved records")
        for rid in report["unresolved_ids"]:
            lines.append(f"- {rid}")
    return "\n".join(lines) + "\n"


def load_catalogue(data_root: Path = DEFAULT_DATA_ROOT) -> list[CatalogueRecord]:
    path = data_root / "normalized" / "reconciliation" / "catalogue.jsonl"
    return [CatalogueRecord.model_validate(orjson.loads(line)) for line in path.read_bytes().splitlines() if line]
