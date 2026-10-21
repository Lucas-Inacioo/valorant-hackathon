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

    def test_round_map_has_no_player_labels_and_legend_stays_outside_map(self):
        events = [
            {
                "kind": "kill",
                "actor": "a",
                "victim": "b",
                "time_ms": 12000,
                "victim_location": {"x": 10, "y": 20},
                "locations": [{"puuid": "a", "location": {"x": 1, "y": 2}}],
                "alive_after": ["a"],
            }
        ]
        figure = round_map.draw_round_map(
            self.meta,
            events,
            0,
            "a",
            {"a": "Blue", "b": "Red"},
            {"a": "Um nome de jogador muito longo", "b": "Outro nome muito longo"},
        )
        axes = figure.axes[0]
        self.assertEqual([], list(axes.texts))
        self.assertIsNone(axes.get_legend())
        self.assertEqual(1, len(figure.legends))
        figure.canvas.draw()
        legend_box = figure.legends[0].get_window_extent()
        map_box = axes.get_window_extent()
        self.assertLess(legend_box.y1, map_box.y0)
        self.assertEqual([], list(axes.lines))

    def test_simultaneous_killer_and_victim_keep_both_roles_without_duplicate_player(self):
        events = [
            {
                "kind": "kill",
                "actor": "a",
                "victim": "b",
                "time_ms": 1000,
                "victim_location": {"x": 2, "y": 3},
                "locations": [{"puuid": "c", "location": {"x": 7, "y": 8}}],
                "alive_after": ["c"],
            },
            {
                "kind": "kill",
                "actor": "b",
                "victim": "a",
                "time_ms": 1000,
                "victim_location": {"x": 4, "y": 5},
                "locations": [{"puuid": "c", "location": {"x": 7, "y": 8}}],
                "alive_after": ["c"],
            },
        ]
        with patch("valorant.ui.round_map.draw_player", wraps=round_map.draw_player) as draw:
            round_map.draw_round_map(
                self.meta,
                events,
                0,
                "a",
                {"a": "Blue", "b": "Red", "c": "Blue"},
                {"a": "A", "b": "B", "c": "C"},
            )
        calls = {call.args[4]: call for call in draw.call_args_list}
        self.assertEqual(3, len(draw.call_args_list))
        for name in ["A", "B"]:
            self.assertFalse(calls[name].kwargs["alive"])
            self.assertTrue(calls[name].kwargs["is_killer"])
            self.assertTrue(calls[name].kwargs["is_victim"])

    def test_missing_killer_position_is_not_invented_and_environment_has_no_killer_marker(self):
        events = [
            {
                "kind": "kill",
                "actor": "a",
                "victim": "b",
                "time_ms": 1000,
                "victim_location": {"x": 2, "y": 3},
                "locations": [],
                "alive_after": ["a"],
            }
        ]
        teams, names = {"a": "Blue", "b": "Red"}, {"a": "A", "b": "B"}
        with patch("valorant.ui.round_map.draw_player", wraps=round_map.draw_player) as draw:
            round_map.draw_round_map(self.meta, events, 0, "a", teams, names)
        self.assertEqual(["B"], [call.args[4] for call in draw.call_args_list])
        events[0]["finishing"] = {"damageType": "Bomb"}
        events[0]["locations"] = [{"puuid": "a", "location": {"x": 5, "y": 6}}]
        with patch("valorant.ui.round_map.draw_player", wraps=round_map.draw_player) as draw:
            round_map.draw_round_map(self.meta, events, 0, "a", teams, names)
        self.assertFalse(any(call.kwargs["is_killer"] for call in draw.call_args_list))
        self.assertIn("explosão da spike", round_map.describe_event(events[0], names, {}))

    def test_team_view_does_not_mark_an_arbitrary_selected_player(self):
        events = [
            {
                "kind": "plant",
                "locations": [{"puuid": "a", "location": {"x": 2, "y": 3}}],
                "alive_after": ["a"],
            }
        ]
        with patch("valorant.ui.round_map.draw_player", wraps=round_map.draw_player) as draw:
            figure = round_map.draw_round_map(
                self.meta,
                events,
                0,
                "a",
                {"a": "Blue"},
                {"a": "A"},
                highlight_selected=False,
            )
        self.assertFalse(draw.call_args.args[5])
        self.assertNotIn("jogador escolhido", [text.get_text() for text in figure.legends[0].texts])


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

        table = pd.DataFrame({("colapsos", "ataque"): [2972, 3565], ("venceu", "ataque"): [0.25, 0.5]})
        before = table.copy(deep=True)
        receiver = Mock()
        display_table(table, container=receiver)
        shown = receiver.dataframe.call_args.args[0]
        config = receiver.dataframe.call_args.kwargs["column_config"]
        self.assertEqual([2972, 3565], shown.iloc[:, 0].tolist())
        self.assertEqual([0.25, 0.5], shown.iloc[:, 1].tolist())
        self.assertIsNone(config[shown.columns[0]]["type_config"].get("format"))
        self.assertEqual(1, config[shown.columns[0]]["type_config"]["step"])
        self.assertEqual("percent", config[shown.columns[1]]["type_config"]["format"])
        self.assertEqual(0.001, config[shown.columns[1]]["type_config"]["step"])
        pd.testing.assert_frame_equal(table, before)

    def test_table_rounds_before_streamlit_truncates_the_decimals(self):
        from unittest.mock import Mock
        from valorant.ui.presentation import display_table

        table = pd.DataFrame({"mortes": [2972.0, 3564.9999999999995], "trocada": [0.30521, 0.11394]})
        receiver = Mock()
        display_table(table, container=receiver)
        shown = receiver.dataframe.call_args.args[0]
        self.assertEqual([2972.0, 3565.0], shown.iloc[:, 0].tolist())
        self.assertEqual([0.305, 0.114], shown.iloc[:, 1].tolist())

    def test_rates_stored_as_objects_are_shown_as_percentages(self):
        from unittest.mock import Mock
        from valorant.ui.presentation import display_table

        table = pd.DataFrame({"vitoria": pd.Series([0.37350, 1], dtype=object), "trocada": pd.Series([True, False], dtype=object)})
        receiver = Mock()
        display_table(table, container=receiver, percentage_columns=["vitoria"])
        shown = receiver.dataframe.call_args.args[0]
        config = receiver.dataframe.call_args.kwargs["column_config"]
        self.assertEqual([0.374, 1.0], shown.iloc[:, 0].tolist())
        self.assertEqual("percent", config[shown.columns[0]]["type_config"]["format"])
        self.assertEqual([True, False], shown.iloc[:, 1].tolist())

    def test_number_step_rounds_counts_and_keeps_two_decimals_for_small_values(self):
        from valorant.ui.presentation import number_step

        self.assertEqual(1, number_step(pd.Series([2972.0, 3564.9999999999995])))
        self.assertEqual(1, number_step(pd.Series([18765.4, 22500.0])))
        self.assertEqual(0.01, number_step(pd.Series([1.25, 45.3, float("nan")])))
        self.assertEqual(1, number_step(pd.Series([float("nan")])))


if __name__ == "__main__":
    unittest.main()
