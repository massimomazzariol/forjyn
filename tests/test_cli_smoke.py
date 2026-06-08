import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliSmokeTests(unittest.TestCase):
    def run_forjyn(self, *args):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["FORJYN_WORKBENCH_ROOT"] = tmp
            env["PYTHONIOENCODING"] = "utf-8"
            completed = subprocess.run(
                [sys.executable, *args],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"Command failed: {' '.join(args)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            )
            return completed, Path(tmp)

    def test_workbench_help(self):
        completed, _tmp = self.run_forjyn("tools/forjyn_workbench.py", "--help")
        self.assertIn("ForJyn Workbench", completed.stdout)

    def test_workbench_init_and_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["FORJYN_WORKBENCH_ROOT"] = tmp
            env["PYTHONIOENCODING"] = "utf-8"
            for args in (
                [sys.executable, "tools/forjyn_workbench.py", "init"],
                [sys.executable, "tools/forjyn_workbench.py", "scan"],
            ):
                completed = subprocess.run(
                    args,
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"Command failed: {' '.join(args)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
                )
            self.assertTrue((Path(tmp) / "_runtime" / "reports" / "scan.json").exists())

    def test_reference_generator_check_and_presets(self):
        completed, _tmp = self.run_forjyn("tools/forjyn_reference_generator.py", "--check")
        self.assertIn("reference generator check passed", completed.stdout)
        completed, _tmp = self.run_forjyn("tools/forjyn_reference_generator.py", "list-presets")
        self.assertIn("cyber-edge", completed.stdout)

    def test_gui_check(self):
        completed, _tmp = self.run_forjyn("tools/forjyn_workbench_gui.py", "--check")
        self.assertIn("ForJyn Workbench GUI check", completed.stdout)
        self.assertIn("Workbench:", completed.stdout)
        self.assertIn("Run monitor: available", completed.stdout)
        self.assertIn("Stop/Cancel: available", completed.stdout)


if __name__ == "__main__":
    unittest.main()
