import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed\n{completed.stderr}")
    return completed.stdout.splitlines()


class RepoHygieneTests(unittest.TestCase):
    def test_runtime_roots_are_not_tracked(self):
        tracked = git("ls-files", "workbench", "ForJyn" + "_Workbench", "forjyn-" + "workbench", "." + "local", ".venv")
        self.assertEqual(tracked, [])

    def test_upstream_onnx_weights_are_tracked(self):
        expected = {
            "weights/candy.onnx",
            "weights/mosaic.onnx",
            "weights/rain-princess.onnx",
            "weights/udnie.onnx",
        }
        tracked = set(git("ls-files", "weights"))
        self.assertEqual(tracked, expected)
        for path in expected:
            self.assertTrue((ROOT / path).exists(), path)

    def test_no_operational_references_to_legacy_runtime_paths(self):
        blocked = [
            "ForJyn" + "_Workbench",
            "forjyn-" + "workbench",
            "." + "local",
            "technical" + "/",
            "_forjyn" + "_runtime",
        ]
        allowed = {".gitignore"}
        for name in git("ls-files"):
            if name in allowed:
                continue
            path = ROOT / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for needle in blocked:
                self.assertNotIn(needle, text, f"{needle} found in {name}")


if __name__ == "__main__":
    unittest.main()
