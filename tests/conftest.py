"""Shared fixtures: a small but real, end-to-end reconciled data root built from
the trimmed NIST/Canadian fixtures (AC + SA families only)."""

from pathlib import Path

import pytest

from itsp_kb.parsers.itsp_10_033 import parse_all_families
from itsp_kb.parsers.nist_oscal import import_nist_oscal
from itsp_kb.provenance import write_snapshot
from itsp_kb.reconcile import run_reconciliation

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def reconciled_data_root(tmp_path: Path) -> Path:
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
    parse_all_families(data_root=tmp_path)
    run_reconciliation(data_root=tmp_path, strict=False)
    return tmp_path
