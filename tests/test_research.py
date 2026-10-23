"""Contagens do ranking, exposição e separação entre eventos e padrões."""

from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

from valorant.analysis.research import (
    MATCH_TOTALS, review_events, summarize_review_match, team_ranking,
)


class ResearchTests(unittest.TestCase):
    def fixture(self):
        info = dict(match_id="one", arquivo="FIX_001_20-06-26_alpha_2_x_1_beta_ascent.json",
                    torneio="Cup", inicio=pd.Timestamp("2026-06-20"))
        match = dict(
            teams=[dict(teamId="Blue", roundsWon=2, won=True), dict(teamId="Red", roundsWon=1, won=False)],
            roundResults=[dict(winningTeam=team) for team in ["Blue", "Red", "Blue"]],
        )
        observations = pd.DataFrame([
            dict(team_id=team, round=number, event_index=event, pattern_id=pattern, won_round=True)
            for team, number, event, pattern in [
                ("Blue", 1, 0, "isolated_opening_untraded"), ("Blue", 1, 0, "numerical_advantage_lost"),
                ("Blue", 1, 1, "collapse"), ("Blue", 2, 0, "numerical_advantage_lost"),
                ("Red", 3, 0, "isolated_opening_untraded"), ("Blue", 1, 3, "opening_kill"),
                ("Blue", 2, None, "lower_starting_equipment"),
            ]
        ])
        opportunities = pd.DataFrame([
            dict(pattern_id="isolated_opening_untraded", team_id=team) for team in ["Blue", "Red"]
        ])
        rounds = pd.DataFrame([dict(team_id=team) for team in ["Blue", "Red"] * 3])
        review = SimpleNamespace(observations=observations, opportunities=opportunities, rounds=rounds)
        fights = pd.DataFrame([
            dict(time_vitima=team, diagnostico_tatico=True, aliados_vivos=1)
            for team in ["Blue"] * 4 + ["Red"] * 3
        ])
        return info, match, review, fights

    def test_overlapping_patterns_count_one_event_per_team_and_round(self):
        _, _, review, _ = self.fixture()
        events = review_events(review.observations)
        self.assertEqual(4, len(events))
        self.assertTrue(events["won_round"].all(), "Rounds vencidos também entram no ranking")
        self.assertNotIn("opening_kill", events["pattern_id"].tolist())
        self.assertNotIn("lower_starting_equipment", events["pattern_id"].tolist())
        repeated = pd.concat([
            review.observations.assign(match_id="one"), review.observations.assign(match_id="two")
        ], ignore_index=True)
        self.assertEqual(8, len(review_events(repeated)))

    def test_match_summary_matches_replay_counts_and_keeps_distinct_rounds(self):
        rows = summarize_review_match(*self.fixture())
        blue = next(row for row in rows if row["team_id"] == "Blue")
        self.assertEqual("alpha", blue["team_name"])
        self.assertEqual(3, blue["review_events"])
        self.assertEqual(2, blue["review_rounds"])
        self.assertEqual(3, blue["rounds"])
        self.assertEqual(2, blue["round_wins"])
        self.assertEqual(1, blue["match_wins"])
        self.assertEqual(4, blue["deaths"])

    def test_rates_pool_exposure_instead_of_averaging_match_percentages(self):
        first, second = summarize_review_match(*self.fixture())
        longer = {**first, "match_id": "two", "rounds": 9, "round_outcomes": 9,
                  "review_events": 9, "review_rounds": 6, "round_wins": 4}
        ranking = team_ranking(pd.DataFrame([first, second, longer]), 2)
        self.assertEqual(["alpha"], ranking["team_name"].tolist())
        alpha = ranking.iloc[0]
        self.assertEqual(12, alpha["review_events"])
        self.assertEqual(100, alpha["review_per_100"])
        self.assertEqual(.5, alpha["round_win_rate"])
        self.assertAlmostEqual(2 / 3, alpha["review_round_rate"])
        self.assertEqual(1, alpha["review_rank"])

    def test_unknown_outcomes_and_zero_exposure_are_unavailable(self):
        first, _ = summarize_review_match(*self.fixture())
        first.update({key: 0 for key in MATCH_TOTALS})
        first["matches"] = 1
        ranking = team_ranking(pd.DataFrame([first]), 1)
        self.assertTrue(np.isnan(ranking.iloc[0]["match_win_rate"]))
        self.assertTrue(np.isnan(ranking.iloc[0]["round_win_rate"]))
        self.assertTrue(np.isnan(ranking.iloc[0]["review_per_100"]))
        self.assertTrue(team_ranking(pd.DataFrame([first]), 3).empty)

    def test_undecided_match_is_not_recorded_as_two_losses(self):
        info, match, review, fights = self.fixture()
        for team in match["teams"]:
            team["won"] = False
        rows = summarize_review_match(info, match, review, fights)
        self.assertTrue(all(row["decided_matches"] == 0 for row in rows))
        self.assertTrue(all(row["matches"] == 1 for row in rows))


if __name__ == "__main__":
    unittest.main()
