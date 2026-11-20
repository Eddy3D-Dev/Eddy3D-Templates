#!/usr/bin/env python3
"""Extract template descriptions from Grasshopper .ghx files.

A template documents itself by containing a Panel component whose nickname is
"Description" (case-insensitive), holding six labelled lines in a fixed order -
Purpose, Fidelity, Method, Result, Needs, Edit (see scripts/description_format.py
for the rules). This script scans every .ghx in the repository, parses each
panel into those fields, and writes docs/descriptions.json keyed by file name:

    { "BoxDomain.ghx": { "Purpose": "...", "Fidelity": "...", ... } }

It also writes docs/manifest.json: every .ghx with its size, and the preview
images in docs/previews/. The gallery reads both from the branch being browsed,
so listing templates costs no GitHub API call (the API allows 60 per hour per IP).

A template with no panel, or a panel that breaks the structure, is reported;
on GitHub Actions the findings become annotations. Pass --strict to exit
non-zero on any finding (local use, CI gates). Internal/ templates are hidden
from the gallery but follow the same structure and are linted too.

Run from anywhere: python scripts/extract_descriptions.py [--strict]
Write a description into a template with scripts/set_description.py.
"""
import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from description_format import parse

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "descriptions.json"
MANIFEST = ROOT / "docs" / "manifest.json"



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


def annotate(level: str, rel: str, message: str) -> None:
    """Print a lint finding; as a workflow annotation when running on GitHub Actions."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{level} file={rel}::{message}")
    else:
        print(f"  ! {rel}: {message}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 if any template is missing a description or breaks its structure")
    args = ap.parse_args()

    descriptions: dict[str, dict[str, str]] = {}
    paths: dict[str, str] = {}
    templates: list[dict] = []
    findings = 0
    for ghx in sorted(ROOT.rglob("*.ghx")):
        rel = ghx.relative_to(ROOT)
        if ".claude" in rel.parts:  # relative: ROOT itself may live under a .claude worktree
            continue
        if ghx.name in paths:
            annotate("error", rel.as_posix(), f"file name also used by {paths[ghx.name]}; descriptions are keyed by file name")
            findings += 1
        paths[ghx.name] = rel.as_posix()
        templates.append({"path": rel.as_posix(), "size": ghx.stat().st_size})

        text = panel_description(ghx)
        if not text:
            print(f"  - {ghx.name}: no 'Description' panel")
            annotate("warning", rel.as_posix(), "no Panel nicknamed 'Description'; the gallery card falls back to generic text")
            findings += 1
            continue

        fields, problems = parse(text)
        descriptions[ghx.name] = fields
        print(f"  + {ghx.name}: {fields.get('Purpose', '')[:70]}")
        for problem in problems:
            annotate("warning", rel.as_posix(), problem)
            findings += 1

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(descriptions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    previews = sorted(p.name for p in (ROOT / "docs" / "previews").glob("*") if p.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg"})
    try:  # commit date of the latest change to any template or preview; the gallery shows it
        updated = subprocess.run(["git", "log", "-1", "--format=%cI", "--", "*.ghx", "docs/previews"],
                                 cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        updated = ""
    MANIFEST.write_text(json.dumps({"updated": updated, "templates": templates, "previews": previews}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST.relative_to(ROOT)} ({len(templates)} templates, {len(previews)} previews)")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(descriptions)} descriptions, {findings} finding(s))")
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
