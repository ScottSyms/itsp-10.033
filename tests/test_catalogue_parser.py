from pathlib import Path

from itsp_kb.models.common import RequirementKind
from itsp_kb.parsers.itsp_10_033 import parse_family_html

FIXTURES = Path(__file__).parent / "fixtures" / "cyber_centre"


def _parse(name: str, family_id: str, family_name: str):
    html = (FIXTURES / name).read_bytes()
    return parse_family_html(
        html,
        family_id=family_id,
        family_name=family_name,
        url="https://fixture.example/" + name,
        retrieved_at="2026-01-01T00:00:00Z",
        source_sha256="deadbeef",
    )


def _by_id(records, rid):
    return next(r for r in records if r.id == rid)


def test_activity_with_no_enhancements():
    records = _parse("access_control_excerpt.html", "AC", "Access control")
    ac1 = _by_id(records, "AC-01")
    assert ac1.requirement_kind == RequirementKind.ACTIVITY
    assert ac1.enhancements == []
    assert not ac1.is_canadian_specific
    assert not ac1.is_withdrawn
    assert "AC-01" not in ac1.related  # sanity: doesn't include itself
    assert set(ac1.related) == {"IA-01", "PM-09", "PM-24", "PS-08", "SI-02", "SI-12"}
    assert len(ac1.references) >= 1


def test_control_with_enhancements_and_odps():
    records = _parse("access_control_excerpt.html", "AC", "Access control")
    ac2 = _by_id(records, "AC-02")
    assert ac2.requirement_kind == RequirementKind.CONTROL
    assert len(ac2.enhancements) == 13
    assert ac2.odps  # has [Assignment: ...] placeholders
    enh1 = _by_id(ac2.enhancements, "AC-02(01)")
    assert enh1.parent_id == "AC-02"
    assert enh1.enhancement_number == "01"
    assert not enh1.is_canadian_specific
    # The enhancement's discussion continues in an unlabeled sibling <li> after
    # "Discussion:" -- it must land in `discussion`, not bleed into `statement_text`.
    assert "Automated mechanisms can include internal system functions" in enh1.discussion
    assert "Automated mechanisms can include internal system functions" not in enh1.statement_text
    assert "[Assignment: organization-defined automated mechanisms]" in enh1.statement_text


def test_gc_discussion_and_canada_only_enhancement():
    records = _parse("access_control_excerpt.html", "AC", "Access control")
    ac17 = _by_id(records, "AC-17")
    assert ac17.gc_discussion is not None
    assert "Directive on Security Management" in ac17.gc_discussion
    enh400 = _by_id(ac17.enhancements, "AC-17(400)")
    assert enh400.is_canadian_specific
    assert enh400.statement_text


def test_canada_only_base_record():
    records = _parse("sa_excerpt.html", "SA", "System and services acquisition")
    sa400 = _by_id(records, "SA-400")
    assert sa400.is_canadian_specific
    assert sa400.requirement_kind in (RequirementKind.CONTROL, RequirementKind.ACTIVITY)
    assert len(sa400.enhancements) > 0
    assert all(e.parent_id == "SA-400" for e in sa400.enhancements)


def test_no_duplicate_ids_in_fixture():
    records = _parse("access_control_excerpt.html", "AC", "Access control")
    ids = [r.id for r in records] + [e.id for r in records for e in r.enhancements]
    assert len(ids) == len(set(ids))


def test_withdrawn_record():
    records = _parse("ac_edge_cases.html", "AC", "Access control")
    ac13 = _by_id(records, "AC-13")
    assert ac13.is_withdrawn
    assert "AC-02" in ac13.withdrawal_note and "AU-06" in ac13.withdrawal_note
    assert ac13.statement_text == ""
    assert ac13.enhancements == []


def test_ambiguous_activity_control_label_does_not_guess():
    records = _parse("ac_edge_cases.html", "AC", "Access control")
    ac12 = _by_id(records, "AC-12")
    assert not ac12.is_withdrawn
    # The source itself doesn't commit to one kind here; we must not guess.
    assert ac12.requirement_kind == RequirementKind.UNKNOWN
    # But the statement text is still fully captured despite the unusual
    # <p><strong>Activity/Control:</strong> ...</p> (no <h3>, no <ol>) rendering.
    assert "Automatically terminate a user session" in ac12.statement_text
    assert len(ac12.enhancements) == 3


def test_paragraph_label_classification_with_separate_statement_list():
    records = _parse("cm_edge_cases.html", "CM", "Configuration management")
    cm06 = _by_id(records, "CM-06")
    # <p><strong>Control:</strong></p> (label only) followed by a sibling <ol>
    # (the statement) -- not an <h3>Control</h3> like the common case.
    assert cm06.requirement_kind == RequirementKind.CONTROL
    assert len(cm06.statements) == 4
    assert "Establish and document configuration settings" in cm06.statement_text
