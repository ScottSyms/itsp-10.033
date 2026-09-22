"""Typed loader for the source registry (config/sources.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES_PATH = REPO_ROOT / "config" / "sources.yaml"
DEFAULT_DATA_ROOT = REPO_ROOT / "data"


class FamilyEntry(BaseModel):
    id: str
    name: str
    slug: str


class SourceEntry(BaseModel):
    publication: str
    title: str
    type: str
    authority: str
    language: str = "en"
    enabled: bool = True

    format: str | None = None
    repository: str | None = None
    path: str | None = None
    raw_url: str | None = None
    api_commits_url: str | None = None
    source_ref: str | None = None

    root_url: str | None = None
    toc_url: str | None = None
    families: list[FamilyEntry] = Field(default_factory=list)


class SourceRegistry(BaseModel):
    sources: dict[str, SourceEntry]

    def enabled_sources(self) -> dict[str, SourceEntry]:
        return {k: v for k, v in self.sources.items() if v.enabled}

    def __getitem__(self, key: str) -> SourceEntry:
        return self.sources[key]


def load_registry(path: Path | None = None) -> SourceRegistry:
    path = path or DEFAULT_SOURCES_PATH
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return SourceRegistry.model_validate(raw)
