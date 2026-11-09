#!/usr/bin/env python3
"""Golden evals: pin the exact behaviour of the golden scenario + core
invariants. Writes eval_report.json deterministically."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import demo, scenario
from fleet import Fleet

def main():
    checks = []
    def check(name, ok, detail=None):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})
    with tempfile.TemporaryDirectory() as td:
        log = os.path.join(td, "f.jsonl"); dec = os.path.join(td, "d.json")
        scenario.build(log, dec)
        f = Fleet(log)
        state = {rid: [r["status"], r["version"]] for rid, r in sorted(f.runs.items())}
        expected = {k: list(v) for k, v in demo.EXPECTED.items()}
        check("E1_golden_final_state", state == expected, state)
        check("E2_truncated_tail_tolerated", f.truncated_tail == 1)
        check("E3_rejected_commands_logged", len(f.rejected) == 3, len(f.rejected))
        s = f.summary(now=scenario.BASE + 1030, threshold_seconds=900)
        check("E4_stale_exactly_run_c", s["stale"] == ["run-c"], s["stale"])
        check("E5_summary_counts", s["by_status"] == {"done": 2, "queued": 1, "running": 2}, s["by_status"])
        check("E6_events_count", f.events == 20, f.events)
        f2 = Fleet(log)
        check("E7_replay_determinism", f2.state_hash() == f.state_hash(), f.state_hash())
        # idempotency under replay: duplicate command ids collapse
        check("E8_idempotent_commands", len([c for c in f.commands if c == "c10"]) == 1)
    report = {"evals": checks, "passed": sum(1 for c in checks if c["pass"]), "total": len(checks)}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_report.json")
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    for c in checks:
        print(("PASS " if c["pass"] else "FAIL ") + c["name"])
    print(f"evals: {report['passed']}/{report['total']} passed")
    return 0 if report["passed"] == report["total"] else 1

if __name__ == "__main__":
    sys.exit(main())
