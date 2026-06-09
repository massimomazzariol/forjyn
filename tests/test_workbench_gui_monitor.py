import sys
import queue
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from forjyn_workbench_gui import (
    ForJynWorkbenchApp,
    format_cpu_load,
    format_elapsed,
    format_process_cores,
    format_ram_mb,
    psutil,
)


class WorkbenchGuiMonitorTests(unittest.TestCase):
    def test_format_elapsed_uses_hh_mm_ss(self):
        self.assertEqual(format_elapsed(0), "00:00:00")
        self.assertEqual(format_elapsed(65), "00:01:05")
        self.assertEqual(format_elapsed(3661), "01:01:01")

    def test_monitor_metric_formatting_is_human_readable(self):
        self.assertEqual(format_cpu_load(62.4), "62%")
        self.assertEqual(format_process_cores(1580.0), "15.8 cores")
        self.assertEqual(format_ram_mb(1843), "1843 MB")
        self.assertEqual(format_cpu_load(None), "-")
        self.assertEqual(format_process_cores(None), "-")

    def test_cancel_terminates_process_tree(self):
        if psutil is None:
            self.skipTest("psutil is not available")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            child_script = tmp_path / "child.py"
            child_script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            parent_script = tmp_path / "parent.py"
            parent_script.write_text(
                "\n".join(
                    [
                        "import subprocess",
                        "import sys",
                        "import time",
                        "child = subprocess.Popen([sys.executable, sys.argv[1]])",
                        "print(child.pid, flush=True)",
                        "time.sleep(30)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [sys.executable, str(parent_script), str(child_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
            )
            assert process.stdout is not None
            child_pid = int(process.stdout.readline().strip())
            try:
                app_like = SimpleNamespace(log_queue=queue.Queue())
                ForJynWorkbenchApp._terminate_process_tree(app_like, process)
                process.wait(timeout=8)
                with self.assertRaises(psutil.NoSuchProcess):
                    psutil.Process(child_pid)
            finally:
                if process.poll() is None:
                    process.kill()


if __name__ == "__main__":
    unittest.main()
