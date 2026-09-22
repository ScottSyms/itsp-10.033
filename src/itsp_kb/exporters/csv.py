"""CSV convenience export (spec S11.2). Kept as a thin re-export: the CSV and
JSONL catalogue exports are derived from the same loaded records in one pass
in `itsp_kb.exporters.jsonl` to avoid loading the catalogue twice."""

from __future__ import annotations

from itsp_kb.exporters.jsonl import export_catalogue_jsonl_csv as export_catalogue

__all__ = ["export_catalogue"]
