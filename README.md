# agent-fleet-control-kit

**A control plane for a fleet of local agent runs where the failure handling is the product: an append-only event log is the only state, every command is idempotent, illegal transitions are rejected and logged — never silently applied — and a crash mid-write costs you exactly one truncated line, not the fleet.**

Running several agents at once (the pattern behind tools like t3code, 49k★ in GitHub trending) is easy to demo and hard to operate: two writers race, a command gets retried and applies twice, a run dies silently, an approval lands after its run already timed out. This kit is the small, honest core that survives those cases. State is **event-sourced** — rebuilt by replaying an append-only JSONL log — commands carry ids so retries are no-ops, versions are checked so stale writers lose, and staleness is judged on an injected clock so every behaviour is deterministic and testable.

Stdlib-only Python. Zero network, zero API keys, zero external dependencies. CLI only — deliberately **no HTTP layer**: Claude's cross-check on this design (2026-11-06) cut the serve API, because an HTTP wrapper adds polish, not signal; the control semantics are the signal.

## How this differs from its sibling projects

- **tool-approval-gate** — owns approval POLICY (rules, TTLs, approvers). This kit does not rebuild a queue: it *consumes* the gate's decision file and turns decisions into fleet commands.
- **agent-eval-dashboard** — a read-only view over eval results. This kit is the write path: commands that change run state, with the invariants to do it safely.
- **agent-slo-tracker** — measures fleet health after the fact (SLOs, burn alerts). This kit is the live control surface those measurements describe.

## Quickstart

```bash
python3 cli.py --log fleet.jsonl register run-1 scout --ts 1700000000
python3 cli.py --log fleet.jsonl command c1 run-1 start --ts 1700000010
python3 cli.py --log fleet.jsonl command c2 run-1 heartbeat --ts 1700000100
python3 cli.py --log fleet.jsonl summary --now 1700000200
python3 cli.py --log fleet.jsonl apply-decisions fixtures/decisions.json
python3 cli.py --log fleet.jsonl check --now 1700000200   # exit 0 pass / 1 stale-or-rejected breach / 2 corrupt log
python3 demo.py                                            # golden scenario, asserted end state
```

## The golden scenario (fixtures/fleet_log.jsonl)

Five runs across three agents, one stream containing every planted failure: a **duplicate command** (c10 sent twice — second is a no-op), an **illegal transition** (completing a queued run — rejected, logged), a **version conflict**, an **approval for a run that was never waiting** (rejected by the transition table), a run that goes **silent** (run-c, stale at the check clock), and a **crash mid-write** (the log's last line is truncated — replay tolerates it and counts it). Exact final state, pinned by evals:

| Run | Agent | Final status | Version |
|---|---|---|---|
| run-a | scout | done | 4 |
| run-b | scout | done | 5 |
| run-c | builder | running (stale) | 2 |
| run-d | builder | running | 5 |
| run-e | hawk | queued | 1 |

20 events · 3 rejected commands · 1 truncated tail · stale at BASE+1030 (threshold 900s): exactly `[run-c]`.

## Design notes

- **Event sourcing** — keeping every change as an appended fact and deriving state from the facts, so replay always reproduces the same fleet.
- **Idempotency** — a command id that has been seen returns its original result; retries cannot double-apply.
- **Optimistic concurrency** — a writer names the version it saw; if the run has moved, the command is rejected instead of overwriting.
- **Injected clock** — time is passed in, never read from the wall, so stale-detection is a pure function and the golden eval is exact.

## Dev-loop honesty

- The demo's first stale check used a clock where run-d was *also* legitimately stale — the assertion was right and the scenario clock was wrong; the check now uses the window where only the planted silent run is stale, and a unit test pins both sides of the threshold.
- Mid-log corruption raises `CorruptLog` (exit 2); only the *final* line may be truncated. Anything else would hide real damage.

## Tests & evals

- `python3 -m unittest discover -s tests` → 20 hermetic tests (incl. no-network).
- `python3 evals/run_evals.py` → 8/8 golden evals; `eval_report.json` byte-identical across runs.
