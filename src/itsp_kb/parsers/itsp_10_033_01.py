"""ITSP.10.033-01 Medium-impact profile parser and catalogue join (spec S8).

The live page renders one real HTML `<table>` per family, identified by a
`<caption id="tab4.N">` (a direct child of the `<table>`, not the table
itself). Each row -- base control *and* each enhancement individually, e.g.
id "02(01)" -- is its own row with columns:
Family, ID, Name, Description, Control/Activity, Suggested for this profile,
Suggested placeholder values, Profile-specific notes. Because enhancements
already get their own row, a profile record's `control_id` (family + id
column, e.g. "AC-02(01)") already matches the final Canadian canonical id
directly -- no separate enhancement-selection parsing is needed.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import orjson
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel

from itsp_kb.config import DEFAULT_DATA_ROOT, load_registry
from itsp_kb.models.common import RequirementKind
from itsp_kb.models.profile import ProfileRecord, ProfileSource
from itsp_kb.parsers.html_utils import get_text_ws
from itsp_kb.provenance import latest_raw_snapshot_dir, read_fetch_meta, sha256_hex
from itsp_kb.reconcile import load_catalogue

logger = logging.getLogger(__name__)


class ProfileJoinError(ValueError):
    def __init__(self, message: str, *, control_id: str | None = None):
        super().__init__(message)
        self.control_id = control_id


_KIND_MAP = {"control": RequirementKind.CONTROL, "activity": RequirementKind.ACTIVITY}


def _parse_table(
    table: Tag, *, caption_text: str, url: str, retrieved_at: str, source_sha256: str
) -> list[ProfileRecord]:
    tbody = table.find("tbody")
    rows = tbody.find_all("tr", recursive=False) if tbody else table.find_all("tr")[1:]

    records: list[ProfileRecord] = []
    for tr in rows:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            logger.warning("Profile row with %d columns (expected 8) in %s; skipping", len(tds), caption_text)
            continue
        family = get_text_ws(tds[0])
        id_col = get_text_ws(tds[1])
        if not family or not id_col:
            continue
        control_id = f"{family}-{id_col}"
        name = get_text_ws(tds[2])
        description_raw = get_text_ws(tds[3])
        kind_raw = get_text_ws(tds[4]).lower()
        requirement_kind = _KIND_MAP.get(kind_raw, RequirementKind.UNKNOWN)
        selected_raw = get_text_ws(tds[5])
        selected = selected_raw == "Selected"
        placeholder_raw = get_text_ws(tds[6]) or None
        notes_raw = get_text_ws(tds[7]) or None

        records.append(
            ProfileRecord(
                control_id=control_id,
                family_id=family,
                name=name,
                requirement_kind=requirement_kind,
                selected=selected,
                selected_raw=selected_raw,
                suggested_placeholder_values_raw=placeholder_raw,
                profile_specific_notes=notes_raw,
                description_raw=description_raw,
                source=ProfileSource(
                    table=caption_text,
                    url=url,
                    retrieved_at=retrieved_at,
                    source_sha256=source_sha256,
                    source_type="html",
                ),
            )
        )
    return records


def parse_profile_html(html: bytes, *, url: str, retrieved_at: str, source_sha256: str) -> list[ProfileRecord]:
    soup = BeautifulSoup(html, "lxml")
    records: list[ProfileRecord] = []
    captions = [c for c in soup.find_all("caption") if str(c.get("id") or "").startswith("tab4.")]
    if not captions:
        raise ProfileJoinError("No 'tab4.N' profile tables found on the Medium-profile page")

    for caption in sorted(captions, key=lambda c: int(str(c["id"]).split(".", 1)[1])):
        table = caption.find_parent("table")
        if table is None:
            logger.warning("Caption '%s' has no parent <table>; skipping", caption.get("id"))
            continue
        caption_text = get_text_ws(caption)
        records.extend(
            _parse_table(
                table, caption_text=caption_text, url=url, retrieved_at=retrieved_at, source_sha256=source_sha256
            )
        )
    return records


@dataclass
class ProfileParseResult:
    records: list[ProfileRecord] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


def parse_and_join_profile(
    *,
    profile_id: str = "medium",
    data_root: Path = DEFAULT_DATA_ROOT,
    strict: bool = False,
) -> ProfileParseResult:
    registry = load_registry()
    source = registry["itsp_10_033_01"]
    snapshot_dir = latest_raw_snapshot_dir("itsp_10_033_01", data_root=data_root)
    if snapshot_dir is None:
        raise FileNotFoundError("No ITSP.10.033-01 snapshot found; run `itsp-kb fetch` first.")

    fetch_meta = read_fetch_meta(snapshot_dir)
    html_bytes = (snapshot_dir / "profile.html").read_bytes()
    actual_hash = sha256_hex(html_bytes)
    records = parse_profile_html(
        html_bytes, url=fetch_meta["url"], retrieved_at=fetch_meta["retrieved_at"], source_sha256=actual_hash
    )
    for r in records:
        r.profile_id = profile_id
        r.profile_publication = source.publication

    # Duplicate rows that disagree on selection state are a hard failure (spec S8.3);
    # duplicates that agree are just redundant and are de-duplicated.
    seen: dict[str, ProfileRecord] = {}
    deduped: list[ProfileRecord] = []
    for r in records:
        prior = seen.get(r.control_id)
        if prior is not None:
            if prior.selected != r.selected:
                msg = f"Duplicate profile row for '{r.control_id}' disagrees on selection state"
                if strict:
                    raise ProfileJoinError(msg, control_id=r.control_id)
                logger.warning(msg)
            continue
        seen[r.control_id] = r
        deduped.append(r)
    records = deduped

    catalogue = load_catalogue(data_root=data_root)
    catalogue_by_id = {c.id: c for c in catalogue}

    unresolved: list[str] = []
    for r in records:
        target = catalogue_by_id.get(r.control_id)
        if target is None:
            msg = f"Profile row '{r.control_id}' does not resolve to any Canadian catalogue record"
            if r.selected and strict:
                raise ProfileJoinError(msg, control_id=r.control_id)
            logger.warning(msg)
            unresolved.append(r.control_id)
            continue
        if target.reconciliation_status.value == "unresolved" and strict:
            raise ProfileJoinError(
                f"Profile row '{r.control_id}' targets a record with reconciliation_status=unresolved",
                control_id=r.control_id,
            )
        target.profile_memberships[profile_id] = r.selected

    _write_output(records, catalogue, profile_id=profile_id, data_root=data_root)
    return ProfileParseResult(records=records, unresolved=unresolved)


def _write_jsonl(path: Path, models: Sequence[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for m in models:
            f.write(orjson.dumps(m.model_dump(mode="json")))
            f.write(b"\n")


def _write_output(records: list[ProfileRecord], catalogue, *, profile_id: str, data_root: Path) -> None:
    profiles_dir = data_root / "output" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(profiles_dir / f"{profile_id}.jsonl", records)
    (profiles_dir / f"{profile_id}.json").write_bytes(
        orjson.dumps([r.model_dump(mode="json") for r in records], option=orjson.OPT_INDENT_2)
    )

    import csv

    with (profiles_dir / f"{profile_id}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "control_id",
                "family_id",
                "name",
                "requirement_kind",
                "selected",
                "selected_raw",
                "suggested_placeholder_values_raw",
                "profile_specific_notes",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r.control_id,
                    r.family_id,
                    r.name,
                    r.requirement_kind.value,
                    r.selected,
                    r.selected_raw,
                    r.suggested_placeholder_values_raw or "",
                    r.profile_specific_notes or "",
                ]
            )

    # Project profile membership onto the reconciled catalogue (spec S8.4).
    catalogue_dir = data_root / "normalized" / "reconciliation"
    _write_jsonl(catalogue_dir / "catalogue.jsonl", catalogue)
