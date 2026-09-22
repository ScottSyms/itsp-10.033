"""Relationship graph export (spec S7.12, S11.4).

`edges.jsonl` distinguishes Canadian-authoritative edges (derived from the
final reconciled catalogue's own `related`/`parent_id`/`enhancement_ids`
fields) from upstream-only NIST edges (derived straight from the OSCAL
`rel="related"` links and the nesting hierarchy) -- the two are never
merged into one undifferentiated edge, per S7.12's "NIST-only upstream edges
... MUST NOT be silently treated as ITSP relationships unless reconciled."
"""

from __future__ import annotations

from pathlib import Path

import orjson
from pydantic import BaseModel

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.models.common import RecordKind
from itsp_kb.parsers.nist_oscal import load_normalized_nist
from itsp_kb.reconcile import load_catalogue, nist_related_ids


class Edge(BaseModel):
    source_id: str
    relationship: str  # "related_to" | "enhancement_of" | "has_enhancement"
    target_id: str
    source_publication: str
    lineage: str  # "canada" | "nist_upstream"


def build_edges(*, data_root: Path = DEFAULT_DATA_ROOT) -> list[Edge]:
    catalogue = load_catalogue(data_root=data_root)
    edges: list[Edge] = []

    for r in catalogue:
        for target in r.related:
            edges.append(
                Edge(
                    source_id=r.id,
                    relationship="related_to",
                    target_id=target,
                    source_publication="ITSP.10.033",
                    lineage="canada",
                )
            )
        if r.record_kind == RecordKind.BASE:
            for enh_id in r.enhancement_ids:
                edges.append(
                    Edge(
                        source_id=r.id,
                        relationship="has_enhancement",
                        target_id=enh_id,
                        source_publication="ITSP.10.033",
                        lineage="canada",
                    )
                )
        elif r.parent_id:
            edges.append(
                Edge(
                    source_id=r.id,
                    relationship="enhancement_of",
                    target_id=r.parent_id,
                    source_publication="ITSP.10.033",
                    lineage="canada",
                )
            )

    nist_result = load_normalized_nist(data_root=data_root)
    for rec in nist_result.records:
        for target in nist_related_ids(rec):
            edges.append(
                Edge(
                    source_id=rec.canonical_candidate_id,
                    relationship="related_to",
                    target_id=target,
                    source_publication="NIST SP 800-53 Rev. 5",
                    lineage="nist_upstream",
                )
            )
    for rel in nist_result.relationships:
        edges.append(
            Edge(
                source_id=rel.source_id,
                relationship=rel.relationship,
                target_id=rel.target_id,
                source_publication="NIST SP 800-53 Rev. 5",
                lineage="nist_upstream",
            )
        )

    return edges


def export_edges(*, data_root: Path = DEFAULT_DATA_ROOT) -> list[Edge]:
    edges = build_edges(data_root=data_root)
    out_path = data_root / "output" / "relationships" / "edges.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        for e in edges:
            f.write(orjson.dumps(e.model_dump(mode="json")))
            f.write(b"\n")
    return edges
