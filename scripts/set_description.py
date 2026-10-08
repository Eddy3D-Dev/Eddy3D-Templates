#!/usr/bin/env python3
"""Add or update the "Description" Panel in Grasshopper .ghx templates.

The gallery (docs/index.html) shows, on each template's card, the text of a
Panel whose nickname is "Description" (see scripts/extract_descriptions.py).
This script writes that panel without opening Grasshopper:

    python scripts/set_description.py Outdoor/OpenFOAM/BoxDomain.ghx "One hundred words..."
    python scripts/set_description.py --from-json descriptions-to-apply.json
    python scripts/set_description.py --dry-run --from-json descriptions-to-apply.json

The JSON maps repository-relative template paths to description text:

    { "Outdoor/OpenFOAM/BoxDomain.ghx": "Wind CFD in a box domain ..." }

It edits the file as TEXT, never re-serialising the XML, so the diff of a
template is the new panel and nothing else (the files are UTF-8 with a BOM and
mostly LF; one is CRLF - both are preserved). Running it twice with the same
text is a no-op: the panel's InstanceGuid is derived from the template path,
and an existing Description panel is updated in place rather than duplicated.

The panel is placed above the top-left corner of the definition so it is the
first thing seen when the file is opened. House target: 100 words.
"""
import argparse
import json
import math
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = uuid.UUID("5fd2c8e1-3a4b-4c1d-9e7a-0d3e0a5b6c21")  # fixed: keeps panel guids stable
PANEL_GUID = "59e0b89a-e487-49f8-bab8-b5bab16be14c"  # Grasshopper's built-in Panel
PANEL_W = 420.0
HOUSE_WORDS = 100

# Copied from a Panel saved by Grasshopper itself (Indoor/Validation_Zhang_Chen_UFAD.ghx).
# Placeholders ({index}, {guid}, {text}, {x}, {y}, {w}, {h}) are filled in set_description().
PANEL_TEMPLATE = """\
<chunk name="Object" index="{index}">
  <items count="2">
    <item name="GUID" type_name="gh_guid" type_code="9">59e0b89a-e487-49f8-bab8-b5bab16be14c</item>
    <item name="Name" type_name="gh_string" type_code="10">Panel</item>
  </items>
  <chunks count="1">
    <chunk name="Container">
      <items count="8">
        <item name="Description" type_name="gh_string" type_code="10">A panel for custom notes and text values</item>
        <item name="InstanceGuid" type_name="gh_guid" type_code="9">{guid}</item>
        <item name="Name" type_name="gh_string" type_code="10">Panel</item>
        <item name="NickName" type_name="gh_string" type_code="10">Description</item>
        <item name="Optional" type_name="gh_bool" type_code="1">false</item>
        <item name="ScrollRatio" type_name="gh_double" type_code="6">0</item>
        <item name="SourceCount" type_name="gh_int32" type_code="3">0</item>
        <item name="UserText" type_name="gh_string" type_code="10">{text}</item>
      </items>
      <chunks count="2">
        <chunk name="Attributes">
          <items count="4">
            <item name="Bounds" type_name="gh_drawing_rectanglef" type_code="35">
              <X>{x}</X>
              <Y>{y}</Y>
              <W>{w}</W>
              <H>{h}</H>
            </item>
            <item name="MarginLeft" type_name="gh_int32" type_code="3">0</item>
            <item name="MarginRight" type_name="gh_int32" type_code="3">0</item>
            <item name="MarginTop" type_name="gh_int32" type_code="3">0</item>
          </items>
        </chunk>
        <chunk name="PanelProperties">
          <items count="7">
            <item name="Colour" type_name="gh_drawing_color" type_code="36">
              <ARGB>255;255;250;90</ARGB>
            </item>
            <item name="DrawIndices" type_name="gh_bool" type_code="1">true</item>
            <item name="DrawPaths" type_name="gh_bool" type_code="1">true</item>
            <item name="Multiline" type_name="gh_bool" type_code="1">true</item>
            <item name="SpecialCodes" type_name="gh_bool" type_code="1">false</item>
            <item name="Stream" type_name="gh_bool" type_code="1">false</item>
            <item name="Wrap" type_name="gh_bool" type_code="1">true</item>
          </items>
        </chunk>
      </chunks>
    </chunk>
  </chunks>
</chunk>"""

OBJECTS_HEAD = re.compile(
    r'<chunk name="DefinitionObjects">\s*<items count="1">\s*'
    r'<item name="ObjectCount" type_name="gh_int32" type_code="3">(\d+)</item>\s*</items>\s*'
    r'<chunks count="(\d+)">'
)
NICK_DESC = re.compile(r'<item name="NickName" type_name="gh_string" type_code="10">\s*description\s*</item>', re.I)
TOKEN = re.compile(r"<chunk\b|</chunk>")
CHUNKS_TOKEN = re.compile(r"<chunks\b|</chunks>")


class TemplateError(Exception):
    pass


def xml_text(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def panel_height(text: str) -> int:
    lines = sum(max(1, math.ceil(len(p) / 52)) for p in text.split("\n"))
    return int(round((lines * 16 + 28) / 10.0) * 10)


def child_chunk(parent: ET.Element, name: str):
    chunks = parent.find("chunks")
    if chunks is None:
        return None
    return next((c for c in chunks.findall("chunk") if c.get("name") == name), None)


def object_bounds(root: ET.Element):
    """(minX, minY) over the top-level objects, ignoring any existing Description panel."""
    xs, ys = [], []
    definition = next(c for c in root.iter("chunk") if c.get("name") == "Definition")
    objs = next(c for c in definition.find("chunks").findall("chunk") if c.get("name") == "DefinitionObjects")
    for obj in objs.find("chunks").findall("chunk"):
        cont = child_chunk(obj, "Container")
        if cont is None:
            continue
        items = {i.get("name"): i for i in cont.find("items").findall("item")}
        nick = (items["NickName"].text or "") if "NickName" in items else ""
        if nick.strip().lower() == "description":
            continue
        attr = child_chunk(cont, "Attributes")
        if attr is None or attr.find("items") is None:
            continue
        for it in attr.find("items").findall("item"):
            if it.get("name") in ("Bounds", "Pivot"):
                try:
                    xs.append(float(it.find("X").text))
                    ys.append(float(it.find("Y").text))
                except (AttributeError, TypeError, ValueError):
                    pass
    if not xs:
        return 0.0, 0.0
    return min(xs), min(ys)


def matching_close(s: str, start: int, token: re.Pattern, open_prefix: str) -> int:
    """Index of the closing tag that balances the opening tag found at `start`."""
    depth = 0
    for m in token.finditer(s, start):
        depth += 1 if m.group().startswith(open_prefix) else -1
        if depth == 0:
            return m.start()
    raise TemplateError("unbalanced chunk structure")


def set_description(path: Path, text: str, dry_run: bool = False) -> str:
    raw = path.read_bytes().decode("utf-8")  # keeps the BOM as U+FEFF so it is written back
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = text.strip().replace("\r\n", "\n")
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() and ROOT in path.parents else path.as_posix()

    root = ET.fromstring(raw.lstrip("﻿"))
    min_x, min_y = object_bounds(root)
    height = panel_height(text)
    # 100 px clear of the topmost object: a Group frame is drawn ~55 px above its members and has
    # no Bounds in the file, so the numbers read here understate where the canvas really starts.
    x, y = int(min_x), int(min_y - height - 100)
    guid = str(uuid.uuid5(NAMESPACE, "description:" + rel))

    nick = NICK_DESC.search(raw)
    if nick:
        obj_start = raw.rfind('<chunk name="Object"', 0, nick.start())
        obj_end = matching_close(raw, obj_start, TOKEN, "<chunk")
        block = raw[obj_start:obj_end]
        if not re.search(r'<item name="UserText"', block):
            raise TemplateError("existing Description panel has no UserText item")
        block = re.sub(
            r'(<item name="UserText" type_name="gh_string" type_code="10">).*?(</item>)',
            lambda m: m.group(1) + xml_text(text) + m.group(2),
            block, count=1, flags=re.S,
        )
        # re-seat the panel at the standard place and size
        block = re.sub(
            r'(<item name="Bounds" type_name="gh_drawing_rectanglef" type_code="35">\s*)<X>.*?</X>(\s*)<Y>.*?</Y>(\s*)<W>.*?</W>(\s*)<H>.*?</H>',
            lambda m: f"{m.group(1)}<X>{x}</X>{m.group(2)}<Y>{y}</Y>{m.group(3)}<W>{int(PANEL_W)}</W>{m.group(4)}<H>{height}</H>",
            block, count=1, flags=re.S,
        )
        out = raw[:obj_start] + block + raw[obj_end:]
        action = "updated"
    else:
        head = OBJECTS_HEAD.search(raw)
        if not head:
            raise TemplateError("DefinitionObjects header not found")
        count, chunk_count = int(head.group(1)), int(head.group(2))
        if count != chunk_count:
            raise TemplateError(f"ObjectCount {count} != chunks count {chunk_count}; refusing to guess")
        chunks_open = head.end() - len(f'<chunks count="{chunk_count}">')
        close = matching_close(raw, chunks_open, CHUNKS_TOKEN, "<chunks")
        # indentation of the existing Object chunks (taken from the first one)
        first = raw.find('<chunk name="Object"', head.end())
        line_start = raw.rfind("\n", 0, first) + 1
        indent = raw[line_start:first]
        if indent.strip():
            raise TemplateError("could not determine Object chunk indentation")
        panel = PANEL_TEMPLATE.format(
            index=count, guid=guid, text=xml_text(text), x=x, y=y, w=int(PANEL_W), h=height,
        )
        panel = eol.join((indent + ln) if i else ln for i, ln in enumerate(panel.split("\n")))
        # `close` points at </chunks>; its own line indentation precedes it
        close_line = raw.rfind("\n", 0, close) + 1
        insert_at = close_line
        out = raw[:insert_at] + indent + panel + eol + raw[insert_at:]
        # bump the two counters (both live inside the header we matched)
        header = out[head.start():head.end()]
        header = header.replace(f'type_code="3">{count}</item>', f'type_code="3">{count + 1}</item>', 1)
        header = header.replace(f'<chunks count="{chunk_count}">', f'<chunks count="{chunk_count + 1}">', 1)
        out = out[:head.start()] + header + out[head.end():]
        action = "added"

    # sanity: still well-formed, exactly one Description panel, counters agree
    check = ET.fromstring(out.lstrip("﻿"))
    n = sum(1 for e in check.iter("item") if e.get("name") == "NickName" and (e.text or "").strip().lower() == "description")
    if n != 1:
        raise TemplateError(f"expected exactly one Description panel after edit, found {n}")
    if not dry_run and out != raw:
        path.write_bytes(out.encode("utf-8"))
    return action if out != raw else "unchanged"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template", nargs="?", help="path of one .ghx")
    ap.add_argument("text", nargs="?", help="description text for that template")
    ap.add_argument("--from-json", help="JSON file mapping repo-relative .ghx paths to description text")
    ap.add_argument("--dry-run", action="store_true", help="validate and report without writing")
    args = ap.parse_args()

    jobs = []
    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        jobs = [(ROOT / rel, text) for rel, text in data.items()]
    elif args.template and args.text is not None:
        jobs = [(Path(args.template).resolve(), args.text)]
    else:
        ap.error("give a template and text, or --from-json")

    failed = 0
    for path, text in jobs:
        words = len(text.split())
        flag = "" if words == HOUSE_WORDS else f"  (! {words} words, house target {HOUSE_WORDS})"
        try:
            action = set_description(path, text, args.dry_run)
            print(f"{action:9s} {path.relative_to(ROOT).as_posix()}{flag}")
        except (TemplateError, ET.ParseError, OSError) as e:
            failed += 1
            print(f"FAILED    {path}: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
