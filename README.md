# Eddy3D Templates

This repository stores Grasshopper template files used by Eddy3D.

## What This Repo Is For

- Source of reusable `.gh` / `.ghx` templates for Eddy workflows.
- Consumed by the `Templates` component in Eddy (`SelectTemplate_Component`).
- Used by `TemplateSync.Cli` in the Eddy3D repo to validate/sync component IO labels.

## How Eddy Loads Templates

- Eddy targets this repository (`Eddy3D-Dev/Eddy3D-Templates`).
- By default, Eddy uses the branch matching `EddyVersion.ProductVersion`.
- Template metadata and downloaded files are cached locally under:
  - `%AppData%/Eddy3D/Templates/GitHub` (main repo cache)
  - `%AppData%/Eddy3D/Templates/External/...` (external GitHub sources)
- Selecting a template in the component menu downloads missing files on demand from `raw.githubusercontent.com`.

## Repo Structure

- `Outdoor/` Outdoor-focused templates.
- `Indoor/` Indoor-focused templates.
- `Internal (beta)/` Experimental/internal templates.

## Template Gallery (GitHub Pages)

- `docs/index.html` is a static gallery site served at https://templates.eddy3d.com via GitHub Pages (source: a version branch, `/docs` folder).
- The site lists all `.ghx` files live via the GitHub API - no rebuild needed when templates are added. Templates under `Internal/` are never shown.
- **The site always opens on the highest version branch** (e.g. `1.17.0.827`), beta or stable. GitHub's own default branch is *not* used - it only advances on a stable release. A `?branch=` link (a shared template, the Select Template component) overrides it; nothing is remembered between visits.
- **Keeping that true:** a Pages source is a single fixed branch, so something has to move it. Eddy3D's `template-branch-sync.yml` (in the main Eddy3D repo, run on every beta and stable push) creates the new version branch, lets it deploy to the `github-pages` environment, and points the Pages source at the newest version branch. Nothing to do by hand per release.

### Documenting a template: six labelled fields

Every template carries a description in the SAME structure, shown on its gallery card. It lives *inside the definition* as a Panel nicknamed `Description`, so it travels with the file. Six lines, in this order, each starting with its label:

```
Purpose:  the question the template answers, in one sentence.
Fidelity: Validated | Engineering | Screening | Experimental, then the caveat. "Cite: ..." where a paper applies.
Method:   the model or engine and what it solves.
Result:   what comes out, and where on the canvas to look.
Needs:    the Eddy3D Setup row(s) to install first, or "Nothing to install"; then "Runtime: <band>."
Edit:     what the user replaces to make it their own.
```

- **Fidelity** classes: *Validated* - compared against measured or published data, and must cite it; *Engineering* - a real solver, not validated for this particular site; *Screening* - machine learning, ray casting, analytic or data views; *Experimental* - a workflow still in development.
- **Needs** names the row exactly as the Eddy3D Setup window titles it (its middle dot written as `/`, e.g. `Eddy3D Setup > Comfort study (Radiance / EnergyPlus).`), so a user can find it. Runtime is one band - `seconds`, `minutes`, `about an hour`, `hours`, `overnight` - or two joined by `to`.
- At most 25 words per field (aim for about 20), ASCII only, no markdown. The rules live in `scripts/description_format.py`.

1. Put it in the file with `python scripts/set_description.py --from-json fields.json`, mapping each template path to its six fields (or pass one template and its six lines as text). It checks the structure first and REFUSES a description that breaks it; a valid one is added above the top-left of the canvas, or updates the existing panel, editing the file as text so the diff is the panel and nothing else. Or edit the Panel in Grasshopper.
2. On push, the `extract-descriptions` workflow runs `scripts/extract_descriptions.py`, which parses every panel into `docs/descriptions.json` (read by the gallery from the branch being browsed: Purpose as the lead, Fidelity as a badge, the rest as labelled rows) and **warns** on any template, Internal included, whose description is missing or breaks the structure. `python scripts/extract_descriptions.py --strict` fails on the same findings locally.

## Notes For Contributors

- Keep template file paths and names stable when possible (they appear in component menus).
- Prefer `.ghx` for version-control-friendly diffs.
- If template ports or labels change, run `TemplateSync.Cli` from the Eddy3D repo to check/fix alignment with component definitions.
