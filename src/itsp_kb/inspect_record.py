"""`itsp-kb show <id> [--upstream]` (spec S15): inspect one final Canadian
record plus its lineage, or the corresponding NIST upstream object."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from itsp_kb.config import DEFAULT_DATA_ROOT
from itsp_kb.parsers.nist_oscal import load_normalized_nist
from itsp_kb.reconcile import load_catalogue


def show_record(record_id: str, *, upstream: bool, data_root: Path = DEFAULT_DATA_ROOT, as_json: bool = False) -> None:
    catalogue = load_catalogue(data_root=data_root)
    record = next((r for r in catalogue if r.id == record_id), None)
    if record is None:
        typer.echo(f"No Canadian catalogue record found for '{record_id}'.", err=True)
        raise typer.Exit(code=1)

    if upstream:
        if record.nist_oscal_id is None:
            typer.echo(f"'{record_id}' has no NIST upstream mapping (origin={record.origin.value}).", err=True)
            raise typer.Exit(code=1)
        nist_result = load_normalized_nist(data_root=data_root)
        upstream_record = next((r for r in nist_result.records if r.upstream_id == record.nist_oscal_id), None)
        if upstream_record is None:
            typer.echo(f"NIST upstream id '{record.nist_oscal_id}' not found in normalized dataset.", err=True)
            raise typer.Exit(code=1)
        payload = upstream_record.model_dump(mode="json")
    else:
        payload = record.model_dump(mode="json")

    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return

    _print_human(record_id, payload, upstream=upstream)


def _print_human(record_id: str, payload: dict, *, upstream: bool) -> None:
    if upstream:
        typer.echo(f"NIST upstream object for '{record_id}':")
        typer.echo(f"  upstream_id:       {payload['upstream_id']}")
        typer.echo(f"  canonical_id:      {payload['canonical_candidate_id']}")
        typer.echo(f"  family_id:         {payload['family_id']}")
        typer.echo(f"  title:             {payload['title']}")
        typer.echo(f"  parent_upstream_id:{payload.get('parent_upstream_id')}")
        typer.echo(f"  child_control_ids: {payload.get('child_control_ids')}")
        typer.echo(f"  param count:       {len(payload.get('params', []))}")
        typer.echo(f"  part count:        {len(payload.get('parts', []))}")
        src = payload.get("source", {})
        typer.echo(
            f"  source:            {src.get('publication')} {src.get('metadata_version')} "
            f"(oscal {src.get('oscal_version')})"
        )
        typer.echo(f"  git_commit:        {src.get('git_commit')}")
        return

    typer.echo(f"{payload['id']}  {payload['name']}")
    typer.echo(f"  family:                {payload['family_id']} ({payload['family_name']})")
    typer.echo(f"  record_kind:           {payload['record_kind']}")
    typer.echo(f"  requirement_kind:      {payload['requirement_kind']}")
    typer.echo(f"  origin:                {payload['origin']}")
    typer.echo(f"  reconciliation_status: {payload['reconciliation_status']}")
    typer.echo(f"  nist_oscal_id:         {payload.get('nist_oscal_id')}")
    typer.echo(f"  is_canadian_specific:  {payload['is_canadian_specific']}")
    typer.echo(f"  is_withdrawn:          {payload['is_withdrawn']}")
    if payload.get("withdrawal_note"):
        typer.echo(f"  withdrawal_note:       {payload['withdrawal_note']}")
    typer.echo(f"  canadian_delta.fields: {payload['canadian_delta']['fields']}")
    typer.echo(f"  related:               {payload['related']}")
    typer.echo(f"  enhancement_ids:       {payload['enhancement_ids']}")
    typer.echo(f"  profile_memberships:   {payload['profile_memberships']}")
    typer.echo("")
    typer.echo("  statement_text:")
    for line in (payload["statement_text"] or "(none)").splitlines():
        typer.echo(f"    {line}")
    if payload.get("discussion"):
        typer.echo("")
        typer.echo("  discussion:")
        typer.echo(f"    {payload['discussion'][:500]}")
    if payload.get("gc_discussion"):
        typer.echo("")
        typer.echo("  gc_discussion:")
        typer.echo(f"    {payload['gc_discussion'][:500]}")
