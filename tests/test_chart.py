import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("chart", ROOT / "assets" / "chart.py")
chart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chart)

class ChartSmokeTests(unittest.TestCase):
    def test_svg_escapes_text(self):
        self.assertIn("&lt;tag&gt;", chart.hbar([("<tag>", 1)]))

    def test_explicit_zero_max_is_preserved(self):
        svg = chart.hbar([("x", 0)], maxv=1)
        self.assertIn('width="0.0"', svg)

    def test_negative_pair_is_rendered(self):
        svg = chart.paired_bars([("x", -2, 3)], ymin=-3, ymax=4)
        self.assertIn("-2", svg)

if __name__ == "__main__":
    unittest.main()
