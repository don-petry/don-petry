---
name: cad-design
description: 'Create and edit CAD designs agentically with two open-source, MCP-driven CAD apps: SolidCraft
  (parametric 3D parts and assemblies → STEP/STL/3MF/URDF) and CADCraft (2D AutoCAD-style drafting → DXF/DWG/PDF/SVG).
  Use for any request to model, draw, draft, dimension, export or 3D-print a part, bracket, plate, enclosure,
  case, mount, adapter, jig, floor plan, shop drawing or fabrication drawing — ''design a bracket'', ''model
  this in CAD'', ''make a STEP file'', ''STL for the printer'', ''draw a plan'', ''DXF for the laser cutter'',
  ''add a dimension'', ''change the width to 120'' — and for installing, updating or configuring the CAD
  tools themselves.'
license: MIT
metadata:
  argument-hint: '[what to make, with dimensions] | install | check | update'
---

# CAD design — SolidCraft (3D) and CADCraft (2D) over MCP

Two pure-Rust, MIT/Apache-2.0 CAD apps that agents drive through a Model Context Protocol server.
Each exposes a headless CLI, a JSON control channel into its desktop app, and an MCP server; the
MCP tools run the same engine commands the GUI runs, so anything a person can do, an agent can do.
Both are ~2 weeks old (first release 2026-10-07), release daily, and call themselves early.

| | SolidCraft | CADCraft |
| :--- | :--- | :--- |
| Makes | parametric 3D solids, assemblies with joints, sheet metal | 2D drawings: lines, circles, polylines, hatches, blocks, dimensions, layouts |
| Think of it as | Fusion 360 / SolidWorks | AutoCAD |
| Output | STEP AP242, STL, 3MF, OBJ, glTF, IGES, URDF, `.solidcraft` | DXF (R12–2018 read, 2018 write), DWG, PDF, SVG, PNG |
| Upstream | github.com/tangency-labs/solidcraft | github.com/storytold/cadcraft |
| Reference | [reference/solidcraft.md](reference/solidcraft.md) | [reference/cadcraft.md](reference/cadcraft.md) |

## Which tool

Decide by the **deliverable**, not by the words in the request.

| The request needs… | Use | Why |
| :--- | :--- | :--- |
| A physical part: something to 3D-print, machine, or send to a fab as STEP/STL/3MF | **SolidCraft** | Only it makes solids. |
| A part whose dimensions may change later ("make the width a parameter") | **SolidCraft** | Named parameters drive sketches and features; `set_parameter` rebuilds everything. |
| An assembly, mechanism, or robot description (URDF) | **SolidCraft** | Joints, motion studies, URDF export. |
| A 2D drawing: floor plan, site plan, shop drawing, laser/plasma/CNC-router profile (DXF), anything with title blocks, layers, hatches and annotation | **CADCraft** | Only it writes DXF/DWG with layers, dims and plot layouts. |
| A dimensioned drawing *of* a 3D part | **SolidCraft** for the solid, then **CADCraft** for the sheet | SolidCraft's 2D drawings are deferred on its roadmap; it can only dump the current view (`File → Export Current View as DXF`). Redraw the views in CADCraft from the same numbers (see `examples/plate_cadcraft.json`). |
| Editing a DXF/DWG someone sent | **CADCraft** | `open {path}` then `query_entities`. Entities it does not model yet are dropped on save; say so. |
| Editing a STEP someone sent | **SolidCraft** | `open {path}` imports bodies as a base feature. Assemblies flatten to single bodies. |
| 3D in CADCraft, or drawing sheets in SolidCraft | neither, yet | CADCraft 3D is at 2% parity; SolidCraft drawings are deferred. Say so instead of improvising. |

## Setup (once per Mac)

Run from the skill folder:

```bash
scripts/install.sh            # pinned versions; idempotent
scripts/install.sh --check    # what is installed and whether MCP is registered
scripts/install.sh --latest   # upgrade both to the newest GitHub release
```

The installer downloads the official `*-cli-<ver>-macos-universal.zip` release assets with `gh`,
unpacks them to `~/.local/share/cad-design/<tool>-<ver>/`, symlinks `solidcraft-cli` and
`cadcraft-cli` into `~/.local/bin/`, and strips the quarantine flag (the releases are unsigned).
It then registers both MCP servers with the harness: automatically for Claude Code (user scope)
when its CLI is on PATH, and by printing paste-ready JSON and TOML definitions for every other
MCP-capable harness (Codex, Gemini CLI, Cursor, VS Code/Copilot). The servers are:

```
solidcraft: ~/.local/bin/solidcraft-cli mcp --allow-path ~/cad-designs
cadcraft:   ~/.local/bin/cadcraft-cli mcp
```

- **`~/cad-designs/` is the only folder SolidCraft may read or write over MCP.** That is its own
  sandbox (`--allow-path`); a path outside it is refused with a clear error. Put every export there.
  CADCraft has no such limit, but use the same folder.
- No Rust toolchain is needed; nothing is built from source. There is no Linux or Windows path in
  the installer yet, though both projects ship those assets.
- The desktop apps are optional. To watch an agent model, install the `.dmg`, start it with
  `solidcraft --control 7878` (or `cadcraft --control 7979`) and run the MCP server with
  `--connect 127.0.0.1:7878`. Headless is the default.
- Verified 2026-10-20 with SolidCraft 0.17.0 and CADCraft 0.8.0 (the pinned versions).

## Reaching the tools from a session

1. **Native MCP tools** (preferred). Once the servers are registered, the harness exposes the
   `solidcraft` and `cadcraft` servers' tools (`batch`, `execute`, `measure`, `list_commands`, …).
   Some harnesses load MCP tools lazily; search for or load them before the first call.
2. **The stdio client** (`scripts/mcpc.py`), when the servers are not registered (a cloud
   session, another machine, or a harness without MCP). It speaks MCP over stdin/stdout and takes a
   JSON list of tool calls, so a saved design script replays exactly:

   ```bash
   python3 -I scripts/mcpc.py ~/.local/bin/solidcraft-cli mcp --allow-path ~/cad-designs -- design.json --out ~/cad-designs
   python3 -I scripts/mcpc.py ~/.local/bin/cadcraft-cli mcp -- drawing.json --out ~/cad-designs
   ```

   `${OUT}` inside the JSON becomes `--out`; image results are saved there as PNG.

Either way, the **command script is the design**: a JSON list of tool calls that rebuilds the part
from nothing. Keep it; the binary outputs are disposable.

## Workflow

1. **Numbers first.** Write the parameters, the placement (center the part on the origin so
   patterns and mirrors work from the planes), every feature with the world point you will pick
   its edge or face by, and the expected volume, bounding box and face count. Compute these
   yourself before the first call. A request without dimensions gets one question to the user,
   not a guess.
2. **Build in stages** (SolidCraft: one `batch` per stage — base sketch + first feature; fillets
   and shell; holes, cuts and patterns. CADCraft: one `execute` per entity, layers first).
3. **Verify numerically after every stage.** SolidCraft `measure {}` must match your volume to
   ~0.01% and your face count exactly; a cut that leaves the volume unchanged missed, even though
   it reported success. CADCraft `inspect_drawing {}` counts and `query_entities` centers/radii
   must match your plan. Only then take a picture.
4. **Prove the parameters** (SolidCraft): `set_parameter` one value, expect `errors: []`, check
   `measure` moved by the amount you computed, set it back.
5. **Export** to `~/cad-designs/<name>.<ext>`: STEP for CAD exchange, STL/3MF for printing, URDF
   for simulators, `.solidcraft` to keep the timeline; DXF for cutters and other CAD, PDF for
   people. Show the user the render PNG and hand over the files.
6. **Keep the source.** Save the final call list as `designs/<name>.json` in the skill folder
   (text, small, reproducible). Keep large or binary outputs out of git; store them in cloud
   storage and link them from wherever the project is tracked.

## Best practices that cost us time

- **Read the reference file before the first call**, not the command catalog. Unfiltered
  `list_commands` is over 100 KB in SolidCraft. Filter on a distinctive word (`"hole"`, `"slot"`).
- **Docs on `main` are ahead of the release you have.** CADCraft's `shapes` command is documented
  but absent in 0.8.0. When a documented command errors as unknown, check
  `list_commands {filter}` and move on; do not retry.
- **Picks snap to the nearest edge or face with no distance limit and no error.** Compute the exact
  midpoint (the vertical corner edge of a centered box is `[w/2, d/2, h/2]`) and confirm by face
  count.
- **A batch is all-or-nothing.** Put a risky step (booleans between touching curved faces, anything
  new) in a batch of its own, so a failure does not roll back the work around it.
- **Expressions, not numbers, wherever a position must follow a parameter.** `"L/2 - inset"` moves
  with `L`; `30` never will. Edge and face picks are the exception: plain numbers only.
- **CADCraft linetypes must be loaded before a layer can use them**, one per call:
  `execute linetype {load:"HIDDEN"}`, then `{load:"CENTER"}`. A comma-separated list only works
  with a `.lin` file. CADCraft has no batch and no rollback: on an error mid-drawing, inspect and
  continue; do not start over.
- **Reply size.** Pass `"verbose": false` to SolidCraft `batch`/`execute` in large designs.
  `body_topology` is 25–45 KB; use `measure` first. `inspect_design {"measure":false,"sketches":false}`
  is the cheap timeline-health check.
- **Boolean warnings** such as `Boolean retry: temporary coincident-face separation` are harmless
  when the measured volume still matches your number, and a defect when it does not.
- **Nothing here replaces a checked drawing.** Both projects say so. A part for a customer or a
  structural drawing for a permit is reviewed by a human in real CAD before it leaves the house.

## Scheduled runs

None. A design job is interactive by nature (it needs dimensions). A cloud or CI job cannot use
these tools unless its container installs them; the installer is macOS-only today.

## Files

```
cad-design/
├── SKILL.md
├── scripts/install.sh        install / --check / --latest; registers or prints the MCP servers
├── scripts/mcpc.py           stdio MCP client; replays a call list
├── reference/solidcraft.md   tools, command shapes, planes, ids, traps
├── reference/cadcraft.md     tools, command shapes, layers, dims, traps
├── examples/plate_solidcraft.json   verified 2026-10-20: 80×50×6 plate, boss, 4 holes, parametric
├── examples/plate_cadcraft.json     the same plate as a dimensioned 2-view drawing
└── designs/                  saved call lists for real designs (one JSON per design)
```
