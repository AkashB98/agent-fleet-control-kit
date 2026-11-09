"""Approval consumption — the boundary with tool-approval-gate.

This kit does NOT rebuild an approval queue (tool-approval-gate owns
policy, TTLs and approvers). It CONSUMES a decision file in the gate's
output shape: [{"request_id", "run_id", "decision": "approved"|"denied",
"decided_at"}] and turns each decision into a fleet command:
approved -> approve (waiting_approval -> running),
denied   -> reject  (waiting_approval -> failed).
Decisions for runs not waiting are recorded as rejected commands by the
transition table — never silently applied.
"""
import json

def load_decisions(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("decision file must be a JSON list")
    return data

def apply_decisions(fleet, decisions, command_prefix="apr"):
    results = []
    for i, d in enumerate(decisions):
        action = "approve" if d["decision"] == "approved" else "reject"
        res = fleet.command(f"{command_prefix}-{i:03d}", d["run_id"], action,
                            ts=d["decided_at"])
        results.append({"run_id": d["run_id"], "decision": d["decision"], **res})
    return results
