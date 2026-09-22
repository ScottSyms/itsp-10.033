from pathlib import Path

from itsp_kb.exporters.embeddings import VALID_VIEWS, render_embedding_records
from itsp_kb.exporters.jsonl import export_catalogue_jsonl_csv, export_upstream_nist
from itsp_kb.exporters.oscal import build_oscal_catalog


def test_catalogue_jsonl_csv_export(reconciled_data_root: Path):
    export_catalogue_jsonl_csv(data_root=reconciled_data_root)
    out_dir = reconciled_data_root / "output" / "catalogue"
    assert (out_dir / "controls.jsonl").exists()
    assert (out_dir / "enhancements.jsonl").exists()
    assert (out_dir / "all_records.jsonl").exists()
    assert (out_dir / "families.json").exists()
    assert (out_dir / "controls.csv").exists()

    import orjson

    all_records = [orjson.loads(line) for line in (out_dir / "all_records.jsonl").read_bytes().splitlines() if line]
    controls = [orjson.loads(line) for line in (out_dir / "controls.jsonl").read_bytes().splitlines() if line]
    enhancements = [orjson.loads(line) for line in (out_dir / "enhancements.jsonl").read_bytes().splitlines() if line]
    assert len(controls) + len(enhancements) == len(all_records)
    assert any(r["id"] == "AC-02" for r in controls)
    assert any(r["id"] == "AC-02(01)" for r in enhancements)


def test_upstream_nist_export_copies_normalized_data(reconciled_data_root: Path):
    export_upstream_nist(data_root=reconciled_data_root)
    out_dir = reconciled_data_root / "output" / "upstream" / "nist"
    for name in ("families.json", "records.jsonl", "relationships.jsonl", "metadata.json"):
        assert (out_dir / name).exists()


def test_all_embedding_views_render(reconciled_data_root: Path):
    for view in VALID_VIEWS:
        records = render_embedding_records(view=view, data_root=reconciled_data_root)
        assert records
        ac2 = next(r for r in records if r.record_id == "AC-02")
        assert ac2.view == view
        assert "AC-02" in ac2.text


def test_embedding_rendering_is_deterministic(reconciled_data_root: Path):
    first = render_embedding_records(view="full", data_root=reconciled_data_root)
    second = render_embedding_records(view="full", data_root=reconciled_data_root)
    assert [r.text for r in first] == [r.text for r in second]


def test_canada_delta_view_omits_unchanged_boilerplate_for_inherited(reconciled_data_root: Path):
    records = render_embedding_records(view="canada_delta", data_root=reconciled_data_root)
    # SA-08's base is trimmed to look inherited in this fixture-derived data root;
    # canada_delta should stay short (no full requirement dump) when nothing changed.
    inherited = [r for r in records if r.reconciliation_status == "verified_inherited"]
    if inherited:
        assert len(inherited[0].text) < 400


def test_oscal_catalog_marks_itself_unofficial_and_preserves_canadian_ids(reconciled_data_root: Path):
    doc = build_oscal_catalog(data_root=reconciled_data_root)
    assert "unofficial" in doc["catalog"]["metadata"]["remarks"].lower()
    ac_group = next(g for g in doc["catalog"]["groups"] if g["id"] == "ac")
    ac2 = next(c for c in ac_group["controls"] if c["id"] == "ac-2")
    canadian_id_prop = next(p for p in ac2["props"] if p["name"] == "canadian-id")
    assert canadian_id_prop["value"] == "AC-02"


def test_oscal_catalog_synthesizes_id_for_canada_only_record(reconciled_data_root: Path):
    doc = build_oscal_catalog(data_root=reconciled_data_root)
    sa_group = next(g for g in doc["catalog"]["groups"] if g["id"] == "sa")
    sa400 = next(c for c in sa_group["controls"] if any(p["value"] == "SA-400" for p in c["props"]))
    assert sa400["id"] == "sa-400"
