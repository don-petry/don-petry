# CADCraft over MCP — reference (0.8.0, 2026-10-20)

Server: `cadcraft-cli mcp [--connect HOST:PORT [--lazy] [--launch]]`. Drawing units are whatever
the drawing says; `new_drawing {metric:true}` gives millimeters. World coordinates, Z = 0.
Full docs: `docs/mcp.md`, `docs/control-protocol.md` in the upstream repo — **written against
`main`, which is ahead of the release**: `shapes` is documented and absent in 0.8.0.

## Tools

| Tool | Args | Use |
| :--- | :--- | :--- |
| `command_line` | `text` | Type like a drafter: `rectang -40,-25 40,25`, `line 0,-30 0,30 ` (a trailing space is Enter), `zoom e`. Returns prompt, keywords and output. Use for geometry you would type anyway. |
| `script` | `text` | A multi-line `.scr`. |
| `execute` | `command, params` | Any command with JSON params, never a dialog. Use for anything with options (layers, dims, text, fillet radius). |
| `list_commands` | `filter?` | Catalog with `params` strings and aliases. |
| `inspect_drawing` | `entities?, limit?` | Counts by type, extents, layers, styles, blocks, layouts, selection, undo, entities. The verification call. |
| `query_entities` | `type?, layer?, selected?, window?, crossing?, limit?, offset?` | Entities with handles and geometry (centers, radii, vertices). |
| `find_text` | `contains?, layer?, window?` | Readable TEXT/MTEXT/attributes. |
| `render` | `width?, height?, fit?, window?` | PNG of model space. 1600×1200 reads well. |
| `new_drawing` / `open` / `save` / `cancel` | `metric?` / `path` / `path?` | `save` to `.dxf`/`.dwg` saves; to `.svg`/`.png`/`.pdf` exports and the drawing keeps its name. |
| `screenshot`, `ui_inspect`, `ui_click` | | Only when `--connect`ed to the app. |

**No batch, no rollback.** Each call is one round trip and one undo step. A failed call changes
nothing; later calls still run, so an error early in a sequence (a layer that was never created)
silently puts later geometry on the wrong layer. Check `inspect_drawing` layers and counts at the end.

## Command shapes (from `list_commands`)

```json
{"command":"layer.new","params":{"name":"OUTLINE","color":7,"lineweight":0.5}}
{"command":"linetype","params":{"load":"HIDDEN"}}         // one name per call unless `file` is given
{"command":"layer.new","params":{"name":"HIDDEN","color":3,"linetype":"HIDDEN"}}
{"command":"layer.current","params":{"name":"OUTLINE"}}
{"command":"ltscale","params":{"scale":0.5}}
{"command":"rectang","params":{"p1":[-40,-25],"p2":[40,25],"fillet":6}}     // also chamfer:[d1,d2], rotation, width
{"command":"circle","params":{"center":[0,0],"diameter":24}}               // or radius; circle.2p, circle.3p, circle.ttr
{"command":"line","params":{"points":[[0,0],[10,0]]}}
{"command":"fillet","params":{"h1":"1A","p1":[..],"h2":"1B","p2":[..],"radius":5}}  // or {handle, polyline:true, radius}
{"command":"hatch","params":{"points":[[5,5]],"pattern":"ANSI31","scale":1,"angle":0}}
{"command":"arrayrect","params":{"handles":["2F"],"rows":2,"cols":2,"rowSpacing":30,"colSpacing":60}}
{"command":"arraypolar","params":{"handles":["2F"],"center":[0,0],"count":6}}
{"command":"dimlinear","params":{"p1":[-40,25],"p2":[40,25],"at":[0,36]}}   // horizontal/vertical from `at`; rotation? text?
{"command":"dimaligned","params":{"p1":[..],"p2":[..],"at":[..]}}
{"command":"dimdiameter","params":{"center":[0,0],"point":[8.485,8.485]}}  // or {handle, at?}; dimradius likewise
{"command":"dimangular","params":{"vertex":[..],"p1":[..],"p2":[..],"at":[..]}}
{"command":"qdim","params":{"handles":[..],"at":[0,40],"mode":"continuous"}}
{"command":"text","params":{"at":[-40,-72],"text":"MOUNTING PLATE","height":3,"justify":"L"}}
{"command":"mtext","params":{"at":[..],"text":"...","height":2.5,"width":60}}
{"command":"block","params":{...}}  {"command":"insert","params":{...}}     // see list_commands {filter:"block"}
```

Handles (`"2F"`) come from `query_entities` or the `created` of the call that drew the entity.

## A drawing, in order

1. `new_drawing {metric:true}`.
2. Linetypes (`linetype {load}` one at a time), then layers (`layer.new`), then `layer.current`.
   Conventional set: `OUTLINE` (7, 0.5 mm), `HIDDEN` (3, HIDDEN), `CENTER` (2, CENTER), `HOLES` (1),
   `DIM` (4), `TEXT`.
3. Geometry per layer, switching with `layer.current`.
4. Dimensions on `DIM`: overall first, then feature pitches, then diameters. Place `at` ≥ 8 units
   off the geometry; stagger stacked dims by ~5–7 units.
5. A title line with `text`.
6. `command_line "zoom e"`, `inspect_drawing {}` (counts, layers), `query_entities {type:"circle"}`
   (centers and radii against the plan), `render {}`.
7. `save ~/cad-designs/<name>.dxf`, then `.pdf` (people) and `.svg` if asked.

## Errors seen

| Text | Fix |
| :--- | :--- |
| `linetype `HIDDEN` is not loaded (load it with LINETYPE)` | `execute linetype {load:"HIDDEN"}` first. |
| `linetype `HIDDEN,CENTER` not found in the library` | One name per `load` call. |
| `no layer `CENTER`` | The `layer.new` before it failed; re-run it. |
| `unknown command `shapes`` | Documented on `main`, not in 0.8.0. Use `query_entities` and compute. |

## What it cannot do yet (roadmap, 2026-10-14)

Pre-alpha, ≈38% "ready for real work". No 3D (2%). No object-snap tracking, stubbed TRIM/EXTEND/
OFFSET options, no block editor, plot styles ignored, SHX fonts not read. DWG: read via `acadrust`,
write R2000, **never verified in AutoCAD**; entities CADCraft does not model are dropped on save,
so a round trip through someone else's DWG loses things. Prefer DXF for exchange.
