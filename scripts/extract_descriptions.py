#!/usr/bin/env python3
"""Extract template descriptions from Grasshopper .ghx files.

A template can document itself by containing a Panel component whose
nickname is "Description" (case-insensitive). This script scans all
.ghx files in the repository, pulls the panel text, and writes
docs/descriptions.json keyed by file name, e.g.:

    { "BoxDomain.ghx": "OpenFOAM wind simulation in a box domain." }

Run from the repository root: python scripts/extract_descriptions.py
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "descriptions.json"


def panel_description(ghx: Path) -> str | None:
    try:
        tree = ET.parse(ghx)
    except ET.ParseError as e:
        print(f"  ! parse error in {ghx.name}: {e}", file=sys.stderr)
        return None
    for items in tree.iter("items"):
        name = nick = text = None
        for item in items.findall("item"):
            attr = item.get("name")
            if attr == "Name":
                name = item.text
            elif attr == "NickName":
                nick = item.text
            elif attr == "UserText":
                text = item.text
        if name == "Panel" and nick and nick.strip().lower() == "description":
            return (text or "").strip() or None
    return None


def main() -> None:
    descriptions = {}
    for ghx in sorted(ROOT.rglob("*.ghx")):
        if ".claude" in ghx.parts:
            continue
        desc = panel_description(ghx)
        if desc:
            descriptions[ghx.name] = desc
            print(f"  + {ghx.name}: {desc[:70]}")
        else:
            print(f"  - {ghx.name}: no 'Description' panel")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(descriptions, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(descriptions)} descriptions)")


if __name__ == "__main__":
    main()
