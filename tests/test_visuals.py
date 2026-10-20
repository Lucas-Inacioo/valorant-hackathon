import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from PIL import Image
from matplotlib import pyplot as plt

import round_map


class VisualRegressionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.image = Path(self.directory.name) / "map.png"
        Image.new("RGB", (100, 100), "white").save(self.image)
        self.meta = {"xMultiplier": .001, "xScalarToAdd": .5,
                     "yMultiplier": .001, "yScalarToAdd": .5}
        self.files = patch("round_map.minimap_file", return_value=self.image)
        self.files.start()

    def tearDown(self):
        self.files.stop()
        self.directory.cleanup()
        plt.close("all")

    def test_revived_player_is_drawn_alive_once_and_figure_is_detached(self):
        events = [
            {"kind": "kill", "victim": "a", "victim_location": {"x": 0, "y": 0},
             "locations": [{"puuid": "b", "location": {"x": 2, "y": 3}}], "alive_after": ["b"]},
            {"kind": "plant", "locations": [
                {"puuid": "a", "location": {"x": 5, "y": 6}},
                {"puuid": "b", "location": {"x": 2, "y": 3}}], "alive_after": ["a", "b"]},
        ]
        before = set(plt.get_fignums())
        with patch("round_map.draw_player", wraps=round_map.draw_player) as draw:
            figure = round_map.draw_round_map(self.meta, events, 1, "a", {"a": "Blue", "b": "Red"}, {"a": "A", "b": "B"})
        player = [call for call in draw.call_args_list if call.args[4] == "A"]
        self.assertEqual(len(player), 1)
        self.assertTrue(player[0].kwargs.get("alive", True))
        self.assertEqual(set(plt.get_fignums()), before)
        output = io.BytesIO()
        figure.savefig(output, format="png")
        self.assertTrue(output.getvalue().startswith(b"\x89PNG"))

    def test_zero_and_one_reference_rates_are_valid_color_scales(self):
        before = set(plt.get_fignums())
        for rate in (0., 1.):
            table = pd.DataFrame({"x": [0], "y": [0], "n": [5], "rate": [rate]}, index=["site"])
            figure = round_map.draw_rate_markers(self.meta, table, "n", "rate", rate, "taxa")
            output = io.BytesIO()
            figure.savefig(output, format="png")
            self.assertGreater(len(output.getvalue()), 100)
        self.assertEqual(set(plt.get_fignums()), before)


if __name__ == "__main__":
    unittest.main()
