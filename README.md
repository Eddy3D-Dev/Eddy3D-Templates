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

- `docs/index.html` is a static gallery site served via GitHub Pages (Settings → Pages → deploy from branch, `/docs` folder).
- The site lists all `.ghx` files live via the GitHub API — no rebuild needed when templates are added.
- **Documenting a template:** add a Panel component nicknamed `Description` to the Grasshopper definition. On push, the
  `extract-descriptions` workflow runs `scripts/extract_descriptions.py`, which pulls the panel text into
  `docs/descriptions.json`; the gallery shows it on the template's card.

> **Note:** The gallery only shows a description when the `.ghx` actually contains a Panel nicknamed `Description`.
> There is no fallback text — a template without that panel appears on the site with just its name, path and size.
> This is deliberate: the description lives with the definition, so it stays accurate as the template changes, and no
> one has to maintain a second list of blurbs elsewhere. To describe a template, add the panel and push.

## Notes For Contributors

- Keep template file paths and names stable when possible (they appear in component menus).
- Prefer `.ghx` for version-control-friendly diffs.
- If template ports or labels change, run `TemplateSync.Cli` from the Eddy3D repo to check/fix alignment with component definitions.
