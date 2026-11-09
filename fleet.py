"""Event-sourced fleet control plane.

The append-only JSONL event log is the ONLY state. Fleet state is always
rebuilt by replaying the log — there is no mutable state file to corrupt.
Commands carry ids (idempotent: a duplicate command_id is a no-op that
returns the original result). Each run carries a version; a command that
names the wrong expected version is rejected (optimistic concurrency).
Appends happen under an exclusive file lock so two CLI writers cannot
interleave a torn write. A truncated final line (crash mid-write) is
tolerated on replay and counted; corruption anywhere else is an error.
"""
import fcntl
import hashlib
import json
import os

TRANSITIONS = {
    "queued": {"start", "cancel"},
    "running": {"heartbeat", "pause", "complete", "fail", "wait_approval"},
    "waiting_approval": {"approve", "reject", "timeout"},
    "paused": {"resume", "cancel"},
    "done": set(), "failed": set(), "cancelled": set(),
}
RESULT_STATUS = {
    "start": "running", "pause": "paused", "resume": "running",
    "complete": "done", "fail": "failed", "cancel": "cancelled",
    "wait_approval": "waiting_approval", "approve": "running",
    "reject": "failed", "timeout": "failed", "heartbeat": "running",
}

class CorruptLog(Exception):
    pass

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

class Fleet:
    def __init__(self, log_path):
        self.log_path = log_path
        self.runs = {}          # run_id -> run dict
        self.commands = {}      # command_id -> result dict
        self.rejected = []      # rejected transition attempts (logged)
        self.truncated_tail = 0
        self.events = 0
        if os.path.exists(log_path):
            self._replay()

    # ---------- replay ----------
    def _replay(self):
        with open(self.log_path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                if i == len(lines) - 1:
                    self.truncated_tail += 1
                    continue
                raise CorruptLog(f"corrupt event at line {i + 1}")
            self.events += 1
            self._apply(ev)

    def _apply(self, ev):
        kind = ev["kind"]
        if kind == "register":
            self.runs[ev["run_id"]] = {
                "run_id": ev["run_id"], "agent": ev["agent"],
                "status": "queued", "version": 1,
                "registered_at": ev["ts"], "last_heartbeat": None,
                "last_ts": ev["ts"],
            }
            return
        if kind == "command":
            self.commands[ev["command_id"]] = ev["result"]
            if ev["result"].get("applied"):
                run = self.runs[ev["run_id"]]
                run["status"] = RESULT_STATUS[ev["action"]]
                run["version"] += 1
                run["last_ts"] = ev["ts"]
                if ev["action"] == "heartbeat":
                    run["last_heartbeat"] = ev["ts"]
            else:
                self.rejected.append(ev)
            return
        raise CorruptLog(f"unknown event kind {kind!r}")

    # ---------- writes ----------
    def _append(self, ev):
        line = _canonical(ev) + "\n"
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
            fcntl.flock(fh, fcntl.LOCK_UN)
        self.events += 1
        self._apply(ev)

    def register(self, run_id, agent, ts):
        if run_id in self.runs:
            return {"applied": False, "reason": "already_registered"}
        self._append({"kind": "register", "run_id": run_id,
                      "agent": agent, "ts": ts})
        return {"applied": True, "status": "queued"}

    def command(self, command_id, run_id, action, ts, expected_version=None):
        if command_id in self.commands:
            prior = dict(self.commands[command_id])
            prior["duplicate"] = True
            return prior
        run = self.runs.get(run_id)
        if run is None:
            result = {"applied": False, "reason": "unknown_run"}
        elif action not in TRANSITIONS.get(run["status"], set()):
            result = {"applied": False, "reason": "illegal_transition",
                      "from": run["status"], "action": action}
        elif expected_version is not None and expected_version != run["version"]:
            result = {"applied": False, "reason": "version_conflict",
                      "expected": expected_version, "actual": run["version"]}
        else:
            result = {"applied": True, "status": RESULT_STATUS[action]}
        self._append({"kind": "command", "command_id": command_id,
                      "run_id": run_id, "action": action, "ts": ts,
                      "result": result})
        return result

    # ---------- reads ----------
    def stale_runs(self, now, threshold_seconds):
        """Running runs whose last heartbeat (or start) is older than the
        threshold. Clock is INJECTED (`now`) — core logic never reads the
        wall clock, so staleness is fully deterministic in tests."""
        out = []
        for run in self.runs.values():
            if run["status"] != "running":
                continue
            ref = run["last_heartbeat"] or run["last_ts"]
            if now - ref > threshold_seconds:
                out.append(run["run_id"])
        return sorted(out)

    def summary(self, now=None, threshold_seconds=900):
        by_status, by_agent = {}, {}
        for run in self.runs.values():
            by_status[run["status"]] = by_status.get(run["status"], 0) + 1
            a = by_agent.setdefault(run["agent"], {"total": 0, "done": 0, "failed": 0})
            a["total"] += 1
            if run["status"] == "done":
                a["done"] += 1
            if run["status"] == "failed":
                a["failed"] += 1
        return {
            "runs": len(self.runs), "events": self.events,
            "by_status": by_status, "by_agent": by_agent,
            "rejected_commands": len(self.rejected),
            "truncated_tail": self.truncated_tail,
            "stale": self.stale_runs(now, threshold_seconds) if now is not None else [],
        }

    def state_hash(self):
        payload = {rid: (r["status"], r["version"]) for rid, r in self.runs.items()}
        return hashlib.sha256(_canonical(payload).encode()).hexdigest()[:16]
