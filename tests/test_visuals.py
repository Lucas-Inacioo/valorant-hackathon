import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from PIL import Image
from matplotlib import pyplot as plt

from valorant.ui import round_map


class VisualRegressionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.image = Path(self.directory.name) / "map.png"
        Image.new("RGB", (100, 100), "white").save(self.image)
        self.meta = {
            "xMultiplier": 0.001,
            "xScalarToAdd": 0.5,
            "yMultiplier": 0.001,
            "yScalarToAdd": 0.5,
        }
        self.files = patch("valorant.ui.round_map.minimap_file", return_value=self.image)
        self.files.start()

    def tearDown(self):
        self.files.stop()
        self.directory.cleanup()
        plt.close("all")

    def test_revived_player_is_drawn_alive_once_and_figure_is_detached(self):
        events = [
            {
                "kind": "kill",
                "victim": "a",
                "victim_location": {"x": 0, "y": 0},
                "locations": [{"puuid": "b", "location": {"x": 2, "y": 3}}],
                "alive_after": ["b"],
            },
            {
                "kind": "plant",
                "locations": [
                    {"puuid": "a", "location": {"x": 5, "y": 6}},
                    {"puuid": "b", "location": {"x": 2, "y": 3}},
                ],
                "alive_after": ["a", "b"],
            },
        ]
        before = set(plt.get_fignums())
        with patch("valorant.ui.round_map.draw_player", wraps=round_map.draw_player) as draw:
            figure = round_map.draw_round_map(
                self.meta, events, 1, "a", {"a": "Blue", "b": "Red"}, {"a": "A", "b": "B"}
            )
        player = [call for call in draw.call_args_list if call.args[4] == "A"]
        self.assertEqual(len(player), 1)
        self.assertTrue(player[0].kwargs.get("alive", True))
        self.assertEqual(set(plt.get_fignums()), before)
        output = io.BytesIO()
        figure.savefig(output, format="png")
        self.assertTrue(output.getvalue().startswith(b"\x89PNG"))

    def test_zero_and_one_reference_rates_are_valid_color_scales(self):
        before = set(plt.get_fignums())
        for rate in (0.0, 1.0):
            table = pd.DataFrame({"x": [0], "y": [0], "n": [5], "rate": [rate]}, index=["site"])
            figure = round_map.draw_rate_markers(self.meta, table, "n", "rate", rate, "taxa")
            output = io.BytesIO()
            figure.savefig(output, format="png")
            self.assertGreater(len(output.getvalue()), 100)
        self.assertEqual(set(plt.get_fignums()), before)


class PresentationRegressionTests(unittest.TestCase):
    def test_categorical_groups_keep_labels_and_counts_in_comparison_chart(self):
        from valorant.ui.charts import dumbbell_chart

        table = pd.DataFrame(
            {
                "esperado_pelos_vivos": [0.2, 0.4],
                "defuse": [0.3, 0.5],
                "plants": [20, 35],
            },
            index=pd.CategoricalIndex(["cedo", "tarde"], ordered=True, name="faixa_tempo"),
        )
        before = table.copy(deep=True)
        chart = dumbbell_chart(
            table,
            "faixa_tempo",
            "esperado_pelos_vivos",
            "defuse",
            "comparação por vivos",
            "desarmes",
            "Desarmes",
            count_column="plants",
        )
        specification = chart.to_dict()
        self.assertIn("cedo (20)", str(specification))
        self.assertIn("tarde (35)", str(specification))
        pd.testing.assert_frame_equal(table, before)

    def test_translated_table_preserves_counts_and_formats_fraction_columns(self):
        from unittest.mock import Mock
        from valorant.ui.presentation import display_table

        table = pd.DataFrame({("colapsos", "ataque"): [5, 8], ("venceu", "ataque"): [0.25, 0.5]})
        before = table.copy(deep=True)
        receiver = Mock()
        display_table(table, container=receiver)
        shown = receiver.dataframe.call_args.args[0]
        config = receiver.dataframe.call_args.kwargs["column_config"]
        self.assertEqual([5, 8], shown.iloc[:, 0].tolist())
        self.assertEqual([0.25, 0.5], shown.iloc[:, 1].tolist())
        self.assertNotIn(shown.columns[0], config)
        self.assertEqual("percent", config[shown.columns[1]]["type_config"]["format"])
        pd.testing.assert_frame_equal(table, before)


if __name__ == "__main__":
    unittest.main()
