"""Full-pipeline (offline, fixture-driven) build test plus a diff round-trip,
covering spec S25 Phase 6's "two builds from identical snapshots produce no
semantic diff" acceptance criterion."""

from pathlib import Path

import orjson

from itsp_kb.build import run_build
from itsp_kb.diff import diff_builds
from itsp_kb.provenance import write_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def _seed_raw(data_root: Path) -> None:
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
        data_root=data_root,
    )
    write_snapshot(
        source_id="itsp_10_033",
        publication="ITSP.10.033",
        url="https://fixture.example/access-control",
        content=(FIXTURES / "cyber_centre" / "access_control_excerpt.html").read_bytes(),
        content_filename="source.html",
        http_status=200,
        content_type="text/html",
        data_root=data_root,
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
        data_root=data_root,
        subdir="system-services-acquisition",
    )
    write_snapshot(
        source_id="itsp_10_033_01",
        publication="ITSP.10.033-01",
        url="https://fixture.example/profile",
        content=(FIXTURES / "cyber_centre" / "medium_profile_excerpt.html").read_bytes(),
        content_filename="profile.html",
        http_status=200,
        content_type="text/html",
        data_root=data_root,
    )


def test_build_is_idempotent_across_identical_snapshots(tmp_path: Path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _seed_raw(root_a)
    _seed_raw(root_b)

    run_build(data_root=root_a, offline=True, strict=False)
    run_build(data_root=root_b, offline=True, strict=False)

    diff = diff_builds(root_a, root_b)
    assert diff.added_records == []
    assert diff.removed_records == []
    assert diff.reconciliation_status_changed == []
    assert diff.authoritative_text_changed == []
    assert diff.related_changed == []
    assert diff.profile_selection_changed == []


def test_build_manifest_counts_match_catalogue(tmp_path: Path):
    _seed_raw(tmp_path)
    run_build(data_root=tmp_path, offline=True, strict=False)

    manifest = orjson.loads((tmp_path / "output" / "manifests" / "build.json").read_bytes())
    catalogue = [
        orjson.loads(line)
        for line in (tmp_path / "normalized" / "reconciliation" / "catalogue.jsonl").read_bytes().splitlines()
        if line
    ]
    counts = manifest["record_counts"]
    assert counts["canadian_base_records"] + counts["canadian_enhancements"] == len(catalogue)
    assert sum(
        counts[k]
        for k in (
            "verified_inherited",
            "verified_modified",
            "verified_reclassified",
            "verified_canada_only",
            "unresolved",
        )
    ) == len(catalogue)


def test_diff_detects_a_real_change(tmp_path: Path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _seed_raw(root_a)
    _seed_raw(root_b)
    run_build(data_root=root_a, offline=True, strict=False)
    run_build(data_root=root_b, offline=True, strict=False)

    path = root_b / "normalized" / "reconciliation" / "catalogue.jsonl"
    rows = [orjson.loads(line) for line in path.read_bytes().splitlines() if line]
    for r in rows:
        if r["id"] == "AC-02":
            r["statement_text"] = r["statement_text"] + " A materially different sentence was added here."
    with path.open("wb") as f:
        for r in rows:
            f.write(orjson.dumps(r))
            f.write(b"\n")

    diff = diff_builds(root_a, root_b)
    changed_ids = {c["id"] for c in diff.authoritative_text_changed}
    assert "AC-02" in changed_ids
