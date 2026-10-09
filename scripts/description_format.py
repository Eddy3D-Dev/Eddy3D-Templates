"""The structure every template description follows, in one place.

A template documents itself with a Panel nicknamed "Description" holding six
labelled lines, always in this order:

    Purpose:  the question the template answers, in one sentence.
    Fidelity: how far to trust the answer. Starts with one of FIDELITY_CLASSES;
              cite the paper where one applies ("Cite: ...").
    Method:   the model or engine and what it solves.
    Result:   what comes out, and where on the canvas to look.
    Needs:    the Eddy3D Setup row(s) to install first, or "Nothing to install",
              then "Runtime: <band>." with a band from RUNTIME_BANDS.
    Edit:     what the user replaces to make it their own.

scripts/set_description.py refuses text that breaks these rules and
scripts/extract_descriptions.py --strict fails on it, so a template cannot drift
back into free prose. The gallery reads the parsed fields from
docs/descriptions.json and lays them out the same way on every card.
"""
import re

FIELDS = ("Purpose", "Fidelity", "Method", "Result", "Needs", "Edit")
MAX_WORDS = 25  # per field; the house target is about 20

FIDELITY_CLASSES = {
    "Validated": "compared against measured or published data, cited",
    "Engineering": "a real solver, not validated for this particular site",
    "Screening": "fast approximation: machine learning, ray casting, analytic or data views",
    "Experimental": "a workflow still in development",
}

# Eddy3D Setup row titles (Provisioning.Engines/Eddy3DSetupCatalog.cs), with the
# middle dot written as "/" because descriptions are ASCII. Naming the row exactly
# is what lets a user find it in the setup window.
SETUP_ROWS = (
    "(U)RANS CFD (OpenFOAM)",
    "Fully-coupled multi-region CFD / HAM / RAD / VEG (urbanMicroclimateFoam)",
    "Comfort study (Radiance / EnergyPlus)",
    "Container runtime (Podman / Docker)",
    "LBM CFD (FluidX3D)",
    "LBM CFD (OpenLB)",
    "Morph weather (Future Weather Generator)",
    "Mesoscale weather / Weather Research and Forecasting (WRF)",
    "Urban microclimate / LES / RANS (PALM-4U)",
)
NOTHING = "Nothing to install"

RUNTIME_BANDS = ("seconds", "minutes", "about an hour", "hours", "overnight")
_BAND = "|".join(re.escape(b) for b in RUNTIME_BANDS)
RUNTIME = re.compile(rf"Runtime: (?:{_BAND})(?: to (?:{_BAND}))?(?:,[^.]*)?\.")

_LINE = re.compile(r"^(?P<label>[A-Z][a-z]+):\s*(?P<text>.*\S)\s*$")


def parse(text: str) -> tuple[dict[str, str], list[str]]:
    """Fields of a panel text, and every way it breaks the structure (empty when valid)."""
    fields: dict[str, str] = {}
    problems: list[str] = []
    seen: list[str] = []
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        if not raw.strip():
            continue
        m = _LINE.match(raw.strip())
        if not m or m.group("label") not in FIELDS:
            problems.append(f"line is not one of the {len(FIELDS)} labelled fields: {raw.strip()[:60]!r}")
            continue
        label = m.group("label")
        if label in fields:
            problems.append(f"{label} appears twice")
            continue
        fields[label] = m.group("text")
        seen.append(label)

    missing = [f for f in FIELDS if f not in fields]
    if missing:
        problems.append("missing " + ", ".join(missing))
    if seen != [f for f in FIELDS if f in seen]:
        problems.append("fields out of order; expected " + ", ".join(FIELDS))
    problems.extend(lint(fields))
    return fields, problems


def lint(fields: dict[str, str]) -> list[str]:
    """Rules on the content of each field."""
    problems = []
    for label, value in fields.items():
        words = len(value.split())
        if words > MAX_WORDS:
            problems.append(f"{label} is {words} words; cap is {MAX_WORDS}")
        if not value.isascii():
            problems.append(f"{label} has non-ASCII characters")

    fidelity = fields.get("Fidelity", "")
    first = re.split(r"[\s.,:;-]+", fidelity.strip(), maxsplit=1)[0] if fidelity else ""
    if fidelity and first not in FIDELITY_CLASSES:
        problems.append(f"Fidelity must start with one of {', '.join(FIDELITY_CLASSES)}; got {first!r}")
    if first == "Validated" and "Cite:" not in fidelity:
        problems.append("Fidelity is Validated but cites nothing (add 'Cite: ...')")

    needs = fields.get("Needs", "")
    if needs:
        if not (needs.startswith(NOTHING) or any(row in needs for row in SETUP_ROWS)):
            problems.append(f"Needs must start with {NOTHING!r} or name an Eddy3D Setup row")
        if not RUNTIME.search(needs):
            problems.append(f"Needs must say 'Runtime: <band>.' with a band from: {', '.join(RUNTIME_BANDS)}")
    return problems


def render(fields: dict[str, str]) -> str:
    """Panel text for a field dict, in the house order."""
    return "\n".join(f"{label}: {fields[label].strip()}" for label in FIELDS if label in fields)
