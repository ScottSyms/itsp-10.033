import pytest

from itsp_kb.ids import (
    IdMappingError,
    map_child_control,
    oscal_control_id_to_canonical,
    oscal_id_to_canonical_any,
    parse_canadian_id,
    render_canadian_enhancement,
)


def test_base_control_mapping():
    assert oscal_control_id_to_canonical("ac-1") == "AC-01"
    assert oscal_control_id_to_canonical("ac-2") == "AC-02"
    assert oscal_control_id_to_canonical("sa-8") == "SA-08"


def test_base_control_mapping_rejects_enhancement_ids():
    with pytest.raises(IdMappingError):
        oscal_control_id_to_canonical("ac-2.1")


def test_child_control_mapping_uses_verified_parent():
    assert map_child_control("ac-2.1", "AC-02", "ac-2") == "AC-02(01)"
    assert map_child_control("sa-8.33", "SA-08", "sa-8") == "SA-08(33)"


def test_child_control_mapping_rejects_mismatched_parent():
    with pytest.raises(IdMappingError):
        map_child_control("ac-2.1", "AC-03", "ac-3")


def test_oscal_id_to_canonical_any():
    assert oscal_id_to_canonical_any("ac-1") == "AC-01"
    assert oscal_id_to_canonical_any("ac-2.1") == "AC-02(01)"
    assert oscal_id_to_canonical_any("sa-8.33") == "SA-08(33)"


def test_parse_canadian_id_base():
    parsed = parse_canadian_id("AC-02")
    assert parsed.family == "AC"
    assert parsed.base_num == "02"
    assert parsed.enh_num is None
    assert parsed.full_id == "AC-02"
    assert not parsed.is_canadian_specific


def test_parse_canadian_id_enhancement():
    parsed = parse_canadian_id("AC-02(01)")
    assert parsed.full_id == "AC-02(01)"
    assert parsed.base_id == "AC-02"


def test_parse_canadian_id_400_series():
    parsed = parse_canadian_id("SA-400")
    assert parsed.is_canadian_specific
    parsed_enh = parse_canadian_id("AC-17(400)")
    assert parsed_enh.is_canadian_specific


def test_render_canadian_enhancement():
    assert render_canadian_enhancement("SA-08", 33) == "SA-08(33)"
    assert render_canadian_enhancement("AC-17", "400") == "AC-17(400)"


def test_parse_canadian_id_rejects_garbage():
    with pytest.raises(IdMappingError):
        parse_canadian_id("not-an-id")
