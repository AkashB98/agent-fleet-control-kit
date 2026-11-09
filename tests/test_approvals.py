import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import approvals
from fleet import Fleet

class TestApprovals(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.f = Fleet(os.path.join(self.td.name, "f.jsonl"))
        self.f.register("r1", "scout", ts=100)
        self.f.command("c1", "r1", "start", ts=110)
        self.f.command("c2", "r1", "wait_approval", ts=120)
    def tearDown(self):
        self.td.cleanup()
    def test_approved_resumes_running(self):
        out = approvals.apply_decisions(self.f, [{"run_id": "r1", "decision": "approved", "decided_at": 130}])
        self.assertTrue(out[0]["applied"])
        self.assertEqual(self.f.runs["r1"]["status"], "running")
    def test_denied_fails_run(self):
        approvals.apply_decisions(self.f, [{"run_id": "r1", "decision": "denied", "decided_at": 130}])
        self.assertEqual(self.f.runs["r1"]["status"], "failed")
    def test_decision_for_non_waiting_run_rejected(self):
        self.f.register("r2", "scout", ts=100)
        out = approvals.apply_decisions(self.f, [{"run_id": "r2", "decision": "approved", "decided_at": 130}])
        self.assertFalse(out[0]["applied"])

if __name__ == "__main__":
    unittest.main()
