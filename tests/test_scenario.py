import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import demo, scenario
from fleet import Fleet

class TestScenario(unittest.TestCase):
    def test_golden_final_state(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "f.jsonl"); dec = os.path.join(td, "d.json")
            scenario.build(log, dec)
            f = Fleet(log)
            state = {rid: (r["status"], r["version"]) for rid, r in f.runs.items()}
            self.assertEqual(state, demo.EXPECTED)
            self.assertEqual(f.truncated_tail, 1)
            self.assertEqual(len(f.rejected), 3)
    def test_golden_stale(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "f.jsonl"); dec = os.path.join(td, "d.json")
            scenario.build(log, dec)
            f = Fleet(log)
            self.assertEqual(f.stale_runs(scenario.BASE + 1030, 900), ["run-c"])

if __name__ == "__main__":
    unittest.main()
