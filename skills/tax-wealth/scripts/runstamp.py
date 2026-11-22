"""Run ids and write-once run files, shared by compute.py and equity_scenarios.py.

A run id names the numbers a draft cites as [run:<id>], so a run file must never change under it.

- `input_sha256` is the sha256 of the canonical inputs, as before.
- The id is `<prefix>-<first 10 hex of sha256({"engine", "engine_version", "inputs"})>`, so a new engine
  version gets a new id instead of reusing one. Run files written under the earlier scheme (engine run
  1: `policyengine-1823e30c0e`, and `equity_scenarios` 0.2.0 such as `equity_scenarios-5e99d9d9c8`) used
  the input hash alone; they stay valid under their existing ids and are never rewritten.
- `write_run` never overwrites a run file whose outputs differ. Rerunning with identical outputs is a
  no-op that leaves the original file (and its `run_at`) alone.
"""

import hashlib
import json
import os
import sys


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def run_id(prefix, engine, engine_version, inputs):
    """Return (id, input_sha256) for a new run."""
    input_digest = canonical_sha256(inputs)
    id_digest = canonical_sha256({"engine": engine, "engine_version": engine_version, "inputs": inputs})
    return "%s-%s" % (prefix, id_digest[:10]), input_digest


def write_run(out_dir, result, text):
    """Write <out_dir>/<id>.json unless it exists. Returns 0 (written or identical) or 2 (refused)."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, result["id"] + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = json.load(f)
        same = (existing.get("engine_version") == result["engine_version"]
                and existing.get("outputs") == json.loads(json.dumps(result["outputs"])))
        if same:
            print("UNCHANGED: %s already holds identical outputs; left as is" % path, file=sys.stderr)
            return 0
        print("REFUSED: %s exists and its engine version or outputs differ; a cited run file is never "
              "overwritten. Investigate the difference instead." % path, file=sys.stderr)
        return 2
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return 0
