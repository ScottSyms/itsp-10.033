from pathlib import Path

import pytest

from itsp_kb.parsers.nist_oscal import (
    OscalVersionError,
    import_nist_oscal,
    parse_oscal_document,
)
from itsp_kb.provenance import sha256_hex, write_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "nist_oscal" / "minimal_catalog.json"


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    raw = FIXTURE.read_bytes()
    write_snapshot(
        source_id="nist_sp800_53_rev5_oscal",
        publication="NIST SP 800-53 Rev. 5",
        url="file://fixture",
        content=raw,
        content_filename="catalog.json",
        configured_ref="fixture",
        resolved_commit="0" * 40,
        http_status=200,
        content_type="application/json",
        data_root=tmp_path,
    )
    return tmp_path


def test_parse_oscal_document():
    doc = parse_oscal_document(FIXTURE.read_bytes())
    assert doc.catalog.metadata.oscal_version
    assert len(doc.catalog.groups) == 2


def test_import_produces_expected_records(data_root: Path):
    result = import_nist_oscal(data_root=data_root)

    by_id = {r.upstream_id: r for r in result.records}
    assert set(by_id) == {"ac-1", "ac-2", "ac-2.1", "sa-8", "sa-8.33"}

    ac1 = by_id["ac-1"]
    assert ac1.canonical_candidate_id == "AC-01"
    assert ac1.family_id == "AC"
    assert ac1.parent_upstream_id is None
    assert any(p.name == "statement" for p in ac1.parts)
    assert len(ac1.params) > 0

    ac2 = by_id["ac-2"]
    assert ac2.canonical_candidate_id == "AC-02"
    assert ac2.child_control_ids == ["ac-2.1"]

    ac2_1 = by_id["ac-2.1"]
    assert ac2_1.canonical_candidate_id == "AC-02(01)"
    assert ac2_1.parent_upstream_id == "ac-2"

    sa8_33 = by_id["sa-8.33"]
    assert sa8_33.canonical_candidate_id == "SA-08(33)"


def test_import_is_idempotent_and_hashes_source(data_root: Path):
    result = import_nist_oscal(data_root=data_root)
    expected_hash = sha256_hex(FIXTURE.read_bytes())
    assert result.metadata.source_sha256 == expected_hash
    assert result.metadata.control_count == len(result.records)

    result2 = import_nist_oscal(data_root=data_root)
    assert [r.upstream_id for r in result.records] == [r.upstream_id for r in result2.records]


def test_relationships_include_enhancement_edges(data_root: Path):
    result = import_nist_oscal(data_root=data_root)
    rels = {(r.source_id, r.relationship, r.target_id) for r in result.relationships}
    assert ("AC-02(01)", "enhancement_of", "AC-02") in rels
    assert ("AC-02", "has_enhancement", "AC-02(01)") in rels


def test_no_duplicate_upstream_ids(data_root: Path):
    # Note: this fixture only contains 2 of the 20 real families, so it can't be run
    # through the family-completeness strict check -- that's covered separately against
    # the full real catalog (see the offline/integration fixtures).
    result = import_nist_oscal(data_root=data_root)
    ids = [r.upstream_id for r in result.records]
    assert len(ids) == len(set(ids))


def test_rejects_newer_oscal_version_unless_allowed(data_root: Path, monkeypatch):
    from itsp_kb.parsers import nist_oscal

    monkeypatch.setattr(nist_oscal, "MAX_SUPPORTED_OSCAL_VERSION", (0, 0, 1))
    with pytest.raises(OscalVersionError):
        import_nist_oscal(data_root=data_root)
    # Should succeed with the escape hatch.
    import_nist_oscal(data_root=data_root, allow_newer_oscal=True)
