"""Intermediate "parsed Canadian record" models -- the direct output of the
ITSP.10.033 HTML parser, before NIST reconciliation assigns `origin` /
`reconciliation_status` and produces the final `CatalogueRecord` (spec S7).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from itsp_kb.models.common import CanadaSourceRef, Odp, Reference, RequirementKind, StatementNode


class CanadianParsedEnhancement(BaseModel):
    id: str  # canonical, e.g. "AC-02(01)" or "AC-17(400)"
    parent_id: str
    enhancement_number: str
    name: str
    statements: list[StatementNode] = Field(default_factory=list)
    statement_text: str = ""
    discussion: str | None = None
    gc_discussion: str | None = None
    related: list[str] = Field(default_factory=list)
    odps: list[Odp] = Field(default_factory=list)
    is_canadian_specific: bool = False


class CanadianParsedRecord(BaseModel):
    id: str
    family_id: str
    family_name: str
    number: str
    name: str
    requirement_kind: RequirementKind
    is_canadian_specific: bool
    is_withdrawn: bool = False
    withdrawal_note: str | None = None
    statements: list[StatementNode] = Field(default_factory=list)
    statement_text: str = ""
    discussion: str | None = None
    gc_discussion: str | None = None
    related: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    odps: list[Odp] = Field(default_factory=list)
    enhancements: list[CanadianParsedEnhancement] = Field(default_factory=list)
    source: CanadaSourceRef
