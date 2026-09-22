"""Data model stubs reserved for the future lifecycle/assessment publications
(ITSP.10.036, ITSP.10.037, ITSP.10.033-02 -- spec S10). Not populated by v1;
kept here only so the schema is extensible without a breaking redesign."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrganizationalActivity(BaseModel):
    """ITSP.10.036 organizational risk-management activity (spec S10.1)."""

    id: str
    publication: str = "ITSP.10.036"
    kind: str = "organizational_activity"
    phase: str
    title: str
    text: str
    related_control_ids: list[str] = Field(default_factory=list)
    source: dict = Field(default_factory=dict)


class SystemLifecycleActivity(BaseModel):
    """ITSP.10.037 system-lifecycle activity (spec S10.2)."""

    id: str
    publication: str = "ITSP.10.037"
    lifecycle_phase: str
    activity: str
    role: str | None = None
    input: str | None = None
    output: str | None = None
    evidence_artifact: str | None = None
    sal: str | None = None
    related_controls: list[str] = Field(default_factory=list)
    source: dict = Field(default_factory=dict)


class AssessmentProcedure(BaseModel):
    """ITSP.10.033-02 assessment/evidence-layer object (spec S10.3)."""

    assessment_id: str
    control_id: str
    objective: str
    methods: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    expected_evidence: list[str] = Field(default_factory=list)
    source: dict = Field(default_factory=dict)
