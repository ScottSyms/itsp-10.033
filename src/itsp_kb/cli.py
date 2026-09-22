"""`itsp-kb` command-line interface (spec S15)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from itsp_kb.config import DEFAULT_DATA_ROOT, load_registry

app = typer.Typer(name="itsp-kb", no_args_is_help=True, add_completion=False)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("itsp_kb")


OutputOpt = Annotated[Path | None, typer.Option("--output", help="Override the data/ output root.")]
StrictOpt = Annotated[bool, typer.Option("--strict", help="Fail the build on any unresolved/invalid record.")]
JsonOpt = Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON instead of text.")]
PublicationOpt = Annotated[
    str | None, typer.Option("--publication", help="Limit to one publication, e.g. 'ITSP.10.033'.")
]
FamilyOpt = Annotated[str | None, typer.Option("--family", help="Limit to one family id, e.g. 'AC'.")]


def _data_root(output: Path | None) -> Path:
    return output or DEFAULT_DATA_ROOT


@app.command()
def fetch(
    offline: Annotated[bool, typer.Option("--offline", help="Rebuild from saved snapshots only.")] = False,
    force_fetch: Annotated[bool, typer.Option("--force-fetch", help="Bypass conditional GET caching.")] = False,
    nist_ref: Annotated[str | None, typer.Option("--nist-ref", help="NIST OSCAL git ref (branch/tag/commit).")] = None,
    publication: PublicationOpt = None,
    output: OutputOpt = None,
    strict: StrictOpt = False,
) -> None:
    """Fetch all configured sources, including NIST OSCAL and Cyber Centre pages."""
    from itsp_kb.fetch import fetch_all

    registry = load_registry()
    results = fetch_all(
        registry,
        offline=offline,
        force=force_fetch,
        nist_ref=nist_ref,
        publication=publication,
        data_root=_data_root(output),
        strict=strict,
    )
    for source_id, fetch_results in results.items():
        logger.info("fetched %s: %d snapshot(s)", source_id, len(fetch_results))


@app.command(name="import-nist")
def import_nist(
    output: OutputOpt = None,
    strict: StrictOpt = False,
    allow_newer_oscal: Annotated[bool, typer.Option("--allow-newer-oscal")] = False,
) -> None:
    """Import/normalize the NIST OSCAL baseline."""
    from itsp_kb.parsers.nist_oscal import import_nist_oscal

    data_root = _data_root(output)
    result = import_nist_oscal(data_root=data_root, strict=strict, allow_newer_oscal=allow_newer_oscal)
    logger.info(
        "imported NIST OSCAL: %d groups, %d controls, %d unmapped structures",
        result.metadata.group_count,
        result.metadata.control_count,
        result.metadata.unmapped_structure_count,
    )


@app.command(name="parse-canada")
def parse_canada(
    family: FamilyOpt = None,
    output: OutputOpt = None,
    strict: StrictOpt = False,
) -> None:
    """Parse Canadian source snapshots."""
    from itsp_kb.parsers.itsp_10_033 import parse_all_families

    data_root = _data_root(output)
    result = parse_all_families(data_root=data_root, family_filter=family, strict=strict)
    logger.info("parsed Canadian source: %d records across %d families", len(result.records), len(result.families))


@app.command()
def reconcile(
    family: FamilyOpt = None,
    output: OutputOpt = None,
    strict: StrictOpt = False,
) -> None:
    """Reconcile NIST baseline against ITSP.10.033."""
    from itsp_kb.reconcile import run_reconciliation

    data_root = _data_root(output)
    result = run_reconciliation(data_root=data_root, family_filter=family, strict=strict)
    logger.info(
        "reconciled: %d verified_inherited, %d verified_modified, %d verified_reclassified, "
        "%d verified_canada_only, %d unresolved",
        result.counts.get("verified_inherited", 0),
        result.counts.get("verified_modified", 0),
        result.counts.get("verified_reclassified", 0),
        result.counts.get("verified_canada_only", 0),
        result.counts.get("unresolved", 0),
    )


@app.command(name="parse-profile")
def parse_profile(
    profile_id: Annotated[str, typer.Argument(help="Profile id, e.g. 'medium'.")] = "medium",
    output: OutputOpt = None,
    strict: StrictOpt = False,
) -> None:
    """Parse/join the Medium profile."""
    from itsp_kb.parsers.itsp_10_033_01 import parse_and_join_profile

    data_root = _data_root(output)
    result = parse_and_join_profile(profile_id=profile_id, data_root=data_root, strict=strict)
    logger.info("parsed profile '%s': %d rows", profile_id, len(result.records))


@app.command()
def validate(
    output: OutputOpt = None,
    strict: StrictOpt = False,
    json_out: JsonOpt = False,
) -> None:
    """Validate all layers."""
    from itsp_kb.validate import validate_all

    data_root = _data_root(output)
    report = validate_all(data_root=data_root, strict=strict)
    if json_out:
        typer.echo(json.dumps(report.model_dump(), indent=2))
    else:
        logger.info(
            "validation passed=%s, errors=%d, warnings=%d",
            report.passed,
            len(report.errors),
            len(report.warnings),
        )
    if strict and not report.passed:
        raise typer.Exit(code=1)


@app.command()
def export(output: OutputOpt = None, strict: StrictOpt = False) -> None:
    """Export JSONL/CSV/graph/derived OSCAL."""
    from itsp_kb.exporters.run import run_all_exports

    data_root = _data_root(output)
    run_all_exports(data_root=data_root, strict=strict)
    logger.info("export complete")


@app.command()
def build(
    output: OutputOpt = None,
    strict: StrictOpt = False,
    offline: Annotated[bool, typer.Option("--offline")] = False,
    force_fetch: Annotated[bool, typer.Option("--force-fetch")] = False,
    nist_ref: Annotated[str | None, typer.Option("--nist-ref")] = None,
    allow_newer_oscal: Annotated[bool, typer.Option("--allow-newer-oscal")] = False,
) -> None:
    """Complete deterministic pipeline: fetch -> import-nist -> parse-canada -> reconcile ->
    parse-profile -> validate -> export -> manifest."""
    from itsp_kb.build import run_build

    data_root = _data_root(output)
    run_build(
        data_root=data_root,
        strict=strict,
        offline=offline,
        force_fetch=force_fetch,
        nist_ref=nist_ref,
        allow_newer_oscal=allow_newer_oscal,
    )


@app.command()
def diff(
    old: Annotated[Path, typer.Argument(help="Path to the old build's data/output directory.")],
    new: Annotated[Path, typer.Argument(help="Path to the new build's data/output directory.")],
    json_out: JsonOpt = False,
) -> None:
    """Compare builds."""
    from itsp_kb.diff import diff_builds

    report = diff_builds(old, new)
    if json_out:
        typer.echo(json.dumps(report.model_dump(), indent=2))
    else:
        typer.echo(report.to_markdown())


@app.command()
def show(
    record_id: Annotated[str, typer.Argument(help="Canadian canonical id, e.g. 'AC-02'.")],
    upstream: Annotated[bool, typer.Option("--upstream", help="Show the corresponding NIST upstream object.")] = False,
    output: OutputOpt = None,
    json_out: JsonOpt = False,
) -> None:
    """Inspect one final Canadian record plus lineage, or its NIST upstream object."""
    from itsp_kb.inspect_record import show_record

    data_root = _data_root(output)
    show_record(record_id, upstream=upstream, data_root=data_root, as_json=json_out)


@app.command(name="render-embeddings")
def render_embeddings(
    view: Annotated[
        str,
        typer.Option("--view", help="requirement_only|requirement_plus_discussion|full|canada_delta"),
    ] = "requirement_only",
    output: OutputOpt = None,
) -> None:
    """Produce embedding-ready representations."""
    from itsp_kb.exporters.embeddings import render_embedding_records

    data_root = _data_root(output)
    records = render_embedding_records(view=view, data_root=data_root)
    logger.info("rendered %d embedding records (view=%s)", len(records), view)


@app.command(name="import-profile-spreadsheet")
def import_profile_spreadsheet(
    path: Annotated[Path, typer.Argument(help="Path to the official Medium-profile spreadsheet (.xlsx).")],
    output: OutputOpt = None,
    strict: StrictOpt = False,
) -> None:
    """Optional: import the official Medium-profile spreadsheet and compare it to the HTML-derived profile."""
    from itsp_kb.parsers.profile_spreadsheet import import_spreadsheet

    data_root = _data_root(output)
    import_spreadsheet(path, data_root=data_root, strict=strict)


if __name__ == "__main__":
    app()
