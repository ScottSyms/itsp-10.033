from pathlib import Path

from itsp_kb.models.common import RequirementKind
from itsp_kb.parsers.itsp_10_033_01 import parse_profile_html

FIXTURE = Path(__file__).parent / "fixtures" / "cyber_centre" / "medium_profile_excerpt.html"


def _parse():
    return parse_profile_html(
        FIXTURE.read_bytes(),
        url="https://fixture.example/profile",
        retrieved_at="2026-01-01T00:00:00Z",
        source_sha256="deadbeef",
    )


def test_parses_base_and_enhancement_rows_with_own_ids():
    records = _parse()
    ids = [r.control_id for r in records]
    assert "AC-01" in ids
    assert "AC-02" in ids
    assert "AC-02(01)" in ids
    assert "SA-400" in ids


def test_selected_boolean_normalization():
    records = {r.control_id: r for r in _parse()}
    assert records["AC-01"].selected is True
    assert records["AC-02(02)"].selected is False
    assert records["AC-25"].selected is False
    assert records["AC-25"].selected_raw == "Not allocated to baseline."


def test_requirement_kind_from_table():
    records = {r.control_id: r for r in _parse()}
    assert records["AC-01"].requirement_kind == RequirementKind.ACTIVITY
    assert records["AC-02"].requirement_kind == RequirementKind.CONTROL


def test_placeholder_values_preserved_raw():
    records = {r.control_id: r for r in _parse()}
    assert "frequency" in records["AC-01"].suggested_placeholder_values_raw


def test_no_duplicate_control_ids_in_fixture():
    records = _parse()
    ids = [r.control_id for r in records]
    assert len(ids) == len(set(ids))
