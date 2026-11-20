#!/usr/bin/env python3
"""Minimal MCP stdio client, for sessions where the SolidCraft/CADCraft MCP servers are not
loaded as native tools (or to replay a saved design script).

    python3 -I mcpc.py <server command...> -- <calls.json> [--out DIR]

calls.json is a list of {"tool": name, "args": {...}, "save"?: "file.png"}.
  - A first entry {"tool": "__list__"} also returns the server's tool list.
  - "${OUT}" inside the file is replaced by --out (default ~/cad-designs).
  - Image content blocks are written to "save" (or img_N.png) under --out.
Prints one JSON object: {"initialize", "tools"?, "calls": [{tool, args, result}]}.
Server stderr goes to <calls.json>.stderr.
"""
import base64, json, os, subprocess, sys

sep = sys.argv.index("--")
cmd, rest = sys.argv[1:sep], sys.argv[sep + 1:]
calls_path = rest[0]
out_dir = os.path.expanduser(rest[rest.index("--out") + 1] if "--out" in rest else "~/cad-designs")
os.makedirs(out_dir, exist_ok=True)
calls = json.loads(open(calls_path, encoding="utf-8").read().replace("${OUT}", out_dir))

p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=open(calls_path + ".stderr", "w"), text=True, bufsize=1)
_id = 0

def rpc(method, params=None, notify=False):
    global _id
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        _id += 1
        msg["id"] = _id
    p.stdin.write(json.dumps(msg) + "\n"); p.stdin.flush()
    if notify:
        return None
    while True:
        line = p.stdout.readline()
        if not line:
            raise SystemExit("server closed the connection; see " + calls_path + ".stderr")
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("id") == _id:
            return r

init = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "mcpc", "version": "1"}})
rpc("notifications/initialized", notify=True)
out = {"initialize": init.get("result", init)}
if calls and calls[0].get("tool") == "__list__":
    out["tools"] = rpc("tools/list").get("result")
    calls = calls[1:]

results = []
for c in calls:
    r = rpc("tools/call", {"name": c["tool"], "arguments": c.get("args", {})})
    res = r.get("result", r)
    for i, blk in enumerate(res.get("content", []) if isinstance(res, dict) else []):
        if blk.get("type") == "image":
            fn = os.path.join(out_dir, c.get("save", f"img_{len(results)}_{i}.png"))
            open(fn, "wb").write(base64.b64decode(blk["data"]))
            blk["data"] = f"<saved {fn}>"
    results.append({"tool": c["tool"], "args": c.get("args"), "result": res})
out["calls"] = results
json.dump(out, sys.stdout, indent=1); print()
p.stdin.close(); p.wait(timeout=10)
