"""NIST SP 800-53 Rev. 5 OSCAL Catalog importer (spec S6).

Parses the official OSCAL Catalog JSON into the normalized upstream records
described in spec S5.2, using the NIST importer as "the structured seed for
all NIST-derived ITSP records" (S6.1) rather than reconstructing controls
from prose. Canonical Canadian candidate ids are derived from the *actual*
OSCAL nesting (via `itsp_kb.ids.map_child_control`), not string splitting
alone (S5.6).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import orjson
from pydantic import BaseModel

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.ids import IdMappingError, map_child_control, oscal_control_id_to_canonical
from itsp_kb.models.nist import (
    NistFamily,
    NistRelationshipEdge,
    NistUpstreamMetadata,
    NistUpstreamRecord,
    NistUpstreamSource,
    OscalCatalogDocument,
    OscalControl,
    OscalPart,
)
from itsp_kb.provenance import latest_raw_snapshot_dir, read_fetch_meta

logger = logging.getLogger(__name__)

# The highest OSCAL Catalog version this parser declares compatibility with
# (spec S6.3). A higher `oscal-version` in the source fails validation unless
# `--allow-newer-oscal` is passed.
MAX_SUPPORTED_OSCAL_VERSION = (1, 2, 2)

# The 20 SP 800-53 Rev. 5 control-family group ids (spec S5.1), used only to
# report a family-set mismatch -- unrecognized groups are still fully retained.
KNOWN_FAMILY_IDS = {
    "ac",
    "at",
    "au",
    "ca",
    "cm",
    "cp",
    "ia",
    "ir",
    "ma",
    "mp",
    "pe",
    "pl",
    "pm",
    "ps",
    "pt",
    "ra",
    "sa",
    "sc",
    "si",
    "sr",
}

# Part names this importer has explicit semantic knowledge of (spec S6.7).
# Any other part name is still fully preserved (Part is structurally
# lossless) but is counted as "unmapped" for validation visibility.
KNOWN_PART_NAMES = {
    "statement",
    "item",
    "guidance",
    "assessment-objective",
    "assessment-method",
    "assessment-objects",
    "objective",
    "overview",
}


class OscalVersionError(ValueError):
    pass


class NistImportError(ValueError):
    def __init__(self, message: str, *, control_id: str | None = None):
        super().__init__(message)
        self.control_id = control_id


@dataclass
class NistImportResult:
    families: list[NistFamily] = field(default_factory=list)
    records: list[NistUpstreamRecord] = field(default_factory=list)
    relationships: list[NistRelationshipEdge] = field(default_factory=list)
    metadata: NistUpstreamMetadata | None = None


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def _check_oscal_version(oscal_version: str, allow_newer_oscal: bool) -> None:
    parsed = _version_tuple(oscal_version)
    if parsed > MAX_SUPPORTED_OSCAL_VERSION and not allow_newer_oscal:
        raise OscalVersionError(
            f"OSCAL catalog version {oscal_version} is newer than the highest version this "
            f"parser declares compatibility with ({'.'.join(map(str, MAX_SUPPORTED_OSCAL_VERSION))}); "
            "pass --allow-newer-oscal to proceed anyway."
        )


def _count_unmapped_parts(parts: list[OscalPart]) -> int:
    count = 0
    for p in parts:
        if p.name not in KNOWN_PART_NAMES:
            count += 1
        count += _count_unmapped_parts(p.parts)
    return count


def _walk_controls(
    controls: list[OscalControl],
    *,
    family_id: str,
    parent_upstream_id: str | None,
    parent_canonical_id: str | None,
    source: NistUpstreamSource,
    records: list[NistUpstreamRecord],
    relationships: list[NistRelationshipEdge],
    seen_ids: set[str],
    strict: bool,
) -> list[str]:
    """Recursively walk OSCAL controls, returning the list of upstream ids at this level."""
    ids_at_this_level: list[str] = []
    for control in controls:
        if control.id in seen_ids:
            msg = f"Duplicate OSCAL control id encountered: '{control.id}'"
            if strict:
                raise NistImportError(msg, control_id=control.id)
            logger.warning(msg)
        seen_ids.add(control.id)

        if parent_canonical_id is None:
            try:
                canonical_id = oscal_control_id_to_canonical(control.id)
            except IdMappingError as e:
                msg = f"Could not derive a canonical id for base control '{control.id}': {e}"
                if strict:
                    raise NistImportError(msg, control_id=control.id) from e
                logger.warning(msg)
                canonical_id = control.id.upper()
        else:
            assert parent_upstream_id is not None
            try:
                canonical_id = map_child_control(control.id, parent_canonical_id, parent_upstream_id)
            except IdMappingError as e:
                msg = f"Could not derive a canonical id for enhancement '{control.id}': {e}"
                if strict:
                    raise NistImportError(msg, control_id=control.id) from e
                logger.warning(msg)
                canonical_id = f"{parent_canonical_id}({control.id.rsplit('.', 1)[-1]})"

        child_ids = _walk_controls(
            control.controls,
            family_id=family_id,
            parent_upstream_id=control.id,
            parent_canonical_id=canonical_id,
            source=source,
            records=records,
            relationships=relationships,
            seen_ids=seen_ids,
            strict=strict,
        )

        unmapped: dict[str, Any] = {}
        unmapped_count = _count_unmapped_parts(control.parts)
        if unmapped_count:
            unmapped["unmapped_part_count"] = unmapped_count

        records.append(
            NistUpstreamRecord(
                upstream_id=control.id,
                canonical_candidate_id=canonical_id,
                family_id=family_id,
                title=control.title,
                parent_upstream_id=parent_upstream_id,
                props=control.props,
                params=control.params,
                parts=control.parts,
                child_control_ids=child_ids,
                links=control.links,
                unmapped=unmapped,
                source=source,
            )
        )
        if parent_upstream_id is not None and parent_canonical_id is not None:
            relationships.append(
                NistRelationshipEdge(
                    source_id=canonical_id, relationship="enhancement_of", target_id=parent_canonical_id
                )
            )
            relationships.append(
                NistRelationshipEdge(
                    source_id=parent_canonical_id, relationship="has_enhancement", target_id=canonical_id
                )
            )
        ids_at_this_level.append(control.id)
    return ids_at_this_level


def parse_oscal_document(raw: bytes) -> OscalCatalogDocument:
    return OscalCatalogDocument.model_validate(orjson.loads(raw))


def import_nist_oscal(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    strict: bool = False,
    allow_newer_oscal: bool = False,
) -> NistImportResult:
    snapshot_dir = latest_raw_snapshot_dir("nist_sp800_53_rev5_oscal", data_root=data_root)
    if snapshot_dir is None:
        raise FileNotFoundError(
            "No NIST OSCAL snapshot found under data/raw/nist_sp800_53_rev5_oscal/; run `itsp-kb fetch` first."
        )
    fetch_meta = read_fetch_meta(snapshot_dir)
    raw = (snapshot_dir / "catalog.json").read_bytes()
    doc = parse_oscal_document(raw)
    cat = doc.catalog

    _check_oscal_version(cat.metadata.oscal_version, allow_newer_oscal)

    source = NistUpstreamSource(
        metadata_version=cat.metadata.version,
        oscal_version=cat.metadata.oscal_version,
        git_commit=fetch_meta["resolved_commit"],
        source_sha256=fetch_meta["sha256"],
    )

    families: list[NistFamily] = []
    records: list[NistUpstreamRecord] = []
    relationships: list[NistRelationshipEdge] = []
    seen_ids: set[str] = set()

    discovered_family_ids = {g.id for g in cat.groups}
    missing = KNOWN_FAMILY_IDS - discovered_family_ids
    extra = discovered_family_ids - KNOWN_FAMILY_IDS
    if missing or extra:
        msg = (
            f"NIST OSCAL group set differs from expected SP 800-53 families: "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )
        if strict:
            raise NistImportError(msg)
        logger.warning(msg)

    for group in cat.groups:
        family_id = group.id.upper()
        control_ids = _walk_controls(
            group.controls,
            family_id=family_id,
            parent_upstream_id=None,
            parent_canonical_id=None,
            source=source,
            records=records,
            relationships=relationships,
            seen_ids=seen_ids,
            strict=strict,
        )
        families.append(
            NistFamily(
                id=family_id,
                title=group.title,
                oscal_group_id=group.id,
                props=group.props,
                links=group.links,
                control_ids=control_ids,
            )
        )

    unmapped_structure_count = sum(1 for r in records if r.unmapped)

    metadata = NistUpstreamMetadata(
        title=cat.metadata.title,
        metadata_version=cat.metadata.version,
        oscal_version=cat.metadata.oscal_version,
        git_commit=fetch_meta["resolved_commit"],
        source_sha256=fetch_meta["sha256"],
        retrieved_at=fetch_meta["retrieved_at"],
        group_count=len(families),
        control_count=len(records),
        unmapped_structure_count=unmapped_structure_count,
    )

    _write_normalized_output(families, records, relationships, metadata, data_root=data_root)
    return NistImportResult(families=families, records=records, relationships=relationships, metadata=metadata)


def _write_jsonl(path: Path, models: Sequence[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for m in models:
            f.write(orjson.dumps(m.model_dump(mode="json")))
            f.write(b"\n")


def _write_normalized_output(
    families: list[NistFamily],
    records: list[NistUpstreamRecord],
    relationships: list[NistRelationshipEdge],
    metadata: NistUpstreamMetadata,
    *,
    data_root: Path,
) -> None:
    out_dir = data_root / "normalized" / "nist"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "families.json").write_bytes(
        orjson.dumps([f.model_dump(mode="json") for f in families], option=orjson.OPT_INDENT_2)
    )
    _write_jsonl(out_dir / "records.jsonl", records)
    _write_jsonl(out_dir / "relationships.jsonl", relationships)
    (out_dir / "metadata.json").write_bytes(orjson.dumps(metadata.model_dump(mode="json"), option=orjson.OPT_INDENT_2))


def load_normalized_nist(data_root: Path = DEFAULT_DATA_ROOT) -> NistImportResult:
    """Load the already-written normalized NIST dataset (for reconciliation/inspection)."""
    out_dir = data_root / "normalized" / "nist"
    families = [NistFamily.model_validate(f) for f in orjson.loads((out_dir / "families.json").read_bytes())]
    records = [
        NistUpstreamRecord.model_validate(orjson.loads(line))
        for line in (out_dir / "records.jsonl").read_bytes().splitlines()
        if line
    ]
    relationships = [
        NistRelationshipEdge.model_validate(orjson.loads(line))
        for line in (out_dir / "relationships.jsonl").read_bytes().splitlines()
        if line
    ]
    metadata = NistUpstreamMetadata.model_validate(orjson.loads((out_dir / "metadata.json").read_bytes()))
    return NistImportResult(families=families, records=records, relationships=relationships, metadata=metadata)


# --- Semantic part-view helpers (spec S6.7) -------------------------------------------------


def statement_parts(record: NistUpstreamRecord) -> list[OscalPart]:
    return [p for p in record.parts if p.name == "statement"]


def guidance_parts(record: NistUpstreamRecord) -> list[OscalPart]:
    return [p for p in record.parts if p.name == "guidance"]


def assessment_objective_parts(record: NistUpstreamRecord) -> list[OscalPart]:
    return [p for p in record.parts if p.name == "assessment-objective"]
