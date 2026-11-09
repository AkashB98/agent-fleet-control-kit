#!/usr/bin/env python3
"""End-to-end demo: build the golden scenario in a temp dir, replay it
from scratch, and assert the exact final fleet state."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenario
from fleet import Fleet

EXPECTED = {
    "run-a": ("done", 4), "run-b": ("done", 5), "run-c": ("running", 2),
    "run-d": ("running", 5), "run-e": ("queued", 1),
}

def run():
    with tempfile.TemporaryDirectory() as td:
        log = os.path.join(td, "fleet.jsonl")
        dec = os.path.join(td, "decisions.json")
        scenario.build(log, dec)
        f = Fleet(log)  # full replay, incl. the truncated tail
        state = {rid: (r["status"], r["version"]) for rid, r in f.runs.items()}
        assert state == EXPECTED, f"state mismatch: {state} != {EXPECTED}"
        assert f.truncated_tail == 1, f.truncated_tail
        summary = f.summary(now=scenario.BASE + 1030, threshold_seconds=900)
        assert summary["stale"] == ["run-c"], summary["stale"]
        assert summary["rejected_commands"] == 3, summary
        print("demo: golden scenario replay OK")
        print(json.dumps(summary, indent=2, sort_keys=True))
        print("demo: OK")
        return 0

if __name__ == "__main__":
    sys.exit(run())
