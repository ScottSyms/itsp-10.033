"""Shared enums and small value types used across the NIST, catalogue, reconciliation,
and profile models (spec S5)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Origin(StrEnum):
    NIST_INHERITED = "nist_inherited"
    NIST_MODIFIED_CANADA = "nist_modified_canada"
    NIST_RECLASSIFIED_ACTIVITY = "nist_reclassified_activity"
    CANADA_ONLY = "canada_only"
    UNKNOWN = "unknown"


class ReconciliationStatus(StrEnum):
    VERIFIED_INHERITED = "verified_inherited"
    VERIFIED_MODIFIED = "verified_modified"
    VERIFIED_RECLASSIFIED = "verified_reclassified"
    VERIFIED_CANADA_ONLY = "verified_canada_only"
    UNRESOLVED = "unresolved"


class RequirementKind(StrEnum):
    CONTROL = "control"
    ACTIVITY = "activity"
    UNKNOWN = "unknown"


class RecordKind(StrEnum):
    BASE = "base"
    ENHANCEMENT = "enhancement"


class FieldDiffKind(StrEnum):
    SAME = "same"
    FORMATTING_ONLY = "formatting_only"
    MODIFIED = "modified"
    CANADA_ONLY = "canada_only"
    NIST_ONLY = "nist_only"
    UNRESOLVED = "unresolved"


class OdpOperation(StrEnum):
    ASSIGNMENT = "assignment"
    SELECTION = "selection"
    UNKNOWN = "unknown"


class NistSourceRef(BaseModel):
    publication: str = "NIST SP 800-53 Rev. 5"
    metadata_version: str
    oscal_version: str
    git_commit: str
    source_sha256: str


class CanadaSourceRef(BaseModel):
    publication: str
    url: str
    section: str | None = None
    retrieved_at: str
    source_sha256: str


class RecordSources(BaseModel):
    nist: NistSourceRef | None = None
    canada: CanadaSourceRef | None = None


class Family(BaseModel):
    id: str
    name: str
    publication: str
    nist_group_id: str | None = None
    source_url: str | None = None
    source_hash: str | None = None


class Reference(BaseModel):
    title: str
    url: str | None = None
    publisher: str | None = None
    external: bool = True
    source_authority: str  # "NIST" | "Canada"


class Odp(BaseModel):
    odp_id: str
    nist_param_id: str | None = None
    operation: OdpOperation = OdpOperation.UNKNOWN
    cardinality: str | None = None
    raw: str
    prompt: str | None = None
    options: list[str] = []
    statement_path: str | None = None
    character_start: int | None = None
    character_end: int | None = None


class StatementNode(BaseModel):
    path: str
    source_designator: str | None = None
    text: str
    children: list[StatementNode] = []
