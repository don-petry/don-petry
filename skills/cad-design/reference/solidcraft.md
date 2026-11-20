# SolidCraft over MCP — reference (0.17.0, 2026-10-20)

Server: `solidcraft-cli mcp [--allow-path DIR]... [--connect HOST:PORT] [--param-check warn|strict] [--in design.solidcraft]`.
Lengths in mm, angles in degrees, right-handed Z-up. Any numeric field takes an expression over the
design's parameters (`"w/2 - wall"`, `"30 deg"`, `"1 in"`). Full docs: `docs/mcp.md`,
`skills/solidcraft-modeling/reference.md` in the upstream repo (the shipped Agent Skills are good).

## Tools

| Tool | Args | Use |
| :--- | :--- | :--- |
| `list_commands` | `filter?` | Catalog. **Always filter**; unfiltered is >100 KB. |
| `describe_command` | `id` | Param docs + JSON Schema for `solid.box`, `solid.extrude`, `engine.describe`. |
| `execute` | `command, params?, verbose?` | One engine command. Failure leaves the design unchanged. |
| `batch` | `commands:[{command,params}], rollback?=true, verbose?, timings?, profile?` | Stages. Stops at first error and rolls back; reply has `failed.index/command/error`. |
| `inspect_design` | `measure?, sketches?, joints?` | Parameters, timeline (each feature's `error`/`warning`), bodies, sketches. `{"measure":false,"sketches":false}` ≈ 4 KB. |
| `measure` | `body?` or `items?` | Volume mm³, area, center of mass, bbox, face/edge/vertex counts; ≈1 KB. With `items` (faces/edges/curves): distances, diameters, angles. |
| `body_topology` | `body` | Every edge midpoint and face name/centroid/normal. 25–45 KB; last resort. |
| `set_parameter` | `name, value\|expression, unit?` | Change a parameter and recompute; reports `recomputed`, `restored`, `errors`. |
| `screenshot` | `view?: iso\|top\|front\|…, camera?, path?, width?, height?, source?: model\|window, grid?, axes?` | PNG. Headless renders on the GPU. Use `source:"model"`, 800×560 is plenty. |
| `export` | `path, format?: step\|3mf\|stl\|stla\|obj\|urdf, bodies?` | Writes under an allowed folder only. |
| `open` / `save` / `new_design` | `path` / `path?` / `name?` | `.solidcraft`, STEP (`.step/.stp` → Import base feature), 3MF/STL as mesh bodies. `new_design` discards unsaved work. |
| `undo` / `redo` / `crash_reports` | | |

Resources: `solidcraft://design`, `solidcraft://commands`. Engine failures come back as
`isError: true` with the message; schema failures as JSON-RPC -32602.

## Sketch planes

| `plane` | sketch x | sketch y | normal |
| :--- | :--- | :--- | :--- |
| `"XY"` | +X | +Y | +Z |
| `"XZ"` | +X | **−Z** | +Y |
| `"YZ"` | +Y | +Z | +X |
| `{origin, x_dir, y_dir}` | x_dir | y_dir | x_dir × y_dir |

`sketch.create {plane, offset?: "T", name?, flip?}`; `offset` follows parameters. Top face of a
part of height h: `{"plane":"XY","offset":"h"}`. `solid.hole {sketch}` drills from the sketch
plane along −normal, so hole sketches go on the top face.

## Ids inside a sketch

Each sketch counts per kind from 1: curves `l1`, `c1`, `a1`; points `p1`, `l1.start`, `c1.center`,
`"origin"`. Creators return `created: {points, curves, constraints, dimensions}`.
`sketch.rectangle.center` makes `l1`–`l6` (two construction diagonals) and `p1`–`p5` (center is
`p5`); its corners join 3 lines, so use `solid.fillet` in 3D rather than `sketch.fillet`.
`sketch.circle.center` makes `c1` and `c1.center`, no `p`. Dimensions and constraints share the `k`
counter. Ids are predictable, so later steps in the same batch can use them.

## Commands a part needs

```json
{"command":"parameters.add","params":{"name":"L","expression":"80 mm"}}
{"command":"sketch.create","params":{"plane":"XY","name":"PlateSketch"}}
{"command":"sketch.draw.dimensioned","params":{"command":"sketch.rectangle.center","params":{"center":[0,0],"corner":[40,25]},"dimensions":{"width":"L","height":"W"}}}
{"command":"sketch.circle.center","params":{"center":[0,0],"radius":12}}
{"command":"sketch.dimension","params":{"entities":["c1"],"type":"diameter","value":"boss_d"}}
{"command":"sketch.point","params":{"point":[30,15]}}
{"command":"sketch.dimension","params":{"entities":["origin","p1"],"type":"horizontal","value":"L/2 - inset"}}
{"command":"sketch.finish","params":{}}
{"command":"solid.extrude","params":{"distance":"T","name":"Plate"}}
{"command":"solid.extrude","params":{"distance":"boss_h","sketch":"BossSketch","profiles":[{"point":[8.5,0]}],"operation":"join","name":"Boss"}}
{"command":"solid.extrude","params":{"distance":"T + 2","sketch":"BossSketch","profiles":[{"point":[0,0]}],"direction":"negative","operation":"cut","name":"Bore"}}
{"command":"solid.fillet","params":{"edges":[[40,25,3],[-40,25,3],[40,-25,3],[-40,-25,3]],"radius":6,"name":"Corners"}}
{"command":"solid.hole","params":{"sketch":"HolePts","diameter":4.5,"name":"Hole"}}
{"command":"solid.pattern.rectangular","params":{"features":["Hole"],"dir1":[-1,0,0],"count1":2,"spacing1":"L - 2*inset","dir2":[0,-1,0],"count2":2,"spacing2":"W - 2*inset","name":"Holes"}}
{"command":"solid.box","params":{"length":"L","width":"W","height":"T","center":[0,0,"T/2"],"operation":"new","body_name":"Base"}}
{"command":"solid.cylinder","params":{"diameter":6.6,"height":"T + 2","base":["bcd/2",0,-1],"operation":"cut","name":"BoltHole"}}
{"command":"solid.pattern.circular","params":{"features":["BoltHole"],"axis":"Z","count":"n"}}
{"command":"solid.shell","params":{"faces":[[0,0,"h"]],"thickness":2}}
{"command":"solid.mirror","params":{"features":["Boss"],"plane":"YZ"}}
{"command":"timeline.edit","params":{"feature":"Plate","set":{"extent":{"distance":"30"}}}}
```

- `solid.extrude` takes **every region** by default; for a boss with a bore, pick the ring with
  `profiles:[{"point":[x,y]}]` (two concentric circles, extrude the ring) — that builds correctly
  where a cylinder join plus a cylinder cut has left material behind.
- `solid.hole`: `clearance:"M3"`, `type: simple|drilled|counterbore|countersink` (`cb_diameter`,
  `cb_depth` / `cs_diameter`, `cs_angle`), `depth` defaults to through all.
- Fillet first, then shell; except the rim of the face the shell removes, which is rounded after.
- A mirror or pattern feature cannot be patterned or mirrored again; pattern the original.
- Primitive booleans that touch curved faces can fail with `planar faces only`; use a sketch
  profile and an extrude cut instead.
- Name every feature and keep names unique across sketches and features.

## Verification numbers (the plate example)

Plate 80×50×6, R6 corners, boss Ø24×14, bore Ø10, 4× Ø4.5 at 60×30:
plate 24,000 − 4·(36 − 9π)·6 = 23,814.46; + boss π·144·14 = 6,333.45; − bore π·25·20 = 1,570.80;
− holes 4·π·2.25²·6 = 381.70 → **28,195.4 mm³, 17 faces**. Measured 28,195.50. After `L=120`:
+12,000 → 40,195.5. Measured 40,195.50.

## Errors seen

| Text | Fix |
| :--- | :--- |
| `… no sketch is being edited` | `sketch.create` or `sketch.edit` first. |
| `unknown sketch entity 'p1'` | Use the ids from `created`; a circle's center is `c1.center`. |
| `the corner must join exactly two lines` | A `rectangle.center` corner: fillet in 3D. |
| `an edge is a point [x,y,z]…` | Picks must be plain numbers, not expressions. |
| `<Feature> cannot be patterned or mirrored yet` | Pattern the original feature. |
| `path … is outside the allowed folders` | Write under `~/cad-designs` (the `--allow-path`). |
| `Boolean retry: temporary coincident-face separation …` | A warning. Fine if `measure` matches; otherwise rebuild the feature as a single profile. |

## What it cannot do yet (roadmap, 2026-10-14)

2D drawing sheets (deferred; only "Export Current View as DXF"), surfacing, mesh editing, CAM,
simulation. Some coincident curved booleans still fail. G2 fillets only on straight edges between
planar faces. STEP import flattens assemblies. Downloads are unsigned.
