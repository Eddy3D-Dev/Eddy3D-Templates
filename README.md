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

### Documenting a template: the 100-word description

Every template carries a **100-word description**, shown on its gallery card. It lives *inside the definition* as a Panel nicknamed `Description`, so it travels with the file:

1. Write one plain paragraph of exactly 100 words (ASCII, no markdown). Say what the template does, the component chain, what comes out, and what the user must change or supply.
2. Put it in the file with `python scripts/set_description.py <template.ghx> "text"` (or `--from-json` for several). It adds the panel above the top-left of the canvas, or updates the existing one, editing the file as text so the diff is the panel and nothing else. Or add the Panel by hand in Grasshopper.
3. On push, the `extract-descriptions` workflow runs `scripts/extract_descriptions.py`, which pulls every panel into `docs/descriptions.json` (read by the gallery from the branch being browsed) and **warns** on any gallery template that has no description or is not 100 words (+/- 10). `python scripts/extract_descriptions.py --strict` fails on the same findings locally.

## Notes For Contributors

- Keep template file paths and names stable when possible (they appear in component menus).
- Prefer `.ghx` for version-control-friendly diffs.
- If template ports or labels change, run `TemplateSync.Cli` from the Eddy3D repo to check/fix alignment with component definitions.
