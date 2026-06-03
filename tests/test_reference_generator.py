import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def is_relative_to(path, parent):
    path = Path(path).resolve()
    parent = Path(parent).resolve()
    return path == parent or parent in path.parents


class ReferenceGeneratorTests(unittest.TestCase):
    def test_generate_one_reference_in_temp_workbench(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["FORJYN_WORKBENCH_ROOT"] = tmp
            env["PYTHONIOENCODING"] = "utf-8"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/forjyn_reference_generator.py",
                    "generate",
                    "--preset",
                    "cyber-edge",
                    "--count",
                    "1",
                    "--size",
                    "128",
                    "--seed",
                    "123",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(len(payload["images"]), 1)
            self.assertEqual(len(payload["metadata"]), 1)

            image_path = Path(payload["images"][0])
            metadata_path = Path(payload["metadata"][0])
            self.assertTrue(is_relative_to(image_path, tmp), image_path)
            self.assertTrue(is_relative_to(metadata_path, tmp), metadata_path)
            self.assertTrue(image_path.exists())
            self.assertTrue(metadata_path.exists())
            self.assertEqual(image_path.suffix.lower(), ".png")

            with Image.open(image_path) as image:
                self.assertEqual(image.size, (128, 128))

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["preset"], "cyber-edge")
            self.assertEqual(metadata["requested_seed"], 123)
            self.assertIn("actual_seed", metadata)
            self.assertIn("quality_score", metadata)
            self.assertIn("final_quality_pass", metadata)
            self.assertIn("contrast_score", metadata)


if __name__ == "__main__":
    unittest.main()
