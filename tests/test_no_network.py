import os, socket, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

class TestNoNetwork(unittest.TestCase):
    def test_demo_runs_with_network_disabled(self):
        real = socket.socket
        class Blocked(real):
            def connect(self, *a, **k):
                raise AssertionError("network use attempted")
            def connect_ex(self, *a, **k):
                raise AssertionError("network use attempted")
        socket.socket = Blocked
        try:
            import demo
            self.assertEqual(demo.run(), 0)
        finally:
            socket.socket = real

if __name__ == "__main__":
    unittest.main()
