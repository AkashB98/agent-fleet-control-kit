import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fleet import Fleet, CorruptLog

class TestFleet(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.td.name, "f.jsonl")
        self.f = Fleet(self.log)
    def tearDown(self):
        self.td.cleanup()
    def test_register_and_start(self):
        self.f.register("r1", "scout", ts=100)
        res = self.f.command("c1", "r1", "start", ts=110)
        self.assertTrue(res["applied"])
        self.assertEqual(self.f.runs["r1"]["status"], "running")
    def test_illegal_transition_rejected_and_logged(self):
        self.f.register("r1", "scout", ts=100)
        res = self.f.command("c1", "r1", "complete", ts=110)
        self.assertFalse(res["applied"])
        self.assertEqual(res["reason"], "illegal_transition")
        self.assertEqual(len(self.f.rejected), 1)
        self.assertEqual(self.f.runs["r1"]["status"], "queued")
    def test_duplicate_command_is_noop(self):
        self.f.register("r1", "scout", ts=100)
        self.f.command("c1", "r1", "start", ts=110)
        v = self.f.runs["r1"]["version"]
        res = self.f.command("c1", "r1", "start", ts=999)
        self.assertTrue(res.get("duplicate"))
        self.assertEqual(self.f.runs["r1"]["version"], v)
    def test_version_conflict_rejected(self):
        self.f.register("r1", "scout", ts=100)
        res = self.f.command("c1", "r1", "start", ts=110, expected_version=7)
        self.assertFalse(res["applied"])
        self.assertEqual(res["reason"], "version_conflict")
    def test_unknown_run_rejected(self):
        res = self.f.command("c1", "ghost", "start", ts=110)
        self.assertFalse(res["applied"])
    def test_replay_rebuilds_state(self):
        self.f.register("r1", "scout", ts=100)
        self.f.command("c1", "r1", "start", ts=110)
        self.f.command("c2", "r1", "complete", ts=120)
        f2 = Fleet(self.log)
        self.assertEqual(f2.runs["r1"]["status"], "done")
        self.assertEqual(f2.state_hash(), self.f.state_hash())
    def test_truncated_tail_tolerated(self):
        self.f.register("r1", "scout", ts=100)
        with open(self.log, "a") as fh:
            fh.write('{"kind":"command","comm')
        f2 = Fleet(self.log)
        self.assertEqual(f2.truncated_tail, 1)
    def test_mid_log_corruption_raises(self):
        self.f.register("r1", "scout", ts=100)
        self.f.register("r2", "scout", ts=101)
        lines = open(self.log).read().splitlines()
        lines[0] = "{broken"
        open(self.log, "w").write("\n".join(lines) + "\n")
        with self.assertRaises(CorruptLog):
            Fleet(self.log)
    def test_stale_detection_injected_clock(self):
        self.f.register("r1", "scout", ts=100)
        self.f.command("c1", "r1", "start", ts=110)
        self.f.command("c2", "r1", "heartbeat", ts=120)
        self.assertEqual(self.f.stale_runs(now=500, threshold_seconds=900), [])
        self.assertEqual(self.f.stale_runs(now=2000, threshold_seconds=900), ["r1"])
    def test_done_run_never_stale(self):
        self.f.register("r1", "scout", ts=100)
        self.f.command("c1", "r1", "start", ts=110)
        self.f.command("c2", "r1", "complete", ts=120)
        self.assertEqual(self.f.stale_runs(now=99999, threshold_seconds=1), [])
    def test_pause_resume_cycle(self):
        self.f.register("r1", "scout", ts=100)
        self.f.command("c1", "r1", "start", ts=110)
        self.f.command("c2", "r1", "pause", ts=120)
        self.assertEqual(self.f.runs["r1"]["status"], "paused")
        self.f.command("c3", "r1", "resume", ts=130)
        self.assertEqual(self.f.runs["r1"]["status"], "running")
    def test_terminal_states_closed(self):
        self.f.register("r1", "scout", ts=100)
        self.f.command("c1", "r1", "start", ts=110)
        self.f.command("c2", "r1", "fail", ts=120)
        res = self.f.command("c3", "r1", "start", ts=130)
        self.assertFalse(res["applied"])

if __name__ == "__main__":
    unittest.main()
