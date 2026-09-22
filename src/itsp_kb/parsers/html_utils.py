"""Generic HTML/DOM helpers shared by the Cyber Centre parsers (spec S7.2:
"prefer semantic headings and DOM traversal over fragile CSS selectors").

These were written against the *real* fetched ITSP.10.033 and
ITSP.10.033-01 pages (not guessed), specifically:

- Each control/activity is bounded by an `<h2 id="{section}-{ID}">{ID} {Name}</h2>`.
- Content between one `<h2>` and the next is split into sections by real
  `<h3>` headings ("Control"/"Activity", "Discussion", the GC-discussion
  heading -- whose "GC" is wrapped in an `<abbr>` tag, so it must be read
  with `get_text(" ", strip=True)` rather than a raw string search --
  "Related controls and activities", "Enhancements") *and* by two headings
  that are rendered as plain `<p>` text rather than `<h3>`: "References:"
  and, when a control has no enhancements, "Enhancements: None."
- Enhancement statement/discussion/related sub-fields are similarly encoded
  as `<li><strong>Label:</strong> ...</li>` items inside a nested
  `<ul class="list-unstyled">`, with un-labeled `<li>` items being the
  enhancement's own statement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4.element import NavigableString, Tag

from itsp_kb.models.common import Odp, OdpOperation, StatementNode

WHITESPACE_RE = re.compile(r"\s+")

H2_ID_RE = re.compile(r"^(?P<section>[\d.]+)-(?P<id>[A-Z]{2}-\d{2,3}(?:\(\d{2,3}\))?)$")
H2_TEXT_RE = re.compile(r"^(?P<id>[A-Z]{2}-\d{2,3})\s+(?P<name>.+)$")
CANADIAN_ID_IN_TEXT_RE = re.compile(r"[A-Z]{2}-\d{2,3}(?:\(\d{2,3}\))?")
REFERENCES_MARKER_RE = re.compile(r"^references:?\s*$", re.IGNORECASE)
ENHANCEMENTS_NONE_RE = re.compile(r"^enhancements:\s*none\.?$", re.IGNORECASE)
RELATED_NONE_RE = re.compile(r"^none\.?$", re.IGNORECASE)
ENHANCEMENT_HEADER_RE = re.compile(r"^\((?P<num>\d{2,3})\)\s*(?P<name>.+)$")
WITHDRAWN_RE = re.compile(r"^withdrawn:?\s*(?P<note>.*)$", re.IGNORECASE)

# Most controls put their classification in a real `<h3>Control</h3>` /
# `<h3>Activity</h3>` heading, but a real minority (confirmed: AC-12, CM-06,
# and others) instead use a `<p><strong>Control:</strong></p>` (label only,
# statement is the next sibling `<ol>`) or `<p><strong>Activity/Control:
# </strong> ...</p>` (label plus the statement inline in the same `<p>`, and
# in that specific case the source itself does not commit to one kind).
CLASSIFICATION_LABELS = {"control", "activity", "activity/control", "control/activity"}

# Labels that appear as `<li><strong>Label:</strong> ...</li>` inside a nested
# enhancement `<ul>`. Matched case-insensitively against normalized text.
ENHANCEMENT_SUBLABELS = {
    "discussion": "discussion",
    "gc discussion": "gc_discussion",
    "related controls and activities": "related",
}


def normalize_ws(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def get_text_ws(tag: Tag) -> str:
    """`Tag.get_text` with a separator so text split across inline tags (e.g. the
    GC-discussion heading's `<abbr>GC</abbr> discussion`) doesn't get glued together."""
    return normalize_ws(tag.get_text(" ", strip=True))


def direct_text(tag: Tag) -> str:
    """A tag's own text, excluding any nested `<ol>`/`<ul>` (which become child
    StatementNodes instead of being duplicated into the parent's text)."""
    parts: list[str] = []
    for child in tag.children:
        if isinstance(child, Tag) and child.name in ("ol", "ul"):
            continue
        if isinstance(child, Tag):
            parts.append(child.get_text(" ", strip=True))
        elif isinstance(child, NavigableString):
            parts.append(str(child))
    return normalize_ws(" ".join(p for p in parts if p))


def _index_label(depth: int, index: int) -> str:
    """Deterministic outline label for a list item: letters at even depths,
    numbers at odd depths (matches the spec's own "a", "a.1" examples)."""
    if depth % 2 == 0:
        return chr(ord("a") + index)
    return str(index + 1)


def build_statement_nodes_from_lis(li_tags: list[Tag], *, depth: int = 0, prefix: str = "") -> list[StatementNode]:
    nodes: list[StatementNode] = []
    for i, li in enumerate(li_tags):
        label = _index_label(depth, i)
        path = f"{prefix}.{label}" if prefix else label
        text = direct_text(li)
        children: list[StatementNode] = []
        for sublist in li.find_all(["ol", "ul"], recursive=False):
            sub_lis = sublist.find_all("li", recursive=False)
            children.extend(build_statement_nodes_from_lis(sub_lis, depth=depth + 1, prefix=path))
        nodes.append(StatementNode(path=path, text=text, children=children))
    return nodes


def build_statement_nodes(container: Tag) -> list[StatementNode]:
    """Build a StatementNode tree from a top-level `<ol>`/`<ul>` (or a bare
    `<p>`, treated as a single unlabeled statement node)."""
    if container.name in ("ol", "ul"):
        return build_statement_nodes_from_lis(container.find_all("li", recursive=False))
    text = direct_text(container)
    if not text:
        return []
    return [StatementNode(path="a", text=text, children=[])]


def flatten_statement_text(nodes: list[StatementNode]) -> str:
    lines: list[str] = []

    def walk(ns: list[StatementNode]) -> None:
        for n in ns:
            if n.text:
                lines.append(f"({n.path}) {n.text}")
            walk(n.children)

    walk(nodes)
    return "\n".join(lines)


def extract_related_ids(text: str) -> list[str]:
    if RELATED_NONE_RE.match(text.strip()):
        return []
    return CANADIAN_ID_IN_TEXT_RE.findall(text)


def classify_enhancement_sub_item(li: Tag) -> tuple[str | None, str]:
    """Classify one `<li>` inside an enhancement's nested `<ul class="list-unstyled">`.

    Returns `(label, text)` where `label` is one of ENHANCEMENT_SUBLABELS'
    values when the `<li>` starts with a recognized `<strong>Label:</strong>`
    prefix, or `(None, text)` when it's an unlabeled statement line.
    """
    strong = li.find("strong", recursive=False)
    if strong is not None:
        label_prefix = get_text_ws(strong)
        label_raw = label_prefix.rstrip(":").lower()
        if label_raw in ENHANCEMENT_SUBLABELS:
            # Unlike a statement `<li>` (where nested `<ol>`/`<ul>` become separate
            # StatementNode children), discussion/related prose has no such structure
            # to preserve, so nested list text is flattened in rather than dropped.
            full_text = get_text_ws(li)
            remainder = full_text[len(label_prefix) :].strip() if full_text.startswith(label_prefix) else full_text
            return ENHANCEMENT_SUBLABELS[label_raw], remainder
    return None, direct_text(li)


# Matches "[Assignment: ...]" / "[Selection: ...]" / "[Selection (one or more): ...]" /
# "[Selection (1 or more): ...]" (spec S5.10). Bracket bodies observed in the live
# pages never contain nested brackets, so a non-nested match is sufficient.
ODP_BRACKET_RE = re.compile(
    r"\[(?P<kind>Assignment|Selection)\s*(?P<cardinality>\([^)]*\))?\s*:\s*(?P<body>[^\[\]]+)\]",
    re.IGNORECASE,
)


def _extract_odps_from_text(text: str, *, record_id: str, statement_path: str | None, counter: list[int]) -> list[Odp]:
    odps: list[Odp] = []
    for m in ODP_BRACKET_RE.finditer(text):
        counter[0] += 1
        kind = m.group("kind").lower()
        cardinality = m.group("cardinality")
        cardinality_norm = normalize_ws(cardinality.strip("()")) if cardinality else None
        body = normalize_ws(m.group("body"))
        operation = OdpOperation.ASSIGNMENT if kind == "assignment" else OdpOperation.SELECTION
        options = [normalize_ws(o) for o in body.split(";") if o.strip()] if operation == OdpOperation.SELECTION else []
        odps.append(
            Odp(
                odp_id=f"{record_id}:odp:{counter[0]:03d}",
                nist_param_id=None,
                operation=operation,
                cardinality=cardinality_norm,
                raw=m.group(0),
                prompt=body,
                options=options,
                statement_path=statement_path,
                character_start=m.start(),
                character_end=m.end(),
            )
        )
    return odps


def extract_odps_from_statement(nodes: list[StatementNode], record_id: str) -> list[Odp]:
    """Walk a StatementNode tree extracting ODP bracket placeholders in document order."""
    counter = [0]
    odps: list[Odp] = []

    def walk(ns: list[StatementNode]) -> None:
        for n in ns:
            if n.text:
                odps.extend(
                    _extract_odps_from_text(n.text, record_id=record_id, statement_path=n.path, counter=counter)
                )
            walk(n.children)

    walk(nodes)
    return odps


@dataclass
class ControlSections:
    """The result of splitting one control/activity's `<h2>...</h2>` sibling
    run into named sections, keyed by normalized heading text plus the two
    plain-`<p>` pseudo-headings ("references", "enhancements" when empty)."""

    classification: str | None = None  # "control" | "activity" | "activity/control" | "control/activity"
    sections: dict[str, list[Tag]] = field(default_factory=dict)
    enhancements_explicitly_none: bool = False
    is_withdrawn: bool = False
    withdrawal_note: str | None = None


def split_control_sections(nodes: list[Tag]) -> ControlSections:
    result = ControlSections()
    current_key = "_preamble"
    result.sections[current_key] = []

    for node in nodes:
        if not isinstance(node, Tag):
            continue
        if node.name == "h3":
            heading = get_text_ws(node).lower()
            if heading in ("control", "activity"):
                result.classification = heading
            current_key = heading
            result.sections.setdefault(current_key, [])
            continue
        if node.name == "p":
            text = get_text_ws(node)

            withdrawn_match = WITHDRAWN_RE.match(text)
            if withdrawn_match:
                result.is_withdrawn = True
                result.withdrawal_note = text
                continue

            label_strong = node.find("strong", recursive=False)
            if label_strong is not None:
                label_text = get_text_ws(label_strong).rstrip(":").lower()
                if label_text in CLASSIFICATION_LABELS:
                    result.classification = label_text
                    current_key = label_text
                    result.sections.setdefault(current_key, [])
                    label_strong.decompose()
                    if get_text_ws(node):
                        result.sections[current_key].append(node)
                    continue

            if REFERENCES_MARKER_RE.match(text):
                current_key = "references"
                result.sections.setdefault(current_key, [])
                continue
            if ENHANCEMENTS_NONE_RE.match(text):
                result.enhancements_explicitly_none = True
                current_key = "enhancements"
                result.sections.setdefault(current_key, [])
                continue
        result.sections.setdefault(current_key, []).append(node)

    return result
