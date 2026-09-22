"""Optional official Medium-profile spreadsheet importer (spec S9).

Not a v1 prerequisite -- the Cyber Centre states a spreadsheet version of the
profile "can be requested"; this importer uses the same canonical
`ProfileRecord` model as the HTML parser and reports (never silently
resolves) any divergence between the two sources.

Expected columns (same as the HTML table, spec S8.1): Family, ID, Name,
Description, Control/Activity, Suggested for this profile, Suggested
placeholder values, Profile-specific notes -- in a single sheet, or spread
across one sheet per family (all sheets are read and combined).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import orjson
from openpyxl import load_workbook

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.models.common import RequirementKind
from itsp_kb.models.profile import ProfileRecord, ProfileSource
from itsp_kb.provenance import sha256_hex, utcnow_iso

logger = logging.getLogger(__name__)

_EXPECTED_HEADER = [
    "family",
    "id",
    "name",
    "description",
    "control/activity",
    "suggested for this profile",
    "suggested placeholder values",
    "profile-specific notes",
]

_KIND_MAP = {"control": RequirementKind.CONTROL, "activity": RequirementKind.ACTIVITY}


class SpreadsheetImportError(ValueError):
    pass


@dataclass
class SpreadsheetImportResult:
    records: list[ProfileRecord] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)


def _parse_sheet(sheet, *, source_sha256: str, path_name: str) -> list[ProfileRecord]:
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    if header[:8] != _EXPECTED_HEADER:
        logger.warning("Sheet '%s' header does not match the expected 8 profile columns; skipping.", sheet.title)
        return []

    records: list[ProfileRecord] = []
    for row in rows[1:]:
        if row is None or all(c is None for c in row):
            continue
        family, id_col, name, _description, kind_raw, selected_raw, placeholder, notes = (row + (None,) * 8)[:8]
        if not family or not id_col:
            continue
        control_id = f"{str(family).strip()}-{str(id_col).strip()}"
        requirement_kind = _KIND_MAP.get(str(kind_raw or "").strip().lower(), RequirementKind.UNKNOWN)
        selected_raw_str = str(selected_raw or "").strip()
        records.append(
            ProfileRecord(
                control_id=control_id,
                family_id=str(family).strip(),
                name=str(name or "").strip(),
                requirement_kind=requirement_kind,
                selected=selected_raw_str == "Selected",
                selected_raw=selected_raw_str,
                suggested_placeholder_values_raw=str(placeholder).strip() if placeholder else None,
                profile_specific_notes=str(notes).strip() if notes else None,
                source=ProfileSource(
                    table=sheet.title,
                    url=f"file://{path_name}",
                    retrieved_at=utcnow_iso(),
                    source_sha256=source_sha256,
                    source_type="official_spreadsheet",
                ),
            )
        )
    return records


def parse_profile_spreadsheet(path: Path) -> list[ProfileRecord]:
    source_sha256 = sha256_hex(path.read_bytes())
    wb = load_workbook(path, read_only=True, data_only=True)
    records: list[ProfileRecord] = []
    for sheet in wb.worksheets:
        records.extend(_parse_sheet(sheet, source_sha256=source_sha256, path_name=path.name))
    if not records:
        raise SpreadsheetImportError(f"No profile rows recognized in '{path}'.")
    return records


def import_spreadsheet(
    path: Path, *, profile_id: str = "medium", data_root: Path = DEFAULT_DATA_ROOT, strict: bool = False
) -> SpreadsheetImportResult:
    spreadsheet_records = parse_profile_spreadsheet(path)
    by_id_spreadsheet = {r.control_id: r for r in spreadsheet_records}

    html_path = data_root / "output" / "profiles" / f"{profile_id}.jsonl"
    differences: list[str] = []
    if html_path.exists():
        html_rows = {
            row["control_id"]: row
            for row in (orjson.loads(line) for line in html_path.read_bytes().splitlines() if line)
        }
        for control_id, sheet_row in by_id_spreadsheet.items():
            html_row = html_rows.get(control_id)
            if html_row is None:
                differences.append(f"'{control_id}' is in the spreadsheet but not in the HTML-derived profile.")
                continue
            if sheet_row.selected != html_row["selected"]:
                differences.append(
                    f"'{control_id}' selection differs: spreadsheet={sheet_row.selected_raw!r} "
                    f"html={html_row['selected_raw']!r}"
                )
        for control_id in set(html_rows) - set(by_id_spreadsheet):
            differences.append(f"'{control_id}' is in the HTML-derived profile but not in the spreadsheet.")
    else:
        differences.append("No HTML-derived profile found to compare against; only the spreadsheet was imported.")

    if differences and strict:
        raise SpreadsheetImportError(
            f"{len(differences)} difference(s) between the spreadsheet and HTML-derived profile: {differences[:5]}"
        )
    for d in differences:
        logger.warning(d)

    return SpreadsheetImportResult(records=spreadsheet_records, differences=differences)
