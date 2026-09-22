"""OSCAL Catalog models (spec S6.2) and the normalized NIST upstream record (spec S5.2).

These mirror the OSCAL JSON shape closely enough to avoid losing information
(spec S6.10 "OSCAL round-trip safety") while still being a plain internal
representation -- this is *not* an attempt at a general OSCAL library.

OSCAL's `class` property is a reserved word in Python, so it is exposed here as
`class_` via a field alias; `populate_by_name=True` lets code construct these
models with either spelling.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_ALIASED = ConfigDict(extra="allow", populate_by_name=True)


class OscalProp(BaseModel):
    model_config = _ALIASED

    name: str
    value: str
    ns: str | None = None
    class_: str | None = Field(default=None, alias="class")
    uuid: str | None = None


class OscalLink(BaseModel):
    model_config = _ALIASED

    href: str
    rel: str | None = None
    media_type: str | None = Field(default=None, alias="media-type")
    text: str | None = None
    resolved_resource: dict[str, Any] | None = None


class OscalSelect(BaseModel):
    model_config = _ALIASED

    how_many: str | None = Field(default=None, alias="how-many")
    choice: list[str] = []


class OscalGuideline(BaseModel):
    model_config = _ALIASED

    prose: str


class OscalParam(BaseModel):
    model_config = _ALIASED

    id: str
    label: str | None = None
    usage: str | None = None
    values: list[str] = []
    select: OscalSelect | None = None
    constraints: list[dict[str, Any]] = []
    guidelines: list[OscalGuideline] = []
    props: list[OscalProp] = []
    links: list[OscalLink] = []


class OscalPart(BaseModel):
    model_config = _ALIASED

    id: str | None = None
    name: str
    ns: str | None = None
    class_: str | None = Field(default=None, alias="class")
    title: str | None = None
    prose: str | None = None
    props: list[OscalProp] = []
    links: list[OscalLink] = []
    parts: list[OscalPart] = []


class OscalControl(BaseModel):
    model_config = _ALIASED

    id: str
    class_: str | None = Field(default=None, alias="class")
    title: str
    params: list[OscalParam] = []
    props: list[OscalProp] = []
    links: list[OscalLink] = []
    parts: list[OscalPart] = []
    controls: list[OscalControl] = []  # nested enhancements


class OscalGroup(BaseModel):
    model_config = _ALIASED

    id: str
    class_: str | None = Field(default=None, alias="class")
    title: str
    props: list[OscalProp] = []
    links: list[OscalLink] = []
    controls: list[OscalControl] = []
    groups: list[OscalGroup] = []


class OscalBackMatterResource(BaseModel):
    model_config = _ALIASED

    uuid: str
    title: str | None = None
    rlinks: list[dict[str, Any]] = []
    citation: dict[str, Any] | None = None


class OscalBackMatter(BaseModel):
    model_config = _ALIASED

    resources: list[OscalBackMatterResource] = []


class OscalMetadata(BaseModel):
    model_config = _ALIASED

    title: str
    last_modified: str = Field(alias="last-modified")
    version: str
    oscal_version: str = Field(alias="oscal-version")


class OscalCatalog(BaseModel):
    model_config = _ALIASED

    uuid: str | None = None
    metadata: OscalMetadata
    groups: list[OscalGroup] = []
    controls: list[OscalControl] = []
    back_matter: OscalBackMatter | None = Field(default=None, alias="back-matter")


class OscalCatalogDocument(BaseModel):
    """Top-level `{"catalog": {...}}` document as published by NIST."""

    model_config = _ALIASED

    catalog: OscalCatalog


# --- Normalized upstream record (spec S5.2) -------------------------------------------------


class NistUpstreamSource(BaseModel):
    publication: str = "NIST SP 800-53 Rev. 5"
    metadata_version: str
    oscal_version: str
    git_commit: str
    source_sha256: str


class NistUpstreamRecord(BaseModel):
    upstream_id: str  # OSCAL control id, e.g. "ac-2"
    canonical_candidate_id: str  # e.g. "AC-02"
    family_id: str
    title: str
    oscal_uuid: str | None = None
    parent_upstream_id: str | None = None
    props: list[OscalProp] = []
    params: list[OscalParam] = []
    parts: list[OscalPart] = []
    child_control_ids: list[str] = []
    links: list[OscalLink] = []
    unmapped: dict[str, Any] = {}
    source: NistUpstreamSource


class NistFamily(BaseModel):
    id: str
    title: str
    oscal_group_id: str
    props: list[OscalProp] = []
    links: list[OscalLink] = []
    control_ids: list[str] = []


class NistRelationshipEdge(BaseModel):
    source_id: str
    relationship: str  # "enhancement_of" | "has_enhancement" | "related_to" (upstream-only)
    target_id: str
    lineage: str = "nist_upstream"


class NistUpstreamMetadata(BaseModel):
    publication: str = "NIST SP 800-53 Rev. 5"
    title: str
    metadata_version: str
    oscal_version: str
    git_commit: str
    source_sha256: str
    retrieved_at: str
    group_count: int
    control_count: int
    unmapped_structure_count: int
