"""Final Canadian catalogue record models (spec S5.3, S5.5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from itsp_kb.models.common import (
    Odp,
    Origin,
    ReconciliationStatus,
    RecordKind,
    RecordSources,
    Reference,
    RequirementKind,
    StatementNode,
)

SCHEMA_VERSION = "2.0"


class CanadianDelta(BaseModel):
    title_changed: bool = False
    statement_changed: bool = False
    discussion_changed: bool = False
    parameters_changed: bool = False
    related_changed: bool = False
    references_changed: bool = False
    requirement_kind_changed: bool = False
    fields: list[str] = Field(default_factory=list)


class CatalogueRecord(BaseModel):
    """A final Canadian base control/activity or enhancement record."""

    schema_version: str = SCHEMA_VERSION
    id: str
    family_id: str
    family_name: str
    number: str
    name: str

    record_kind: RecordKind
    requirement_kind: RequirementKind

    parent_id: str | None = None  # required for enhancements, None for base records
    enhancement_number: str | None = None

    origin: Origin
    nist_oscal_id: str | None = None
    reconciliation_status: ReconciliationStatus
    is_canadian_specific: bool = False
    is_withdrawn: bool = False
    withdrawal_note: str | None = None

    statements: list[StatementNode] = Field(default_factory=list)
    statement_text: str = ""
    discussion: str | None = None
    gc_discussion: str | None = None

    odps: list[Odp] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    enhancement_ids: list[str] = Field(default_factory=list)

    canadian_delta: CanadianDelta = Field(default_factory=CanadianDelta)

    profile_memberships: dict[str, bool] = Field(default_factory=dict)

    sources: RecordSources = Field(default_factory=RecordSources)

    content_hash: str | None = None
