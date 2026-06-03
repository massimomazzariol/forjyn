import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


class PathTests(unittest.TestCase):
    def setUp(self):
        self.old_root = os.environ.get("FORJYN_WORKBENCH_ROOT")

    def tearDown(self):
        if self.old_root is None:
            os.environ.pop("FORJYN_WORKBENCH_ROOT", None)
        else:
            os.environ["FORJYN_WORKBENCH_ROOT"] = self.old_root
        import forjyn_paths

        importlib.reload(forjyn_paths)

    def test_default_runtime_paths(self):
        os.environ.pop("FORJYN_WORKBENCH_ROOT", None)
        import forjyn_paths

        paths = importlib.reload(forjyn_paths)
        self.assertEqual(paths.WORKBENCH, ROOT / "workbench")
        self.assertEqual(paths.RUNTIME_DIR, ROOT / "workbench" / "_runtime")
        self.assertNotIn("." + "local", str(paths.WORKBENCH))
        self.assertNotIn("ForJyn" + "_Workbench", str(paths.WORKBENCH))

    def test_env_var_overrides_runtime_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["FORJYN_WORKBENCH_ROOT"] = tmp
            import forjyn_paths

            paths = importlib.reload(forjyn_paths)
            self.assertEqual(paths.WORKBENCH, Path(tmp).resolve())
            self.assertEqual(paths.RUNTIME_DIR, Path(tmp).resolve() / "_runtime")
            self.assertNotIn("." + "local", str(paths.WORKBENCH))
            self.assertNotIn("ForJyn" + "_Workbench", str(paths.WORKBENCH))


if __name__ == "__main__":
    unittest.main()
