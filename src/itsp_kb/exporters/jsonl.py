"""JSONL/CSV catalogue exports (spec S11.1, S11.2) -- the canonical simplified
Canadian knowledge-base representation, plus a CSV convenience export."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import orjson

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.models.catalogue import CatalogueRecord
from itsp_kb.models.common import RecordKind
from itsp_kb.parsers.nist_oscal import load_normalized_nist
from itsp_kb.reconcile import load_catalogue


def _write_jsonl(path: Path, records: list[CatalogueRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for r in records:
            f.write(orjson.dumps(r.model_dump(mode="json")))
            f.write(b"\n")


def export_catalogue_jsonl_csv(*, data_root: Path = DEFAULT_DATA_ROOT) -> None:
    catalogue = load_catalogue(data_root=data_root)
    out_dir = data_root / "output" / "catalogue"
    out_dir.mkdir(parents=True, exist_ok=True)

    bases = [r for r in catalogue if r.record_kind == RecordKind.BASE]
    enhancements = [r for r in catalogue if r.record_kind == RecordKind.ENHANCEMENT]

    _write_jsonl(out_dir / "controls.jsonl", bases)
    _write_jsonl(out_dir / "enhancements.jsonl", enhancements)
    _write_jsonl(out_dir / "all_records.jsonl", catalogue)

    nist_result = load_normalized_nist(data_root=data_root)
    families = sorted({(r.family_id, r.family_name) for r in catalogue})
    nist_group_by_family = {f.id: f.oscal_group_id for f in nist_result.families}
    families_payload = [
        {"id": fid, "name": fname, "publication": "ITSP.10.033", "nist_group_id": nist_group_by_family.get(fid)}
        for fid, fname in families
    ]
    (out_dir / "families.json").write_bytes(orjson.dumps(families_payload, option=orjson.OPT_INDENT_2))

    _write_controls_csv(out_dir / "controls.csv", bases)


def _write_controls_csv(path: Path, records: list[CatalogueRecord]) -> None:
    fieldnames = [
        "id",
        "family_id",
        "family_name",
        "name",
        "record_kind",
        "requirement_kind",
        "origin",
        "reconciliation_status",
        "is_canadian_specific",
        "is_withdrawn",
        "nist_oscal_id",
        "statement_text",
        "discussion",
        "gc_discussion",
        "related",
        "enhancement_ids",
        "canadian_delta_fields",
        "profile_memberships",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "id": r.id,
                    "family_id": r.family_id,
                    "family_name": r.family_name,
                    "name": r.name,
                    "record_kind": r.record_kind.value,
                    "requirement_kind": r.requirement_kind.value,
                    "origin": r.origin.value,
                    "reconciliation_status": r.reconciliation_status.value,
                    "is_canadian_specific": r.is_canadian_specific,
                    "is_withdrawn": r.is_withdrawn,
                    "nist_oscal_id": r.nist_oscal_id or "",
                    "statement_text": r.statement_text,
                    "discussion": r.discussion or "",
                    "gc_discussion": r.gc_discussion or "",
                    "related": json.dumps(r.related),
                    "enhancement_ids": json.dumps(r.enhancement_ids),
                    "canadian_delta_fields": json.dumps(r.canadian_delta.fields),
                    "profile_memberships": json.dumps(r.profile_memberships),
                }
            )


def export_upstream_nist(*, data_root: Path = DEFAULT_DATA_ROOT) -> None:
    """Duplicate the normalized NIST dataset under data/output/upstream/nist/ (spec S11)."""
    import shutil

    src = data_root / "normalized" / "nist"
    dst = data_root / "output" / "upstream" / "nist"
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("families.json", "records.jsonl", "relationships.jsonl", "metadata.json"):
        shutil.copyfile(src / name, dst / name)
