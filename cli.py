#!/usr/bin/env python3
"""Fleet control CLI. No HTTP layer — deliberately (see README)."""
import argparse
import json
import sys

import approvals
from fleet import Fleet, CorruptLog

def _fleet(args):
    return Fleet(args.log)

def main(argv=None):
    p = argparse.ArgumentParser(prog="fleet")
    p.add_argument("--log", default="fixtures/fleet_log.jsonl")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register"); r.add_argument("run_id"); r.add_argument("agent"); r.add_argument("--ts", type=int, required=True)
    c = sub.add_parser("command"); c.add_argument("command_id"); c.add_argument("run_id"); c.add_argument("action"); c.add_argument("--ts", type=int, required=True); c.add_argument("--expected-version", type=int)
    s = sub.add_parser("summary"); s.add_argument("--now", type=int); s.add_argument("--threshold", type=int, default=900)
    sub.add_parser("state")
    sub.add_parser("replay")
    k = sub.add_parser("check"); k.add_argument("--now", type=int, required=True); k.add_argument("--threshold", type=int, default=900)
    sub.add_parser("demo")
    a = sub.add_parser("apply-decisions"); a.add_argument("file")
    args = p.parse_args(argv)
    try:
        f = _fleet(args)
        if args.cmd == "register":
            print(json.dumps(f.register(args.run_id, args.agent, args.ts)))
        elif args.cmd == "command":
            print(json.dumps(f.command(args.command_id, args.run_id, args.action, args.ts, args.expected_version)))
        elif args.cmd == "summary":
            print(json.dumps(f.summary(now=args.now, threshold_seconds=args.threshold), indent=2, sort_keys=True))
        elif args.cmd == "state":
            print(json.dumps({rid: {"status": r["status"], "version": r["version"], "agent": r["agent"]} for rid, r in sorted(f.runs.items())}, indent=2))
        elif args.cmd == "replay":
            print(json.dumps({"events": f.events, "runs": len(f.runs), "truncated_tail": f.truncated_tail, "state_hash": f.state_hash()}))
        elif args.cmd == "apply-decisions":
            print(json.dumps(approvals.apply_decisions(f, approvals.load_decisions(args.file)), indent=2))
        elif args.cmd == "check":
            stale = f.stale_runs(args.now, args.threshold)
            if stale or f.rejected:
                print(json.dumps({"verdict": "BREACH", "stale": stale, "rejected": len(f.rejected)}))
                return 1
            print(json.dumps({"verdict": "PASS", "stale": [], "rejected": 0}))
            return 0
        elif args.cmd == "demo":
            import demo
            return demo.run()
    except CorruptLog as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
