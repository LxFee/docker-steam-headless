#!/usr/bin/env python3
"""Offline regression tests; optional UINPUT_SERVICE checks installed build output."""
import ast
import hashlib
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures/uinput"
PATCH = ROOT / "scripts/patch-dumb-udev.py"
HELPER = Path(os.environ.get("UINPUT_HELPER", ROOT / "overlay/usr/bin/start-dumb-udev.sh"))


class ConfigureUinputTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.service = self.directory / "service.py"
        self.service.write_bytes((FIXTURES / "service.py").read_bytes())

    def patch_service(self):
        result = subprocess.run(["python3", str(PATCH), str(self.service)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fixture_integrity(self):
        self.assertEqual(hashlib.sha256(self.service.read_bytes()).hexdigest(),
                         "09aa1517fe0cc80d8ec61e78e6a1b9f2a4c4f9a4f5d1616f2efa06404d52bb2e")

    def test_installed_service_matches_tested_output(self):
        self.patch_service()
        installed = os.environ.get("UINPUT_SERVICE")
        if installed:
            self.assertEqual(Path(installed).read_bytes(), self.service.read_bytes())
        else:
            self.skipTest("installed service checked during Docker build")

    def test_unknown_and_partial_sources_fail_without_writing(self):
        original = self.service.read_bytes()
        for source in (original + b"\n", original.replace(b"subsys.encode(), 0", b"subsys.encode(), 1"),
                       original.replace(b"ID_INPUT_JOYSTICK", b"ID_INPUT_MOUSE"),
                       original + b"invalid syntax!\n"):
            with self.subTest(source=hashlib.sha256(source).hexdigest()):
                self.service.write_bytes(source)
                result = subprocess.run(["python3", str(PATCH), str(self.service)],
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("source SHA-256", result.stderr)
                self.assertEqual(source, self.service.read_bytes())
        self.service.write_bytes(original)
        self.patch_service()
        patched = self.service.read_bytes()
        result = subprocess.run(["python3", str(PATCH), str(self.service)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)  # Build-only, not a runtime idempotent hook.
        self.assertEqual(patched, self.service.read_bytes())

    def test_marker_survives_absence_reconnect_and_watcher_restart(self):
        helper = HELPER.read_text()
        self.assertNotIn("supervisorctl restart", helper)
        self.assertNotIn('rm -f "${state_dir}/xorg-restarted"', helper)
        self.assertNotIn("ABSENCE_DEBOUNCE_SECONDS", helper)
        subprocess.run(["bash", "-n", str(HELPER)], check=True)
        loop = helper.split("while true; do\n", 1)[1].split("done &", 1)[0]
        script = '''set -e
state_dir="$1"
sync_input_nodes() { :; }
sleep() { :; }
sunshine_inputs_present() { [[ "$present" == 1 ]]; }
supervisorctl() { echo unexpected-restart >&2; exit 99; }
for present in ''' + "0 1 " + "0 " * 30 + "1 1; do\n" + loop + "done\n"
        for watcher_start in range(2):
            result = subprocess.run(["bash", "-c", script, "test", str(self.directory)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((self.directory / "xorg-restarted").exists())
            self.assertEqual(result.stdout.count("announced through udev hotplug"),
                             1 if watcher_start == 0 else 0)

    def test_classification_and_hash_semantics(self):
        self.patch_service()
        tree = ast.parse(self.service.read_text())

        def load_inner(name, namespace):
            node = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name == name)
            # Remove pyudev annotations; test the real patched function body.
            for arg in node.args.args:
                arg.annotation = None
            exec(compile(ast.Module(body=[node], type_ignores=[]), "fixture", "exec"),
                 namespace)
            return namespace[name]

        class Device:
            device_node = "/dev/input/event0"

            def __init__(self, name=None, parent=None):
                self.name, self.parent = name, parent

            def get(self, key):
                return self.name if key == "NAME" else None

        import time
        classify = load_inner("build_data_content", {"time": time})
        for name, properties in [
            ('"Sunshine Keyboard"', ["KEY", "KEYBOARD"]),
            ("Sunshine Mouse", ["MOUSE"]), ("Sunshine Touch", ["TOUCHSCREEN"]),
            ("Sunshine Pen", ["TABLET"]), ("gamepad", ["JOYSTICK"]),
            (None, ["JOYSTICK"]),
        ]:
            with self.subTest(name=name):
                content = classify(Device(parent=Device(name)))
                flags = [line for line in content if line.startswith("E:ID_INPUT_")]
                self.assertEqual(flags, [f"E:ID_INPUT_{p}=1\n" for p in properties])
                self.assertIn("E:ID_INPUT=1\n", content)
                self.assertIn("G:uaccess\n", content)
        def fake_hash(value, seed):
            self.assertEqual(seed, 0)
            return {b"input": 0x12345678, b"event": 0x90abcdef}[value]

        build_header = load_inner("build_header", {
            "socket": socket, "struct": struct, "UDEV_MONITOR_MAGIC": 0xfeedcafe,
            "murmurhash2": fake_hash,
        })
        header = build_header(12, "input", "event", 0)
        self.assertEqual(header[24:32], bytes.fromhex("1234567890abcdef"))
        self.assertEqual(build_header(12, "", "", 0)[24:32], bytes(8))


if __name__ == "__main__":
    unittest.main()
