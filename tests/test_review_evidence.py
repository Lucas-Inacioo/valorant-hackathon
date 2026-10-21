"""Bases das comparações, resultados ausentes e referência do recorte local."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from valorant.analysis.review_evidence import (
    defuse_survival_comparison, first_death_comparison, outcome_summary,
    pattern_round_comparison, pattern_round_groups, plant_time_comparison,
)


class ReviewEvidenceTests(unittest.TestCase):
    def test_trade_comparison_keeps_first_victim_team_and_excludes_other_matches(self):
        support = pd.DataFrame([
            dict(match_id=match, dist_aliado_mais_proximo=distance, trocada=trade, venceu_round=win)
            for match, distance, trade, win in [
                ("a", 1000, True, True), ("a", 1000, False, False),
                ("b", 1001, True, False), ("b", 1001, False, True),
                ("excluded", 10, False, True), ("a", np.nan, True, False),
            ]
        ])
        table, contrasts = first_death_comparison(SimpleNamespace(support_deaths=support), {"a", "b"})
        self.assertEqual([1, 1, 1, 1], table["Casos"].tolist())
        self.assertEqual([1, 0, 0, 1], table["Vitórias"].tolist())
        self.assertEqual(1, contrasts[0][1][0])
        self.assertEqual(-1, contrasts[1][1][0])
        local, _ = first_death_comparison(SimpleNamespace(support_deaths=support), {"a"})
        self.assertEqual([1, 1, 0, 0], local["Casos"].tolist())
        self.assertTrue(local.iloc[2:]["Vitória da equipe"].isna().all())

    def fixture(self):
        rounds = pd.DataFrame([
            dict(match_id="a", team_id=team, round=number, won_round=won)
            for team, number, won in [("Blue", 1, True), ("Red", 1, False),
                                      ("Blue", 2, False), ("Red", 2, True)]
        ])
        advantage = "numerical_advantage_lost"
        opportunities = pd.concat([
            rounds.assign(pattern_id="collapse"),
            rounds.iloc[[0, 2, 3]].assign(pattern_id=advantage),
        ], ignore_index=True)
        # Two flags in the same team-round must still count one round.
        observations = pd.DataFrame([
            dict(match_id="a", team_id=team, round=number, pattern_id=pattern)
            for team, number, pattern in [("Blue", 1, advantage), ("Blue", 1, advantage),
                                          ("Blue", 2, "collapse"), ("Red", 1, "collapse")]
        ])
        return SimpleNamespace(team_rounds=rounds, observations=observations, opportunities=opportunities)

    def test_advantage_comparison_only_includes_rounds_that_had_advantage(self):
        data = self.fixture()
        table, _ = pattern_round_comparison(data, {"a"}, "numerical_advantage_lost")
        self.assertEqual([1, 2], table["Casos"].tolist())
        self.assertEqual([1, 1], table["Vitórias"].tolist())
        self.assertEqual([0, 1], table["Derrotas"].tolist())
        groups = pattern_round_groups(data, {"a"}, "numerical_advantage_lost")
        self.assertFalse(((groups.team_id == "Red") & (groups["round"] == 1)).any())

    def test_collapse_counts_each_team_round_once_and_keeps_opponent_separate(self):
        data = self.fixture()
        table, contrast = pattern_round_comparison(data, {"a"}, "collapse")
        self.assertEqual([2, 2], table["Casos"].tolist())
        self.assertEqual([0, 2], table["Vitórias"].tolist())
        self.assertEqual(-1, contrast[0])
        self.assertTrue(np.isnan(contrast[1]), "One match cannot support a between-match interval")
        empty, _ = pattern_round_comparison(data, {"other"}, "collapse")
        self.assertEqual([0, 0], empty["Casos"].tolist())

    def test_unknown_outcomes_are_not_losses(self):
        summary = outcome_summary(pd.DataFrame(dict(match_id=["a"] * 3, won=[True, False, None])), "won")
        self.assertEqual(3, summary["Casos"])
        self.assertEqual(2, summary["Com resultado"])
        self.assertEqual(1, summary["Derrotas"])
        self.assertEqual(.5, summary["Vitória da equipe"])

    def test_plant_reference_is_recomputed_for_same_alive_counts_in_selected_data(self):
        plants = pd.DataFrame([
            dict(match_id=match, plant_valido=valid, ataque_vivos=attack, defesa_vivos=defense,
                 segundos_plant=time, ataque_venceu=won, esperado_vitoria_vivos=0)
            for match, valid, attack, defense, time, won in [
                ("a", True, 4, 4, 40, True), ("a", True, 4, 4, 41, False),
                ("b", True, 4, 3, 20, True), ("b", False, 4, 4, 41, True),
            ]
        ])
        table = plant_time_comparison(plants)
        self.assertEqual([2, 1], table["Plants"].tolist())
        self.assertEqual([1, 0], table["Vitória do ataque"].tolist())
        self.assertEqual([.75, .5], table["Referência por jogadores vivos"].tolist())
        local = plant_time_comparison(plants[plants.match_id.eq("a")])
        self.assertEqual([.5, .5], local["Referência por jogadores vivos"].tolist())

    def test_defuse_fraction_uses_only_valid_defused_plants_and_keeps_missing_explicit(self):
        setups = pd.DataFrame([
            dict(match_id="a", plant_valido=valid, defusada=defused, atacantes_vivos_no_defuse=alive)
            for valid, defused, alive in [(True, True, 0), (True, True, 2), (True, True, np.nan),
                                         (True, False, 0), (False, True, 0)]
        ])
        table = defuse_survival_comparison(setups)
        self.assertEqual([1, 1, 1], table["Desarmes"].tolist())
        np.testing.assert_allclose(table["Fração dos desarmes"], [1 / 3] * 3)

    def test_example_navigation_restores_filters_after_dashboard_widgets_are_removed(self):
        from valorant.ui.post_match_selection import open_dashboard_evidence, return_from_evidence

        state = dict(dashboard_tournament="Cup", dashboard_example_outcome="Rounds vencidos",
                     dashboard_examples=True, dashboard_example="match|occurrence", dashboard_open_example=True,
                     dashboard_example_team="Equipe de teste")
        observation = dict(match_id="match", team_id="Red", observation_id="occurrence",
                           pattern_id="collapse", round=8, event_index=3)
        with patch("valorant.ui.post_match_selection.st", SimpleNamespace(session_state=state)):
            open_dashboard_evidence("match.json", observation)
            self.assertEqual(("match", "Red"), state["review_scope"])
            self.assertEqual(7, state["pos_round"])
            self.assertEqual(3, state["review_event_focus"]["event_index"])
            self.assertEqual("Lances", state["review_view"])
            self.assertNotIn("dashboard_open_example", state["review_return_to"]["state"])
            for key in list(state):
                if key.startswith("dashboard_"):
                    del state[key]
            return_from_evidence(SimpleNamespace(match_id="match", team_id="Red"))
            self.assertEqual("Dashboard da pesquisa", state["section"])
            self.assertEqual("Cup", state["dashboard_tournament"])
            self.assertEqual("Rounds vencidos", state["dashboard_example_outcome"])
            self.assertEqual("Equipe de teste", state["dashboard_example_team"])
            self.assertTrue(state["dashboard_examples"])


if __name__ == "__main__":
    unittest.main()
