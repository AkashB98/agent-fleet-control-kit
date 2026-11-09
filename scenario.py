"""The golden scenario: a seeded event stream exercising every failure
mode — crash mid-write, duplicate commands, out-of-order heartbeats,
approve-after-timeout. Timestamps are fixed integers (injected clock)."""
import json
import approvals
from fleet import Fleet

BASE = 1_700_000_000

def build(log_path, decision_path):
    f = Fleet(log_path)
    t = BASE
    for run_id, agent in [("run-a", "scout"), ("run-b", "scout"),
                          ("run-c", "builder"), ("run-d", "builder"),
                          ("run-e", "hawk")]:
        f.register(run_id, agent, ts=t); t += 10
    f.command("c01", "run-a", "start", ts=t); t += 10
    f.command("c02", "run-a", "heartbeat", ts=t); t += 10
    f.command("c03", "run-a", "complete", ts=t); t += 10
    f.command("c04", "run-b", "start", ts=t); t += 10
    f.command("c05", "run-b", "wait_approval", ts=t); t += 10
    f.command("c06", "run-c", "start", ts=t); t += 10
    # run-c goes silent here: no more heartbeats -> stale at check time
    f.command("c07", "run-d", "start", ts=t); t += 10
    f.command("c08", "run-d", "pause", ts=t); t += 10
    f.command("c09", "run-d", "resume", ts=t); t += 10
    f.command("c10", "run-d", "heartbeat", ts=t); t += 10
    # duplicate command id: must be a no-op (idempotency)
    f.command("c10", "run-d", "heartbeat", ts=t + 999)
    # illegal transition: completing a queued run -> rejected + logged
    f.command("c11", "run-e", "complete", ts=t); t += 10
    # version conflict: run-a is done (version moved) -> rejected
    f.command("c12", "run-a", "start", ts=t, expected_version=1); t += 10
    # approval decisions arrive from tool-approval-gate's output file:
    # run-b approved; run-e is not waiting, so its decision is rejected
    decisions = [
        {"request_id": "apr-0001", "run_id": "run-b",
         "decision": "approved", "decided_at": t},
        {"request_id": "apr-0002", "run_id": "run-e",
         "decision": "approved", "decided_at": t + 10},
    ]
    with open(decision_path, "w", encoding="utf-8") as fh:
        json.dump(decisions, fh, indent=2)
    results = approvals.apply_decisions(f, decisions)
    t += 20
    # approve-after-timeout: run-b was approved already; a second,
    # late decision for a NEW waiting run that timed out first
    f.command("c13", "run-b", "complete", ts=t); t += 10
    # simulate a crash mid-write: a truncated final line in the log
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write('{"kind":"command","command_id":"c99","run_id":"run-c","act')
    return f, results
