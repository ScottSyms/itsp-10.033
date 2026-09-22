"""Orchestrates all export stages (spec S11): JSONL/CSV catalogue, upstream NIST
copy, relationship graph, derived OSCAL catalog/profile. Embedding rendering is
deliberately separate (`itsp-kb render-embeddings`) since it takes a `--view`."""

from __future__ import annotations

from pathlib import Path

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.exporters.graph import export_edges
from itsp_kb.exporters.jsonl import export_catalogue_jsonl_csv, export_upstream_nist
from itsp_kb.exporters.oscal import export_oscal_catalog, export_oscal_medium_profile


def run_all_exports(*, data_root: Path = DEFAULT_DATA_ROOT, strict: bool = False) -> None:
    export_upstream_nist(data_root=data_root)
    export_catalogue_jsonl_csv(data_root=data_root)
    export_edges(data_root=data_root)
    export_oscal_catalog(data_root=data_root)
    export_oscal_medium_profile(data_root=data_root)
