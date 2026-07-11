#!/usr/bin/env python3
"""Generate Outdoor/OpenFOAM/CylinderDomain.ghx from BoxDomain.ghx.

The cylinder template differs from the box template in two ways:

* The Box Domain component is replaced by the Cylinder Domain component
  (one cylindrical mesh serves all wind directions). Parameter names,
  nicknames, descriptions and defaults mirror GH_Strings.CylinderDomain
  in the Eddy3D plugin source; the component GUID comes from
  Outdoor/CMP/CylinderDomainCMP.cs.
* A panel with eight meteorological wind directions (0-315 in 45-degree
  steps) is wired into the Atmospheric Boundary Layer component, so the
  template produces one solver case per direction.

The Domain Parameters output keeps the InstanceGuid of the Box Domain
output it replaces, so the existing wire into the wind case component's
Domain input survives untouched. The panel that fed Box Domain's Cell
Size feeds Cylinder Domain's Core Cell Size, reset from 100 to the
cylinder's tuned default of 25 (the radial grading coarsens the far
field on its own, so the fine core stays affordable).

Usage: python3 tools/make_cylinder_template.py
"""

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "Outdoor" / "OpenFOAM" / "BoxDomain.ghx"
DST = REPO / "Outdoor" / "OpenFOAM" / "CylinderDomain.ghx"

# Eddy3D plugin identity (Outdoor/CMP/*DomainCMP.cs, manifest lib id).
BOX_COMPONENT_GUID = "6198a575-5278-41e8-99b8-a86c8b08c176"
CYLINDER_COMPONENT_GUID = "65ce60f9-fc22-40a1-b9e8-1d406b0c8777"
EDDY_LIB_GUID = "82b21a65-da8f-433c-93fb-f9814609e1d6"

# Fixed instance GUIDs so regeneration is byte-for-byte reproducible.
CYLINDER_INSTANCE_GUID = "c1d0a1e5-7b3f-4d2a-9c6e-2f8b5a4d9e01"
CYLINDER_INPUT_GUIDS = [f"c1d0a1e5-7b3f-4d2a-9c6e-2f8b5a4d9e{i:02d}" for i in range(10, 20)]
WIND_PANEL_GUID = "b8f3c2d4-5e6a-4f7b-8c9d-0a1b2c3d4e5f"
DOCUMENT_GUID = "7c2e9f14-3a5b-4d68-b1c7-8e4f2a6d0b53"

# GUIDs carried over from BoxDomain.ghx.
BOX_OUTPUT_GUID = "e981a09d-b258-4ab0-a226-d1ead60e6c2a"  # kept: feeds wind case Domain input
CELL_SIZE_PANEL_GUID = "b72a6933-8340-4a80-bd73-556f6cbbbde4"  # panel that fed Cell Size
ABL_WIND_DIR_INPUT_GUID = "8b214393-6eed-4a60-a01d-b9be9871f7b8"

COMPONENT_DESC = (
    "Define a cylindrical simulation domain for Eddy3D. One cylindrical mesh serves "
    "all wind directions; the cylinder side faces switch between inlet and outlet per direction."
)
OUTPUT_DESC = (
    "Cylindrical domain parameters (-1 entries mean auto-sized from the building geometry); "
    "plug into the wind case Domain input."
)

# (Name, NickName, Description, default, persistent item type) per GH_Strings.CylinderDomain.
CYLINDER_INPUTS = [
    ("Core Cell Size", "Cell",
     "Cell size of the inner core blocks in meters. Default: 25.", "25", "number"),
    ("Inner Core Size", "Inner",
     "Half-size of the square inner core in meters. -1 = auto from the building footprint.",
     "-1", "number"),
    ("Outer Radius", "Radius",
     "Outer radius of the cylindrical domain in meters. -1 = auto from the building height.",
     "-1", "number"),
    ("Height", "Height",
     "Height of the cylindrical domain in meters. -1 = auto from the building height.",
     "-1", "number"),
    ("Radial Multiplier", "RadMult",
     "Cell growth factor from the core toward the perimeter. Default: 2.", "2", "number"),
    ("Core Divisions", "Divs",
     "Cells per core block (and per perimeter segment, tangentially). Refines the core "
     "without changing the block layout that Core Cell Size sets; the preview core grid "
     "densifies to match. Default: 1.", "1", "integer"),
    ("Refinement Box Extension", "Refine",
     "Padding of the refinement box around the geometry (m). -1 = auto: 27.5% of the "
     "building footprint.", "-1", "number"),
    ("Radial Grading", "Grade",
     "Far-field cell coarsening across the perimeter ring (outer cell size / inner cell "
     "size). 1 = uniform; &gt;1 keeps fine cells at the buildings but grows the outer "
     "cells. The default 7 coarsens the far field aggressively (far fewer cells downwind); "
     "lower it (1-3) for a gentler, more uniform ring. Default: 7.", "7", "number"),
    ("Core Roundness", "Round",
     "Rounds the O-grid inner core from a square (0) toward a circle (1). Higher values "
     "even out the radial gap to the outer boundary, cutting the corner non-orthogonality "
     "of the square core. 0 keeps the classic square core. 0.65 is the checkMesh-sweep "
     "optimum (lowest max non-orthogonality across mesh resolutions; skewness stays well "
     "within limits). Default: 0.65.", "0.65", "number"),
    ("Vertical Grading", "GradeZ",
     "Vertical cell expansion ratio (top cell size / bottom cell size). 1 = uniform; "
     "&gt;1 keeps fine cells near the ground and coarsens aloft (typical for an ABL). "
     "A checkMesh sweep showed non-orthogonality/skewness are unaffected by this; the "
     "only cost is background aspect ratio. The default 35 strongly refines the "
     "near-ground layer; ease it down if convergence struggles. Default: 35.",
     "35", "number"),
]

WIND_DIRECTIONS = ["0", "45", "90", "135", "180", "225", "270", "315"]


def esc(text: str) -> str:
    """The description strings above already carry &gt; escapes; escape the rest."""
    return text.replace("&", "&amp;").replace("&amp;gt;", "&gt;").replace("<", "&lt;")


def build_cylinder_chunk(object_index: int) -> str:
    """Serialize the Cylinder Domain component in place of the Box Domain object.

    Layout mirrors the Box Domain it replaces: same X band (202..464) and top
    edge (Y 925), grown to 204 px for ten input rows of 20 px each.
    """
    top = 925
    height = len(CYLINDER_INPUTS) * 20 + 4
    pivot_y = top + height / 2

    lines = []
    a = lines.append
    a(f'            <chunk name="Object" index="{object_index}">')
    a('              <items count="3">')
    a(f'                <item name="GUID" type_name="gh_guid" type_code="9">{CYLINDER_COMPONENT_GUID}</item>')
    a(f'                <item name="Lib" type_name="gh_guid" type_code="9">{EDDY_LIB_GUID}</item>')
    a('                <item name="Name" type_name="gh_string" type_code="10">Cylinder Domain</item>')
    a('              </items>')
    a('              <chunks count="1">')
    a('                <chunk name="Container">')
    a('                  <items count="4">')
    a(f'                    <item name="Description" type_name="gh_string" type_code="10">{esc(COMPONENT_DESC)}</item>')
    a(f'                    <item name="InstanceGuid" type_name="gh_guid" type_code="9">{CYLINDER_INSTANCE_GUID}</item>')
    a('                    <item name="Name" type_name="gh_string" type_code="10">Cylinder Domain</item>')
    a('                    <item name="NickName" type_name="gh_string" type_code="10">CylDomain</item>')
    a('                  </items>')
    a(f'                  <chunks count="{2 + len(CYLINDER_INPUTS)}">')
    a('                    <chunk name="Attributes">')
    a('                      <items count="2">')
    a('                        <item name="Bounds" type_name="gh_drawing_rectanglef" type_code="35">')
    a('                          <X>202</X>')
    a(f'                          <Y>{top}</Y>')
    a('                          <W>262</W>')
    a(f'                          <H>{height}</H>')
    a('                        </item>')
    a('                        <item name="Pivot" type_name="gh_drawing_pointf" type_code="31">')
    a('                          <X>347</X>')
    a(f'                          <Y>{pivot_y:g}</Y>')
    a('                        </item>')
    a('                      </items>')
    a('                    </chunk>')

    for i, (name, nick, desc, default, kind) in enumerate(CYLINDER_INPUTS):
        row_top = top + 2 + i * 20
        wired = i == 0  # Core Cell Size keeps the panel that fed Box Domain's Cell Size
        a(f'                    <chunk name="param_input" index="{i}">')
        a(f'                      <items count="{7 if wired else 6}">')
        a(f'                        <item name="Description" type_name="gh_string" type_code="10">{esc(desc)}</item>')
        a(f'                        <item name="InstanceGuid" type_name="gh_guid" type_code="9">{CYLINDER_INPUT_GUIDS[i]}</item>')
        a(f'                        <item name="Name" type_name="gh_string" type_code="10">{name}</item>')
        a(f'                        <item name="NickName" type_name="gh_string" type_code="10">{nick}</item>')
        a('                        <item name="Optional" type_name="gh_bool" type_code="1">true</item>')
        if wired:
            a(f'                        <item name="Source" index="0" type_name="gh_guid" type_code="9">{CELL_SIZE_PANEL_GUID}</item>')
        a(f'                        <item name="SourceCount" type_name="gh_int32" type_code="3">{1 if wired else 0}</item>')
        a('                      </items>')
        a('                      <chunks count="2">')
        a('                        <chunk name="Attributes">')
        a('                          <items count="2">')
        a('                            <item name="Bounds" type_name="gh_drawing_rectanglef" type_code="35">')
        a('                              <X>204</X>')
        a(f'                              <Y>{row_top}</Y>')
        a('                              <W>128</W>')
        a('                              <H>20</H>')
        a('                            </item>')
        a('                            <item name="Pivot" type_name="gh_drawing_pointf" type_code="31">')
        a('                              <X>269.5</X>')
        a(f'                              <Y>{row_top + 10}</Y>')
        a('                            </item>')
        a('                          </items>')
        a('                        </chunk>')
        a('                        <chunk name="PersistentData">')
        a('                          <items count="1">')
        a('                            <item name="Count" type_name="gh_int32" type_code="3">1</item>')
        a('                          </items>')
        a('                          <chunks count="1">')
        a('                            <chunk name="Branch" index="0">')
        a('                              <items count="2">')
        a('                                <item name="Count" type_name="gh_int32" type_code="3">1</item>')
        a('                                <item name="Path" type_name="gh_string" type_code="10">{0}</item>')
        a('                              </items>')
        a('                              <chunks count="1">')
        a('                                <chunk name="Item" index="0">')
        a('                                  <items count="1">')
        if kind == "integer":
            a(f'                                    <item name="integer" type_name="gh_int32" type_code="3">{default}</item>')
        else:
            a(f'                                    <item name="number" type_name="gh_double" type_code="6">{default}</item>')
        a('                                  </items>')
        a('                                </chunk>')
        a('                              </chunks>')
        a('                            </chunk>')
        a('                          </chunks>')
        a('                        </chunk>')
        a('                      </chunks>')
        a('                    </chunk>')

    a('                    <chunk name="param_output" index="0">')
    a('                      <items count="6">')
    a(f'                        <item name="Description" type_name="gh_string" type_code="10">{esc(OUTPUT_DESC)}</item>')
    a(f'                        <item name="InstanceGuid" type_name="gh_guid" type_code="9">{BOX_OUTPUT_GUID}</item>')
    a('                        <item name="Name" type_name="gh_string" type_code="10">Domain Parameters</item>')
    a('                        <item name="NickName" type_name="gh_string" type_code="10">Domain</item>')
    a('                        <item name="Optional" type_name="gh_bool" type_code="1">false</item>')
    a('                        <item name="SourceCount" type_name="gh_int32" type_code="3">0</item>')
    a('                      </items>')
    a('                      <chunks count="1">')
    a('                        <chunk name="Attributes">')
    a('                          <items count="2">')
    a('                            <item name="Bounds" type_name="gh_drawing_rectanglef" type_code="35">')
    a('                              <X>362</X>')
    a(f'                              <Y>{top + 2}</Y>')
    a('                              <W>100</W>')
    a(f'                              <H>{height - 4}</H>')
    a('                            </item>')
    a('                            <item name="Pivot" type_name="gh_drawing_pointf" type_code="31">')
    a('                              <X>412</X>')
    a(f'                              <Y>{pivot_y:g}</Y>')
    a('                            </item>')
    a('                          </items>')
    a('                        </chunk>')
    a('                      </chunks>')
    a('                    </chunk>')
    a('                  </chunks>')
    a('                </chunk>')
    a('              </chunks>')
    a('            </chunk>')
    return "\n".join(lines) + "\n"


def build_wind_panel_chunk(index: int) -> str:
    """A yellow panel with the eight directions, left of the ABL component."""
    text = "\n".join(WIND_DIRECTIONS)
    lines = []
    a = lines.append
    a(f'            <chunk name="Object" index="{index}">')
    a('              <items count="2">')
    a('                <item name="GUID" type_name="gh_guid" type_code="9">59e0b89a-e487-49f8-bab8-b5bab16be14c</item>')
    a('                <item name="Name" type_name="gh_string" type_code="10">Panel</item>')
    a('              </items>')
    a('              <chunks count="1">')
    a('                <chunk name="Container">')
    a('                  <items count="8">')
    a('                    <item name="Description" type_name="gh_string" type_code="10">A panel for custom notes and text values</item>')
    a(f'                    <item name="InstanceGuid" type_name="gh_guid" type_code="9">{WIND_PANEL_GUID}</item>')
    a('                    <item name="Name" type_name="gh_string" type_code="10">Panel</item>')
    a('                    <item name="NickName" type_name="gh_string" type_code="10">Wind Directions</item>')
    a('                    <item name="Optional" type_name="gh_bool" type_code="1">false</item>')
    a('                    <item name="ScrollRatio" type_name="gh_double" type_code="6">0</item>')
    a('                    <item name="SourceCount" type_name="gh_int32" type_code="3">0</item>')
    a(f'                    <item name="UserText" type_name="gh_string" type_code="10">{text}</item>')
    a('                  </items>')
    a('                  <chunks count="2">')
    a('                    <chunk name="Attributes">')
    a('                      <items count="5">')
    a('                        <item name="Bounds" type_name="gh_drawing_rectanglef" type_code="35">')
    a('                          <X>170</X>')
    a('                          <Y>615</Y>')
    a('                          <W>62</W>')
    a('                          <H>110</H>')
    a('                        </item>')
    a('                        <item name="MarginLeft" type_name="gh_int32" type_code="3">0</item>')
    a('                        <item name="MarginRight" type_name="gh_int32" type_code="3">0</item>')
    a('                        <item name="MarginTop" type_name="gh_int32" type_code="3">0</item>')
    a('                        <item name="Pivot" type_name="gh_drawing_pointf" type_code="31">')
    a('                          <X>170</X>')
    a('                          <Y>615</Y>')
    a('                        </item>')
    a('                      </items>')
    a('                    </chunk>')
    a('                    <chunk name="PanelProperties">')
    a('                      <items count="7">')
    a('                        <item name="Colour" type_name="gh_drawing_color" type_code="36">')
    a('                          <ARGB>255;255;250;90</ARGB>')
    a('                        </item>')
    a('                        <item name="DrawIndices" type_name="gh_bool" type_code="1">true</item>')
    a('                        <item name="DrawPaths" type_name="gh_bool" type_code="1">true</item>')
    a('                        <item name="Multiline" type_name="gh_bool" type_code="1">true</item>')
    a('                        <item name="SpecialCodes" type_name="gh_bool" type_code="1">false</item>')
    a('                        <item name="Stream" type_name="gh_bool" type_code="1">false</item>')
    a('                        <item name="Wrap" type_name="gh_bool" type_code="1">true</item>')
    a('                      </items>')
    a('                    </chunk>')
    a('                  </chunks>')
    a('                </chunk>')
    a('              </chunks>')
    a('            </chunk>')
    return "\n".join(lines) + "\n"


def replace_once(text: str, old: str, new: str, what: str) -> str:
    count = text.count(old)
    if count != 1:
        sys.exit(f"error: expected exactly one occurrence of {what}, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = SRC.read_text(encoding="utf-8-sig")

    # 1. Swap the Box Domain object for the Cylinder Domain. Located by the Box Domain
    #    component GUID rather than a fixed object index — Grasshopper re-saves reorder
    #    the object list.
    guid_at = text.find(f'<item name="GUID" type_name="gh_guid" type_code="9">{BOX_COMPONENT_GUID}</item>')
    if guid_at < 0:
        sys.exit("error: Box Domain component GUID not found")
    start = text.rfind('<chunk name="Object" index="', 0, guid_at)
    start = text.rfind("\n", 0, start) + 1
    box_index = int(re.search(r'index="(\d+)"', text[start:guid_at]).group(1))
    end = text.find('<chunk name="Object" index="', guid_at)
    if end < 0:
        sys.exit("error: Box Domain must not be the last object")
    end = text.rfind("\n", 0, end) + 1
    text = text[:start] + build_cylinder_chunk(box_index) + text[end:]

    # 2. Reset the Core Cell Size feeder panel from 100 to the cylinder default 25.
    anchor = text.find(
        f'<item name="InstanceGuid" type_name="gh_guid" type_code="9">{CELL_SIZE_PANEL_GUID}</item>')
    if anchor < 0:
        sys.exit("error: cell size panel not found")
    old_item = '<item name="UserText" type_name="gh_string" type_code="10">100</item>'
    window = text[anchor:anchor + 2000]
    if window.count(old_item) != 1:
        sys.exit("error: cell size panel UserText not found where expected")
    text = text[:anchor] + window.replace(
        old_item,
        '<item name="UserText" type_name="gh_string" type_code="10">25</item>',
        1) + text[anchor + 2000:]

    # 3. Append the wind directions panel as a new object and bump the counts (both read
    #    from the file — the object count differs between template generations).
    m = re.search(r'<item name="ObjectCount" type_name="gh_int32" type_code="3">(\d+)</item>', text)
    if not m:
        sys.exit("error: ObjectCount item not found")
    count = int(m.group(1))
    text = replace_once(text, m.group(0),
                        m.group(0).replace(f">{count}<", f">{count + 1}<"), "ObjectCount item")
    chunks_at = text.find(f'<chunks count="{count}">', text.find('name="DefinitionObjects"'))
    if chunks_at < 0:
        sys.exit("error: DefinitionObjects chunks count not found")
    text = text[:chunks_at] + f'<chunks count="{count + 1}">' + text[chunks_at + len(f'<chunks count="{count}">'):]
    last_obj = text.rfind('<chunk name="Object" index="')
    closer = text.find('\n          </chunks>', last_obj)
    if closer < 0:
        sys.exit("error: DefinitionObjects closing tag not found")
    text = text[:closer + 1] + build_wind_panel_chunk(count) + text[closer + 1:]

    # 4. Wire the panel into the ABL component's Wind Directions input.
    abl = text.find(ABL_WIND_DIR_INPUT_GUID)
    if abl < 0:
        sys.exit("error: ABL Wind Directions input not found")
    items_open = text.rfind('<items count="7">', 0, abl)
    if items_open < 0:
        sys.exit("error: ABL Wind Directions items block not found")
    text = text[:items_open] + '<items count="8">' + text[items_open + len('<items count="7">'):]
    src_marker = '<item name="SourceCount" type_name="gh_int32" type_code="3">0</item>'
    src_at = text.find(src_marker, abl)
    if src_at < 0 or src_at - abl > 1500:
        sys.exit("error: ABL Wind Directions SourceCount not found where expected")
    replacement = (
        f'<item name="Source" index="0" type_name="gh_guid" type_code="9">{WIND_PANEL_GUID}</item>\n'
        '                        <item name="SourceCount" type_name="gh_int32" type_code="3">1</item>'
    )
    text = text[:src_at] + replacement + text[src_at + len(src_marker):]

    # 5. Fresh document identity (whatever DocumentID the source file carries).
    doc_m = re.search(
        r'(<item name="DocumentID" type_name="gh_guid" type_code="9">)([0-9a-fA-F-]{36})(</item>)', text)
    if not doc_m:
        sys.exit("error: DocumentID not found")
    text = replace_once(text, doc_m.group(0), doc_m.group(1) + DOCUMENT_GUID + doc_m.group(3),
                        "DocumentID")
    text = replace_once(
        text,
        '<item name="Name" type_name="gh_string" type_code="10">BoxDomain.ghx</item>',
        '<item name="Name" type_name="gh_string" type_code="10">CylinderDomain.ghx</item>',
        "definition Name")

    validate(text)
    DST.write_text("\ufeff" + text, encoding="utf-8", newline="\n")
    print(f"wrote {DST} ({DST.stat().st_size} bytes)")


def validate(text: str) -> None:
    root = ET.fromstring(text)

    def check_counts(el: ET.Element, path: str) -> None:
        items = [c for c in el if c.tag == "items"]
        chunks = [c for c in el if c.tag == "chunks"]
        for holder, child_tag in ((items, "item"), (chunks, "chunk")):
            for h in holder:
                declared = int(h.get("count", "-1"))
                actual = len([c for c in h if c.tag == child_tag])
                if declared != actual:
                    sys.exit(f"error: {path}/{h.tag} declares {declared} but has {actual}")
                for c in h:
                    check_counts(c, f"{path}/{h.tag}/{c.tag}[{c.get('name', c.get('index', ''))}]")

    check_counts(root, "Archive")

    instance_guids = [i.text for i in root.iter("item") if i.get("name") == "InstanceGuid"]
    if len(instance_guids) != len(set(instance_guids)):
        dupes = {g for g in instance_guids if instance_guids.count(g) > 1}
        sys.exit(f"error: duplicate InstanceGuids: {dupes}")
    guid_set = set(instance_guids)
    for i in root.iter("item"):
        if i.get("name") == "Source" and i.text not in guid_set:
            sys.exit(f"error: dangling wire source {i.text}")

    objects = [c for c in root.iter("chunk") if c.get("name") == "Object"]
    indices = sorted(int(c.get("index")) for c in objects)
    if indices != list(range(len(objects))):
        sys.exit("error: Object indices are not contiguous")
    print(f"validated: {len(objects)} objects, {len(instance_guids)} instance guids, "
          "counts consistent, wires resolve")


if __name__ == "__main__":
    main()
