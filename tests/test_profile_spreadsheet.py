from pathlib import Path

import pytest
from openpyxl import Workbook

from itsp_kb.parsers.profile_spreadsheet import SpreadsheetImportError, import_spreadsheet, parse_profile_spreadsheet


def _write_workbook(path: Path, rows: list[tuple]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "AC"
    ws.append(
        [
            "Family",
            "ID",
            "Name",
            "Description",
            "Control/Activity",
            "Suggested for this profile",
            "Suggested placeholder values",
            "Profile-specific notes",
        ]
    )
    for row in rows:
        ws.append(list(row))
    wb.save(path)


def test_parses_spreadsheet_rows(tmp_path: Path):
    path = tmp_path / "profile.xlsx"
    _write_workbook(
        path,
        [("AC", "01", "Access control policy and procedures", "...", "Activity", "Selected", "NA", "NA")],
    )
    records = parse_profile_spreadsheet(path)
    assert len(records) == 1
    assert records[0].control_id == "AC-01"
    assert records[0].selected is True
    assert records[0].source.source_type == "official_spreadsheet"


def test_import_reports_differences_against_html_profile(tmp_path: Path):
    path = tmp_path / "profile.xlsx"
    _write_workbook(
        path,
        [
            ("AC", "01", "Access control policy and procedures", "...", "Activity", "Not selected", "NA", "NA"),
            ("AC", "99", "Only in spreadsheet", "...", "Control", "Selected", "NA", "NA"),
        ],
    )

    import orjson

    profiles_dir = tmp_path / "output" / "profiles"
    profiles_dir.mkdir(parents=True)
    with (profiles_dir / "medium.jsonl").open("wb") as f:
        f.write(
            orjson.dumps(
                {
                    "control_id": "AC-01",
                    "family_id": "AC",
                    "selected": True,
                    "selected_raw": "Selected",
                }
            )
        )
        f.write(b"\n")

    result = import_spreadsheet(path, data_root=tmp_path, strict=False)
    assert any("AC-01" in d and "differs" in d for d in result.differences)
    assert any("AC-99" in d for d in result.differences)


def test_import_fails_strict_on_differences(tmp_path: Path):
    path = tmp_path / "profile.xlsx"
    _write_workbook(path, [("AC", "01", "X", "...", "Activity", "Not selected", "NA", "NA")])

    import orjson

    profiles_dir = tmp_path / "output" / "profiles"
    profiles_dir.mkdir(parents=True)
    with (profiles_dir / "medium.jsonl").open("wb") as f:
        f.write(orjson.dumps({"control_id": "AC-01", "selected": True, "selected_raw": "Selected"}))
        f.write(b"\n")

    with pytest.raises(SpreadsheetImportError):
        import_spreadsheet(path, data_root=tmp_path, strict=True)
