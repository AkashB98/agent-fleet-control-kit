import json, os, subprocess, sys, tempfile, unittest
ROOT = os.path.join(os.path.dirname(__file__), "..")

class TestCli(unittest.TestCase):
    def run_cli(self, *argv, log):
        return subprocess.run([sys.executable, os.path.join(ROOT, "cli.py"), "--log", log, *argv],
                              capture_output=True, text=True)
    def test_register_command_summary_flow(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "f.jsonl")
            r = self.run_cli("register", "r1", "scout", "--ts", "100", log=log)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = self.run_cli("command", "c1", "r1", "start", "--ts", "110", log=log)
            self.assertTrue(json.loads(r.stdout)["applied"])
            r = self.run_cli("summary", "--now", "200", log=log)
            self.assertEqual(json.loads(r.stdout)["by_status"], {"running": 1})
    def test_check_exit_codes(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "f.jsonl")
            self.run_cli("register", "r1", "scout", "--ts", "100", log=log)
            self.run_cli("command", "c1", "r1", "start", "--ts", "110", log=log)
            r = self.run_cli("check", "--now", "200", log=log)
            self.assertEqual(r.returncode, 0, r.stdout)
            r = self.run_cli("check", "--now", "99999", log=log)
            self.assertEqual(r.returncode, 1)  # stale breach

if __name__ == "__main__":
    unittest.main()
