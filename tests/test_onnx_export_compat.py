import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from forjyn_workbench import build_onnx_export_kwargs


class FakeDim:
    def __init__(self, name, min=None):
        self.name = name
        self.min = min


def export_with_dynamic_shapes(_model, _args, _path, *, dynamic_shapes, **_kwargs):
    return dynamic_shapes


def export_with_dynamic_axes(_model, _args, _path, *, dynamic_axes, **_kwargs):
    return dynamic_axes


class OnnxExportCompatTests(unittest.TestCase):
    def test_uses_dynamic_shapes_when_supported(self):
        kwargs, mode = build_onnx_export_kwargs(export_with_dynamic_shapes, dim_factory=FakeDim)
        self.assertEqual(mode, "dynamic_shapes")
        self.assertIn("dynamic_shapes", kwargs)
        self.assertNotIn("dynamic_axes", kwargs)
        self.assertEqual(kwargs["dynamic_shapes"]["input"][2].name, "height")

    def test_uses_dynamic_axes_legacy_fallback(self):
        kwargs, mode = build_onnx_export_kwargs(export_with_dynamic_axes, dim_factory=FakeDim)
        self.assertEqual(mode, "dynamic_axes")
        self.assertIn("dynamic_axes", kwargs)
        self.assertNotIn("dynamic_shapes", kwargs)
        self.assertEqual(kwargs["dynamic_axes"]["input"][2], "height")
        self.assertEqual(kwargs["dynamic_axes"]["output"][3], "width")


if __name__ == "__main__":
    unittest.main()
