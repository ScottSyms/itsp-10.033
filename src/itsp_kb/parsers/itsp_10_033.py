"""ITSP.10.033 Canadian overlay parser (spec S7).

Extracts the Canadian-authoritative representation of each control, activity,
and enhancement from the fetched family HTML pages. This module does *not*
reconcile against NIST (see `itsp_kb.reconcile`) -- it only produces
`CanadianParsedRecord` objects with everything the Cyber Centre source
actually states, per S7.1: "The Cyber Centre parser is no longer responsible
for inventing the entire NIST-derived data model from HTML."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import orjson
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel

from itsp_kb.config import DEFAULT_DATA_ROOT, load_registry
from itsp_kb.ids import IdMappingError, parse_canadian_id, render_canadian_enhancement
from itsp_kb.models.canada import CanadianParsedEnhancement, CanadianParsedRecord
from itsp_kb.models.common import CanadaSourceRef, Reference, RequirementKind
from itsp_kb.parsers.html_utils import (
    ENHANCEMENT_HEADER_RE,
    H2_ID_RE,
    H2_TEXT_RE,
    build_statement_nodes,
    build_statement_nodes_from_lis,
    classify_enhancement_sub_item,
    extract_odps_from_statement,
    extract_related_ids,
    flatten_statement_text,
    get_text_ws,
    split_control_sections,
)
from itsp_kb.provenance import latest_raw_snapshot_dir, read_fetch_meta, sha256_hex

logger = logging.getLogger(__name__)


class CanadaParseError(ValueError):
    def __init__(self, message: str, *, family_id: str | None = None, control_id: str | None = None):
        super().__init__(message)
        self.family_id = family_id
        self.control_id = control_id


def _join_paragraphs(nodes: list[Tag]) -> str:
    parts = [get_text_ws(n) for n in nodes if get_text_ws(n)]
    return "\n\n".join(parts)


def _parse_references(nodes: list[Tag]) -> list[Reference]:
    references: list[Reference] = []
    for node in nodes:
        if node.name != "ul":
            continue
        for li in node.find_all("li", recursive=False):
            text = get_text_ws(li)
            if not text:
                continue
            anchor = li.find("a", href=True)
            references.append(
                Reference(
                    title=text,
                    url=anchor["href"] if anchor else None,
                    publisher=None,
                    external=True,
                    source_authority="Canada",
                )
            )
    return references


def _parse_enhancements(
    nodes: list[Tag], *, parent_id: str, family_id: str, parent_is_canadian_specific: bool
) -> list[CanadianParsedEnhancement]:
    enhancements: list[CanadianParsedEnhancement] = []
    for node in nodes:
        if node.name != "ul":
            continue
        for li in node.find_all("li", recursive=False):
            strong = li.find("strong", recursive=False)
            header_text = get_text_ws(strong) if strong is not None else get_text_ws(li)
            m = ENHANCEMENT_HEADER_RE.match(header_text)
            if not m:
                logger.warning("Could not parse enhancement header '%s' under %s", header_text, parent_id)
                continue
            enh_num = m.group("num")
            name = m.group("name")
            try:
                enh_id = render_canadian_enhancement(parent_id, enh_num)
            except IdMappingError as e:
                raise CanadaParseError(str(e), family_id=family_id, control_id=parent_id) from e

            nested_uls = li.find_all("ul", recursive=False)
            statement_lis: list[Tag] = []
            discussion_chunks: list[str] = []
            gc_discussion_chunks: list[str] = []
            related_chunks: list[str] = []
            if nested_uls:
                # An unlabeled `<li>` continues whichever labeled section came before it
                # (e.g. a second paragraph of "Discussion:" is its own sibling `<li>` with
                # no label of its own) rather than always being a new statement line --
                # confirmed against the real AC-02(01) enhancement, where exactly this
                # pattern occurs (spec S16.7: "discussion merged into requirement statement"
                # is the failure mode this guards against).
                current_label: str | None = None  # None == statement
                for sub in nested_uls[0].find_all("li", recursive=False):
                    label, text = classify_enhancement_sub_item(sub)
                    if label is not None:
                        current_label = label
                    if current_label == "discussion":
                        discussion_chunks.append(text)
                    elif current_label == "gc_discussion":
                        gc_discussion_chunks.append(text)
                    elif current_label == "related":
                        related_chunks.append(text)
                    else:
                        statement_lis.append(sub)

            statements = build_statement_nodes_from_lis(statement_lis)

            enh = CanadianParsedEnhancement(
                id=enh_id,
                parent_id=parent_id,
                enhancement_number=enh_num,
                name=name,
                statements=statements,
                statement_text=flatten_statement_text(statements),
                discussion="\n\n".join(discussion_chunks) or None,
                gc_discussion="\n\n".join(gc_discussion_chunks) or None,
                related=extract_related_ids(" ".join(related_chunks)),
                # An enhancement of a Canada-only (400-series) base has no possible NIST
                # mapping regardless of its own number, so it inherits Canada-only status.
                is_canadian_specific=parent_is_canadian_specific or int(enh_num) >= 400,
            )
            enh.odps = extract_odps_from_statement(enh.statements, enh.id)
            enhancements.append(enh)
    return enhancements


def parse_family_html(
    html: bytes,
    *,
    family_id: str,
    family_name: str,
    url: str,
    retrieved_at: str,
    source_sha256: str,
) -> list[CanadianParsedRecord]:
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main")
    if main is None:
        raise CanadaParseError(f"No <main> element found on family page for {family_id}", family_id=family_id)

    records: list[CanadianParsedRecord] = []
    for h2 in main.find_all("h2", id=True):
        id_match = H2_ID_RE.match(h2["id"])
        if not id_match:
            continue
        canonical_id = id_match.group("id")

        heading_text = get_text_ws(h2)
        text_match = H2_TEXT_RE.match(heading_text)
        name = text_match.group("name") if text_match else heading_text

        nodes: list[Tag] = []
        for sib in h2.find_next_siblings():
            if sib.name == "h2":
                break
            if isinstance(sib, Tag):
                nodes.append(sib)

        sections = split_control_sections(nodes)

        if sections.classification == "control":
            requirement_kind = RequirementKind.CONTROL
        elif sections.classification == "activity":
            requirement_kind = RequirementKind.ACTIVITY
        else:
            requirement_kind = RequirementKind.UNKNOWN
            if not sections.is_withdrawn:
                if sections.classification in ("activity/control", "control/activity"):
                    logger.warning(
                        "%s (%s) is labeled '%s' by the source, not committing to one kind",
                        canonical_id,
                        family_id,
                        sections.classification,
                    )
                else:
                    logger.warning("No Control/Activity classification found for %s (%s)", canonical_id, family_id)

        statement_nodes = []
        for node in sections.sections.get(sections.classification or "", []):
            statement_nodes.extend(build_statement_nodes(node))

        try:
            parsed_id = parse_canadian_id(canonical_id)
        except IdMappingError as e:
            raise CanadaParseError(str(e), family_id=family_id, control_id=canonical_id) from e

        record = CanadianParsedRecord(
            id=canonical_id,
            family_id=family_id,
            family_name=family_name,
            number=parsed_id.base_num,
            name=name,
            requirement_kind=requirement_kind,
            is_canadian_specific=parsed_id.is_canadian_specific,
            is_withdrawn=sections.is_withdrawn,
            withdrawal_note=sections.withdrawal_note,
            statements=statement_nodes,
            discussion=_join_paragraphs(sections.sections.get("discussion", [])) or None,
            gc_discussion=_join_paragraphs(sections.sections.get("gc discussion", [])) or None,
            related=extract_related_ids(_join_paragraphs(sections.sections.get("related controls and activities", []))),
            references=_parse_references(sections.sections.get("references", [])),
            enhancements=_parse_enhancements(
                sections.sections.get("enhancements", []),
                parent_id=canonical_id,
                family_id=family_id,
                parent_is_canadian_specific=parsed_id.is_canadian_specific,
            ),
            source=CanadaSourceRef(
                publication="ITSP.10.033",
                url=url,
                section=f"{family_name} > {canonical_id} {name}",
                retrieved_at=retrieved_at,
                source_sha256=source_sha256,
            ),
        )
        record.statement_text = flatten_statement_text(statement_nodes)
        record.odps = extract_odps_from_statement(statement_nodes, canonical_id)
        records.append(record)

    return records


@dataclass
class CanadaParseResult:
    families: list[str] = field(default_factory=list)
    records: list[CanadianParsedRecord] = field(default_factory=list)


def parse_all_families(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    family_filter: str | None = None,
    strict: bool = False,
) -> CanadaParseResult:
    registry = load_registry()
    source = registry["itsp_10_033"]
    snapshot_dir = latest_raw_snapshot_dir("itsp_10_033", data_root=data_root)
    if snapshot_dir is None:
        raise FileNotFoundError("No ITSP.10.033 snapshot found; run `itsp-kb fetch` first.")

    all_records: list[CanadianParsedRecord] = []
    families_seen: list[str] = []
    seen_ids: set[str] = set()

    for family in source.families:
        if family_filter and family.id != family_filter:
            continue
        family_dir = snapshot_dir / family.slug
        html_path = family_dir / "source.html"
        if not html_path.exists():
            msg = f"Missing snapshot for family '{family.id}' ({family.slug}); run `itsp-kb fetch` first."
            if strict:
                raise CanadaParseError(msg, family_id=family.id)
            logger.warning(msg)
            continue

        fetch_meta = read_fetch_meta(family_dir)
        html_bytes = html_path.read_bytes()
        actual_hash = sha256_hex(html_bytes)
        records = parse_family_html(
            html_bytes,
            family_id=family.id,
            family_name=family.name,
            url=fetch_meta["url"],
            retrieved_at=fetch_meta["retrieved_at"],
            source_sha256=actual_hash,
        )
        if not records:
            msg = f"Family page '{family.id}' produced zero records"
            if strict:
                raise CanadaParseError(msg, family_id=family.id)
            logger.warning(msg)

        for r in records:
            if r.id in seen_ids:
                msg = f"Duplicate Canadian canonical id encountered: '{r.id}'"
                if strict:
                    raise CanadaParseError(msg, family_id=family.id, control_id=r.id)
                logger.warning(msg)
            seen_ids.add(r.id)
            for e in r.enhancements:
                if e.id in seen_ids:
                    msg = f"Duplicate Canadian canonical id encountered: '{e.id}'"
                    if strict:
                        raise CanadaParseError(msg, family_id=family.id, control_id=e.id)
                    logger.warning(msg)
                seen_ids.add(e.id)

        all_records.extend(records)
        families_seen.append(family.id)

    _write_normalized_output(all_records, data_root=data_root)
    return CanadaParseResult(families=families_seen, records=all_records)


def _write_jsonl(path: Path, models: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for m in models:
            f.write(orjson.dumps(m.model_dump(mode="json")))
            f.write(b"\n")


def _write_normalized_output(records: list[CanadianParsedRecord], *, data_root: Path) -> None:
    out_dir = data_root / "normalized" / "canada"
    _write_jsonl(out_dir / "records.jsonl", records)


def load_normalized_canada(data_root: Path = DEFAULT_DATA_ROOT) -> list[CanadianParsedRecord]:
    out_dir = data_root / "normalized" / "canada"
    return [
        CanadianParsedRecord.model_validate(orjson.loads(line))
        for line in (out_dir / "records.jsonl").read_bytes().splitlines()
        if line
    ]
