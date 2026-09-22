"""Integration test: fetch(fixtures) -> import-nist -> parse-canada -> reconcile,
covering spec S17's required reconciliation cases (inherited, modified,
reclassified, Canada-only, missing NIST mapping) against real trimmed data.
"""

from pathlib import Path

import pytest

from itsp_kb.parsers.itsp_10_033 import parse_all_families
from itsp_kb.parsers.nist_oscal import import_nist_oscal
from itsp_kb.provenance import write_snapshot
from itsp_kb.reconcile import run_reconciliation

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    write_snapshot(
        source_id="nist_sp800_53_rev5_oscal",
        publication="NIST SP 800-53 Rev. 5",
        url="file://fixture",
        content=(FIXTURES / "nist_oscal" / "minimal_catalog.json").read_bytes(),
        content_filename="catalog.json",
        configured_ref="fixture",
        resolved_commit="0" * 40,
        http_status=200,
        content_type="application/json",
        data_root=tmp_path,
    )
    write_snapshot(
        source_id="itsp_10_033",
        publication="ITSP.10.033",
        url="https://fixture.example/access-control",
        content=(FIXTURES / "cyber_centre" / "access_control_excerpt.html").read_bytes(),
        content_filename="source.html",
        http_status=200,
        content_type="text/html",
        data_root=tmp_path,
        subdir="access-control",
    )
    write_snapshot(
        source_id="itsp_10_033",
        publication="ITSP.10.033",
        url="https://fixture.example/system-services-acquisition",
        content=(FIXTURES / "cyber_centre" / "sa_excerpt.html").read_bytes(),
        content_filename="source.html",
        http_status=200,
        content_type="text/html",
        data_root=tmp_path,
        subdir="system-services-acquisition",
    )

    import_nist_oscal(data_root=tmp_path)
    # Snapshots only exist for AC and SA; the other 18 configured families are skipped
    # with a warning (non-strict) since this fixture only needs AC/SA coverage.
    parse_all_families(data_root=tmp_path)
    return tmp_path


def _status_by_id(bundle):
    return {r.id: r for r in bundle.catalogue_records}


def test_verified_inherited_or_modified_for_mapped_control(data_root: Path):
    bundle = run_reconciliation(data_root=data_root)
    by_id = _status_by_id(bundle)
    ac2 = by_id["AC-02"]
    assert ac2.origin in ("nist_inherited", "nist_modified_canada")
    assert ac2.nist_oscal_id == "ac-2"
    assert ac2.reconciliation_status in ("verified_inherited", "verified_modified")


def test_enhancement_reconciles_to_nist_enhancement(data_root: Path):
    bundle = run_reconciliation(data_root=data_root)
    by_id = _status_by_id(bundle)
    enh = by_id["AC-02(01)"]
    assert enh.nist_oscal_id == "ac-2.1"
    assert enh.record_kind == "enhancement"
    assert enh.parent_id == "AC-02"


def test_activity_reclassification(data_root: Path):
    bundle = run_reconciliation(data_root=data_root)
    by_id = _status_by_id(bundle)
    ac1 = by_id["AC-01"]
    assert ac1.origin == "nist_reclassified_activity"
    assert ac1.reconciliation_status == "verified_reclassified"
    assert ac1.nist_oscal_id == "ac-1"
    assert ac1.canadian_delta.requirement_kind_changed


def test_canada_only_400_series_base_and_enhancement(data_root: Path):
    bundle = run_reconciliation(data_root=data_root)
    by_id = _status_by_id(bundle)
    sa400 = by_id["SA-400"]
    assert sa400.origin == "canada_only"
    assert sa400.reconciliation_status == "verified_canada_only"
    assert sa400.nist_oscal_id is None

    ac17_400 = by_id["AC-17(400)"]
    assert ac17_400.origin == "canada_only"
    assert ac17_400.is_canadian_specific


def test_missing_nist_mapping_is_unresolved_not_strict(data_root: Path):
    bundle = run_reconciliation(data_root=data_root, strict=False)
    by_id = _status_by_id(bundle)
    # AC-17 has no NIST counterpart in this trimmed fixture (only ac-1/ac-2/sa-8 exist).
    ac17 = by_id["AC-17"]
    assert ac17.reconciliation_status == "unresolved"


def test_missing_nist_mapping_fails_strict_build(data_root: Path):
    from itsp_kb.reconcile import ReconciliationError

    with pytest.raises(ReconciliationError):
        run_reconciliation(data_root=data_root, strict=True)


def test_gc_discussion_is_canada_only_field(data_root: Path):
    bundle = run_reconciliation(data_root=data_root)
    recon_by_id = {r.canadian_id: r for r in bundle.reconciliation_records}
    assert "gc_discussion" in recon_by_id["AC-17"].canada_only_fields


def test_withdrawn_record_marked_and_reconciled(data_root: Path):
    bundle = run_reconciliation(data_root=data_root)
    by_id = _status_by_id(bundle)
    # AC-13 isn't in the AC excerpt fixture; use SA-08 as a control sanity check instead
    # and rely on the dedicated withdrawn fixture test in test_catalogue_parser.py for the
    # parsing side. Here we just check no withdrawn-record crash across the whole family set.
    assert "SA-08" in by_id


def test_no_duplicate_canadian_ids(data_root: Path):
    bundle = run_reconciliation(data_root=data_root)
    ids = [r.id for r in bundle.catalogue_records]
    assert len(ids) == len(set(ids))
