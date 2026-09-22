"""OSCAL <-> Canadian canonical ID mapping (spec S5.6, S6.5, S7.5).

The mapper prefers the actual OSCAL parent/child nesting (as walked by the NIST
importer) over string-splitting alone: `map_child_control` takes the *already
computed* canonical ID of the parent and validates the child's OSCAL id is
actually nested under it before deriving the enhancement suffix. Pure
string-splitting (`oscal_control_id_to_canonical`) is only used for the base
(non-nested) case, where there is no ambiguity to resolve against a parent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# OSCAL ids observed in the NIST SP 800-53 Rev 5 catalog: "ac-1", "ac-2.1", "sa-8.33".
_OSCAL_BASE_RE = re.compile(r"^(?P<family>[a-z]{2})-(?P<num>\d{1,3})$")
_OSCAL_ENH_RE = re.compile(r"^(?P<family>[a-z]{2})-(?P<num>\d{1,3})\.(?P<enh>\d{1,3})$")

# Canadian canonical ids (spec S7.5). Deliberately not fixed at 2 digits ("Do not
# assume all identifiers are two digits forever").
CANADIAN_BASE_ID_RE = re.compile(r"^[A-Z]{2}-\d{2,3}$")
CANADIAN_ENH_ID_RE = re.compile(r"^[A-Z]{2}-\d{2,3}\(\d{2,3}\)$")
CANADIAN_ANY_ID_RE = re.compile(r"^[A-Z]{2}-\d{2,3}(\(\d{2,3}\))?$")

CANADIAN_SPECIFIC_THRESHOLD = 400


class IdMappingError(ValueError):
    """Raised when an OSCAL id cannot be deterministically mapped."""


@dataclass(frozen=True)
class ParsedCanadianId:
    family: str
    base_num: str  # zero-padded, e.g. "02" or "400"
    enh_num: str | None  # zero-padded, e.g. "01", or None for a base record

    @property
    def base_id(self) -> str:
        return f"{self.family}-{self.base_num}"

    @property
    def full_id(self) -> str:
        if self.enh_num is None:
            return self.base_id
        return f"{self.base_id}({self.enh_num})"

    @property
    def is_canadian_specific(self) -> bool:
        # For an enhancement, Canadian-specificity is about the *enhancement* number
        # (e.g. "AC-17(400)" is a Canada-only enhancement of an otherwise NIST-backed
        # base control); for a base record it's the base number (e.g. "SA-400").
        num = self.enh_num if self.enh_num is not None else self.base_num
        return int(num) >= CANADIAN_SPECIFIC_THRESHOLD


def oscal_control_id_to_canonical(oscal_id: str) -> str:
    """Map a *base* (non-nested) OSCAL control id to its Canadian canonical id.

    Examples: "ac-1" -> "AC-01", "sa-8" -> "SA-08".
    Only valid for base controls; enhancements must go through `map_child_control`
    so the parent relationship is verified rather than assumed from string shape.
    """
    m = _OSCAL_BASE_RE.match(oscal_id)
    if not m:
        raise IdMappingError(f"'{oscal_id}' is not a recognized base OSCAL control id")
    family = m.group("family").upper()
    num = int(m.group("num"))
    return f"{family}-{num:02d}"


def map_child_control(oscal_id: str, parent_canonical_id: str, parent_oscal_id: str) -> str:
    """Map a nested OSCAL enhancement id to its Canadian canonical id.

    Requires the caller to supply the parent's OSCAL id and its *already
    resolved* Canadian canonical id (from walking the actual OSCAL nesting),
    so the mapping is anchored to the real hierarchy rather than re-derived
    from string splitting alone. Raises if `oscal_id` is not actually nested
    under `parent_oscal_id`.
    """
    if not oscal_id.startswith(parent_oscal_id + "."):
        raise IdMappingError(f"'{oscal_id}' is not nested under parent OSCAL id '{parent_oscal_id}'")
    suffix = oscal_id[len(parent_oscal_id) + 1 :]
    if not suffix.isdigit():
        raise IdMappingError(
            f"'{oscal_id}' has a non-numeric enhancement suffix relative to parent '{parent_oscal_id}'"
        )
    enh_num = int(suffix)
    return f"{parent_canonical_id}({enh_num:02d})"


def oscal_id_to_canonical_any(oscal_id: str) -> str:
    """Best-effort mapper for a standalone OSCAL id of unknown nesting depth.

    Used only for diagnostics/tests where no parent context is available; the
    NIST importer itself always uses `map_child_control` with real hierarchy.
    """
    m = _OSCAL_ENH_RE.match(oscal_id)
    if m:
        family = m.group("family").upper()
        base_num = int(m.group("num"))
        enh_num = int(m.group("enh"))
        return f"{family}-{base_num:02d}({enh_num:02d})"
    return oscal_control_id_to_canonical(oscal_id)


def parse_canadian_id(canonical_id: str) -> ParsedCanadianId:
    """Parse a Canadian canonical id such as 'AC-02', 'AC-02(01)', 'SA-400'."""
    if not CANADIAN_ANY_ID_RE.match(canonical_id):
        raise IdMappingError(f"'{canonical_id}' is not a recognized Canadian canonical id")
    if "(" in canonical_id:
        base_part, rest = canonical_id.split("(", 1)
        enh_num = rest.rstrip(")")
    else:
        base_part = canonical_id
        enh_num = None
    family, base_num = base_part.split("-", 1)
    return ParsedCanadianId(family=family, base_num=base_num, enh_num=enh_num)


def render_canadian_enhancement(base_id: str, enh_number: str | int) -> str:
    """Render 'AC-02' + '01' (or 1) -> 'AC-02(01)'."""
    if not CANADIAN_BASE_ID_RE.match(base_id):
        raise IdMappingError(f"'{base_id}' is not a recognized Canadian base id")
    n = int(enh_number)
    return f"{base_id}({n:02d})"


def is_canadian_specific_id(canonical_id: str) -> bool:
    return parse_canadian_id(canonical_id).is_canadian_specific
