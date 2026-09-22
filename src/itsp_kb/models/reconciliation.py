"""Reconciliation record models (spec S7.7)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from itsp_kb.models.common import FieldDiffKind, ReconciliationStatus


class FieldDiff(BaseModel):
    field: str
    kind: FieldDiffKind
    nist_hash: str | None = None
    canada_hash: str | None = None
    normalization_equal: bool = False
    detail: str | None = None


class ReconciliationRecord(BaseModel):
    canadian_id: str
    nist_oscal_id: str | None
    status: ReconciliationStatus
    field_diffs: list[FieldDiff] = Field(default_factory=list)
    canada_only_fields: list[str] = Field(default_factory=list)
    nist_only_fields: list[str] = Field(default_factory=list)
    review_required: bool = False
