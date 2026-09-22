"""Medium-impact profile record models (spec S8.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from itsp_kb.models.common import RequirementKind


class ProfileSource(BaseModel):
    table: str
    url: str
    retrieved_at: str
    source_sha256: str
    source_type: str = "html"  # "html" | "official_spreadsheet"


class ProfileRecord(BaseModel):
    profile_id: str = "medium"
    profile_publication: str = "ITSP.10.033-01"
    control_id: str
    family_id: str
    name: str
    requirement_kind: RequirementKind
    selected: bool
    suggested_enhancements: list[str] = Field(default_factory=list)
    suggested_placeholder_values_raw: str | None = None
    profile_specific_notes: str | None = None
    description_raw: str | None = None
    source: ProfileSource


class ProfileMetadata(BaseModel):
    profile_id: str = "medium"
    publication: str = "ITSP.10.033-01"
    effective_date: str | None = None
    superseded_publication: str | None = None
    impact_values: dict[str, str] = Field(default_factory=dict)
