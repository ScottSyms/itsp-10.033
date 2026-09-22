from pathlib import Path

from itsp_kb.exporters.graph import build_edges


def test_canadian_and_upstream_edges_are_distinguished(reconciled_data_root: Path):
    edges = build_edges(data_root=reconciled_data_root)
    lineages = {e.lineage for e in edges}
    assert lineages == {"canada", "nist_upstream"}


def test_enhancement_edges_present_both_directions(reconciled_data_root: Path):
    edges = build_edges(data_root=reconciled_data_root)
    canada_edges = {(e.source_id, e.relationship, e.target_id) for e in edges if e.lineage == "canada"}
    assert ("AC-02(01)", "enhancement_of", "AC-02") in canada_edges
    assert ("AC-02", "has_enhancement", "AC-02(01)") in canada_edges


def test_related_to_edges_from_canadian_catalogue(reconciled_data_root: Path):
    edges = build_edges(data_root=reconciled_data_root)
    canada_related = {
        (e.source_id, e.target_id) for e in edges if e.lineage == "canada" and e.relationship == "related_to"
    }
    assert ("AC-01", "IA-01") in canada_related
