"""Deterministic embedding-ready text records (spec S12).

No embedding model is invoked here or anywhere in extraction (S12.1); this
produces the text/metadata records an external embedding step would consume
later. Views are S12.5's `requirement_only`, `requirement_plus_discussion`,
`full`, and `canada_delta`.
"""

from __future__ import annotations

import csv as csv_module
from pathlib import Path

import orjson
from pydantic import BaseModel

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.models.catalogue import CatalogueRecord
from itsp_kb.reconcile import load_catalogue

VALID_VIEWS = {"requirement_only", "requirement_plus_discussion", "full", "canada_delta"}


class EmbeddingRecord(BaseModel):
    embedding_id: str
    record_id: str
    record_kind: str
    family_id: str
    family_name: str
    name: str
    requirement_kind: str
    origin: str
    reconciliation_status: str
    profile_medium: bool
    is_canadian_specific: bool
    is_withdrawn: bool
    has_odp: bool
    has_gc_discussion: bool
    view: str
    text: str
    source_publication: str
    source_url: str | None
    canadian_source_hash: str | None
    nist_source_hash: str | None


def _yes_no(v: bool) -> str:
    return "yes" if v else "no"


def _render_odps(record: CatalogueRecord) -> str:
    if not record.odps:
        return "None."
    lines = []
    for odp in record.odps:
        kind = odp.operation.value.capitalize()
        lines.append(f"- [{kind}] {odp.prompt or odp.raw}")
    return "\n".join(lines)


def _render_related(record: CatalogueRecord) -> str:
    return ", ".join(record.related) if record.related else "None."


def _profile_section(record: CatalogueRecord, profile_notes: dict[str, tuple[str | None, str | None]]) -> str:
    selected = record.profile_memberships.get("medium")
    placeholder, notes = profile_notes.get(record.id, (None, None))
    lines = [
        "Medium-impact profile:",
        f"Selected: {_yes_no(bool(selected))}" if selected is not None else "Selected: not assessed",
        f"Suggested enhancements: {', '.join(record.enhancement_ids) if record.enhancement_ids else 'None.'}",
        f"Suggested placeholder values: {placeholder or 'None.'}",
        f"Profile-specific notes: {notes or 'None.'}",
    ]
    return "\n".join(lines)


def _render_text(record: CatalogueRecord, view: str, profile_notes: dict[str, tuple[str | None, str | None]]) -> str:
    header = (
        f"ID: {record.id}\n"
        f"Family: {record.family_name}\n"
        f"Name: {record.name}\n"
        f"Type: {record.requirement_kind.value}\n"
        f"Origin: {record.origin.value}\n"
        f"Canadian-specific: {_yes_no(record.is_canadian_specific)}"
    )
    requirement = f"Requirement:\n{record.statement_text or 'None.'}"
    odps = f"Organization-defined parameters:\n{_render_odps(record)}"

    if view == "requirement_only":
        return "\n\n".join([header, requirement, odps])

    discussion = f"Discussion:\n{record.discussion or 'None.'}"
    gc_discussion = f"Government of Canada discussion:\n{record.gc_discussion or 'None.'}"

    if view == "requirement_plus_discussion":
        return "\n\n".join([header, requirement, odps, discussion, gc_discussion])

    related = f"Related controls and activities:\n{_render_related(record)}"
    profile = _profile_section(record, profile_notes)

    if view == "full":
        return "\n\n".join([header, requirement, odps, discussion, gc_discussion, related, profile])

    if view == "canada_delta":
        # Focused on what's Canadian-specific or changed -- not the full unchanged upstream text.
        parts = [header]
        if record.is_canadian_specific:
            parts.append(requirement)
            parts.append(odps)
        elif record.canadian_delta.statement_changed:
            parts.append(requirement)
        if record.canadian_delta.fields:
            parts.append("Canadian delta fields:\n" + ", ".join(record.canadian_delta.fields))
        if record.gc_discussion:
            parts.append(gc_discussion)
        if record.canadian_delta.discussion_changed and record.discussion:
            parts.append(discussion)
        parts.append(profile)
        return "\n\n".join(parts)

    raise ValueError(f"Unknown embedding view: {view}")


def render_embedding_records(
    *, view: str = "requirement_only", data_root: Path = DEFAULT_DATA_ROOT
) -> list[EmbeddingRecord]:
    if view not in VALID_VIEWS:
        raise ValueError(f"Unknown embedding view '{view}'; must be one of {sorted(VALID_VIEWS)}")

    catalogue = load_catalogue(data_root=data_root)

    profile_notes: dict[str, tuple[str | None, str | None]] = {}
    profile_path = data_root / "output" / "profiles" / "medium.jsonl"
    if profile_path.exists():
        for line in profile_path.read_bytes().splitlines():
            if not line:
                continue
            row = orjson.loads(line)
            profile_notes[row["control_id"]] = (
                row.get("suggested_placeholder_values_raw"),
                row.get("profile_specific_notes"),
            )

    records: list[EmbeddingRecord] = []
    for r in catalogue:
        text = _render_text(r, view, profile_notes)
        records.append(
            EmbeddingRecord(
                embedding_id=f"ITSP.10.033:{r.id}",
                record_id=r.id,
                record_kind=r.record_kind.value,
                family_id=r.family_id,
                family_name=r.family_name,
                name=r.name,
                requirement_kind=r.requirement_kind.value,
                origin=r.origin.value,
                reconciliation_status=r.reconciliation_status.value,
                profile_medium=bool(r.profile_memberships.get("medium")),
                is_canadian_specific=r.is_canadian_specific,
                is_withdrawn=r.is_withdrawn,
                has_odp=bool(r.odps),
                has_gc_discussion=bool(r.gc_discussion),
                view=view,
                text=text,
                source_publication="ITSP.10.033",
                source_url=r.sources.canada.url if r.sources.canada else None,
                canadian_source_hash=r.sources.canada.source_sha256 if r.sources.canada else None,
                nist_source_hash=r.sources.nist.source_sha256 if r.sources.nist else None,
            )
        )

    _write_output(records, view=view, data_root=data_root)
    return records


def _write_output(records: list[EmbeddingRecord], *, view: str, data_root: Path) -> None:
    out_dir = data_root / "output" / "embeddings"
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / "embedding_records.jsonl"
    with jsonl_path.open("wb") as f:
        for r in records:
            f.write(orjson.dumps(r.model_dump(mode="json")))
            f.write(b"\n")

    csv_path = out_dir / "embedding_records.csv"
    fieldnames = list(EmbeddingRecord.model_fields.keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv_module.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r.model_dump(mode="json"))
