"""`itsp-kb diff <old> <new>` (spec S14.3): compares two full `data/` roots
(each with its own normalized/output subtrees, as produced by `itsp-kb
build --output <path>`), reporting source-version changes, added/removed/
withdrawn records, authoritative content changes, reconciliation-status
changes, and profile-selection changes -- never flagging a formatting-only
normalization difference as an authoritative content change.
"""

from __future__ import annotations

from pathlib import Path

import orjson
from pydantic import BaseModel, Field

from itsp_kb.reconcile import comparison_normalize


class DiffReport(BaseModel):
    source_changes: dict[str, dict] = Field(default_factory=dict)
    added_records: list[str] = Field(default_factory=list)
    removed_records: list[str] = Field(default_factory=list)
    withdrawn_changed: list[str] = Field(default_factory=list)
    reconciliation_status_changed: list[dict] = Field(default_factory=list)
    authoritative_text_changed: list[dict] = Field(default_factory=list)
    related_changed: list[str] = Field(default_factory=list)
    profile_selection_changed: list[dict] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = ["# itsp-kb build diff", ""]

        if self.source_changes:
            lines.append("## Source changes")
            for src, changes in self.source_changes.items():
                lines.append(f"- {src}: {changes}")
            lines.append("")

        if self.added_records:
            lines.append(f"## Added records ({len(self.added_records)})")
            lines.extend(f"- {r}" for r in self.added_records)
            lines.append("")

        if self.removed_records:
            lines.append(f"## Removed records ({len(self.removed_records)})")
            lines.extend(f"- {r}" for r in self.removed_records)
            lines.append("")

        if self.withdrawn_changed:
            lines.append(f"## Withdrawal status changed ({len(self.withdrawn_changed)})")
            lines.extend(f"- {r}" for r in self.withdrawn_changed)
            lines.append("")

        if self.reconciliation_status_changed:
            lines.append(f"## Reconciliation status changed ({len(self.reconciliation_status_changed)})")
            for c in self.reconciliation_status_changed:
                lines.append(f"- {c['id']}: {c['old']} -> {c['new']}")
            lines.append("")

        if self.authoritative_text_changed:
            lines.append(f"## Authoritative text changed ({len(self.authoritative_text_changed)})")
            for c in self.authoritative_text_changed:
                lines.append(f"- {c['id']}: {', '.join(c['fields'])}")
            lines.append("")

        if self.related_changed:
            lines.append(f"## Related-control lists changed ({len(self.related_changed)})")
            lines.extend(f"- {r}" for r in self.related_changed)
            lines.append("")

        if self.profile_selection_changed:
            lines.append(f"## Medium-profile selection changed ({len(self.profile_selection_changed)})")
            for c in self.profile_selection_changed:
                lines.append(f"- {c['id']}: {c['old']} -> {c['new']}")
            lines.append("")

        if len(lines) == 2:
            lines.append("No differences detected.")

        return "\n".join(lines) + "\n"


def _load_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["id"]: row for row in (orjson.loads(line) for line in path.read_bytes().splitlines() if line)}


def _load_manifest(root: Path) -> dict:
    path = root / "output" / "manifests" / "build.json"
    if not path.exists():
        return {}
    return orjson.loads(path.read_bytes())


AUTHORITATIVE_TEXT_FIELDS = ("name", "statement_text", "discussion", "gc_discussion")


def diff_builds(old_root: Path, new_root: Path) -> DiffReport:
    report = DiffReport()

    old_manifest = _load_manifest(old_root)
    new_manifest = _load_manifest(new_root)
    for source_id in set(old_manifest.get("sources", {})) | set(new_manifest.get("sources", {})):
        old_src = old_manifest.get("sources", {}).get(source_id, {})
        new_src = new_manifest.get("sources", {}).get(source_id, {})
        if old_src != new_src:
            report.source_changes[source_id] = {"old": old_src, "new": new_src}

    old_catalogue = _load_jsonl(old_root / "normalized" / "reconciliation" / "catalogue.jsonl")
    new_catalogue = _load_jsonl(new_root / "normalized" / "reconciliation" / "catalogue.jsonl")

    old_ids, new_ids = set(old_catalogue), set(new_catalogue)
    report.added_records = sorted(new_ids - old_ids)
    report.removed_records = sorted(old_ids - new_ids)

    for rid in sorted(old_ids & new_ids):
        old_r, new_r = old_catalogue[rid], new_catalogue[rid]

        if old_r.get("is_withdrawn") != new_r.get("is_withdrawn"):
            report.withdrawn_changed.append(rid)

        if old_r.get("reconciliation_status") != new_r.get("reconciliation_status"):
            report.reconciliation_status_changed.append(
                {"id": rid, "old": old_r.get("reconciliation_status"), "new": new_r.get("reconciliation_status")}
            )

        changed_fields = [
            f
            for f in AUTHORITATIVE_TEXT_FIELDS
            if comparison_normalize(old_r.get(f) or "") != comparison_normalize(new_r.get(f) or "")
        ]
        if changed_fields:
            report.authoritative_text_changed.append({"id": rid, "fields": changed_fields})

        if set(old_r.get("related", [])) != set(new_r.get("related", [])):
            report.related_changed.append(rid)

        old_sel = (old_r.get("profile_memberships") or {}).get("medium")
        new_sel = (new_r.get("profile_memberships") or {}).get("medium")
        if old_sel != new_sel:
            report.profile_selection_changed.append({"id": rid, "old": old_sel, "new": new_sel})

    return report
