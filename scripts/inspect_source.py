#!/usr/bin/env python3
"""Ad-hoc inspection helper for raw source snapshots.

Not part of the `itsp-kb` package/CLI -- a developer utility for eyeballing a
raw NIST OSCAL control or a Cyber Centre family-page control section without
writing a one-off script each time (spec S4 lists this file in the canonical
layout).

Usage:
    uv run python scripts/inspect_source.py nist ac-2
    uv run python scripts/inspect_source.py canada access-control AC-02
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itsp_kb.provenance import latest_raw_snapshot_dir  # noqa: E402


def inspect_nist(oscal_id: str) -> None:
    snap = latest_raw_snapshot_dir("nist_sp800_53_rev5_oscal")
    if snap is None:
        print("No NIST snapshot found; run `itsp-kb fetch` first.")
        return
    data = json.loads((snap / "catalog.json").read_text(encoding="utf-8"))

    def walk(controls: list[dict]) -> dict | None:
        for c in controls:
            if c["id"] == oscal_id:
                return c
            if found := walk(c.get("controls", [])):
                return found
        return None

    for group in data["catalog"]["groups"]:
        if found := walk(group.get("controls", [])):
            print(json.dumps(found, indent=2))
            return
    print(f"'{oscal_id}' not found in the latest NIST snapshot.")


def inspect_canada(family_slug: str, control_id: str) -> None:
    from bs4 import BeautifulSoup

    snap = latest_raw_snapshot_dir("itsp_10_033")
    if snap is None:
        print("No ITSP.10.033 snapshot found; run `itsp-kb fetch` first.")
        return
    html_path = snap / family_slug / "source.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")
    h2 = soup.find("h2", id=lambda v: bool(v) and v.endswith(f"-{control_id}"))
    if h2 is None:
        print(f"'{control_id}' not found on '{family_slug}' page.")
        return
    parts = [str(h2)]
    for sib in h2.find_next_siblings():
        if sib.name == "h2":
            break
        parts.append(str(sib))
    print("\n".join(parts))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "nist":
        inspect_nist(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "canada":
        inspect_canada(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)
