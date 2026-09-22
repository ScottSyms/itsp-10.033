from pathlib import Path

from itsp_kb.validate import validate_all


def test_valid_reconciled_data_root_passes(reconciled_data_root: Path):
    report = validate_all(data_root=reconciled_data_root, strict=False)
    assert report.passed, report.errors


def test_duplicate_id_is_detected(reconciled_data_root: Path):
    import orjson

    path = reconciled_data_root / "normalized" / "reconciliation" / "catalogue.jsonl"
    lines = [line for line in path.read_bytes().splitlines() if line]
    rows = [orjson.loads(line) for line in lines]
    dup = dict(rows[0])
    rows.append(dup)
    with path.open("wb") as f:
        for r in rows:
            f.write(orjson.dumps(r))
            f.write(b"\n")

    report = validate_all(data_root=reconciled_data_root, strict=False)
    assert not report.passed
    assert any("Duplicate Canadian canonical ids" in e for e in report.errors)


def test_unbalanced_brackets_detected(reconciled_data_root: Path):
    import orjson

    path = reconciled_data_root / "normalized" / "reconciliation" / "catalogue.jsonl"
    rows = [orjson.loads(line) for line in path.read_bytes().splitlines() if line]
    rows[0]["statement_text"] = rows[0]["statement_text"] + " [unclosed"
    with path.open("wb") as f:
        for r in rows:
            f.write(orjson.dumps(r))
            f.write(b"\n")

    report = validate_all(data_root=reconciled_data_root, strict=False)
    assert not report.passed
    assert any("unbalanced ODP bracket" in e for e in report.errors)


def test_missing_nist_dataset_warns_but_does_not_crash(tmp_path: Path):
    report = validate_all(data_root=tmp_path, strict=False)
    assert report.warnings
