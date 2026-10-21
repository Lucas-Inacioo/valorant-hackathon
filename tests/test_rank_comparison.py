"""Métricas de ordenação, empates, falta de informação e bootstrap por jogo."""

import math
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from valorant.analysis.rank_comparison import (
    bootstrap_comparison, compare_rankings, pairwise_concordance, spearman_correlation,
)
from valorant.analysis.research import MATCH_TOTALS, team_ranking


class RankComparisonTests(unittest.TestCase):
    def fixture(self):
        rows = []
        for match_id, participants in [
            ("ab", [("a", 1, 1), ("b", 3, 0)]),
            ("ac", [("a", 1, 1), ("c", 5, 0)]),
            ("bc", [("b", 3, 1), ("c", 5, 0)]),
        ]:
            for name, events, wins in participants:
                row = {key: 0 for key in MATCH_TOTALS}
                row.update(match_id=match_id, team_name=name, matches=1, decided_matches=1,
                           rounds=10, round_outcomes=10, round_wins=8 if wins else 2,
                           match_wins=wins, review_events=events)
                rows.append(row)
        matches = pd.DataFrame(rows)
        return matches, team_ranking(matches, 1)

    def test_spearman_uses_average_ranks_for_ties(self):
        self.assertAlmostEqual(1, spearman_correlation([1, 2, 3], [4, 5, 6]))
        self.assertAlmostEqual(-1, spearman_correlation([1, 2, 3], [6, 5, 4]))
        self.assertAlmostEqual(math.sqrt(.75), spearman_correlation([1, 1, 2], [1, 2, 3]))

    def test_fewer_reviews_and_more_wins_have_positive_agreement(self):
        _, ranking = self.fixture()
        result = compare_rankings(ranking)
        self.assertAlmostEqual(1, result.spearman)
        self.assertEqual(1, result.concordance)
        self.assertEqual(3, result.comparable_pairs)
        self.assertEqual(3, result.teams)

    def test_concordance_excludes_outcome_ties_and_half_counts_score_ties(self):
        value, pairs, tied_outcomes, tied_scores = pairwise_concordance([1, 1, 3], [1, 2, 3])
        self.assertEqual(3, pairs)
        self.assertEqual(0, tied_outcomes)
        self.assertEqual(1, tied_scores)
        self.assertAlmostEqual(2.5 / 3, value)
        self.assertEqual((1, 2, 1, 0), pairwise_concordance([1, 2, 3], [1, 1, 2]))

    def test_constant_missing_or_tiny_samples_do_not_invent_correlation(self):
        self.assertTrue(math.isnan(spearman_correlation([1, 2], [2, 1])))
        self.assertTrue(math.isnan(spearman_correlation([1, 1, 1], [1, 2, 3])))
        self.assertTrue(math.isnan(spearman_correlation([1, 2, np.inf], [1, 2, 3])))
        value, pairs, _, _ = pairwise_concordance([1, 2, 3], [1, 1, 1])
        self.assertTrue(math.isnan(value))
        self.assertEqual(0, pairs)
        empty = pd.DataFrame(columns=["review_per_100", "round_win_rate"])
        self.assertEqual(0, compare_rankings(empty).teams)

    def test_bootstrap_is_deterministic_and_stays_within_metric_ranges(self):
        matches, ranking = self.fixture()
        first = bootstrap_comparison(matches, ranking, repetitions=80)
        second = bootstrap_comparison(matches, ranking, repetitions=80)
        self.assertEqual(first, second)
        self.assertGreater(first.valid_resamples, 0)
        self.assertLessEqual(-1, first.spearman_low)
        self.assertGreaterEqual(1, first.spearman_high)
        self.assertLessEqual(0, first.concordance_low)
        self.assertGreaterEqual(1, first.concordance_high)

    def test_bootstrap_resamples_whole_matches_and_drops_unseen_teams(self):
        matches, ranking = self.fixture()
        generator = unittest.mock.Mock()
        generator.multinomial.return_value = np.array([[3, 0, 0], [1, 1, 1]])
        with patch("valorant.analysis.rank_comparison.np.random.default_rng", return_value=generator):
            result = bootstrap_comparison(matches, ranking, repetitions=2)
        self.assertEqual(1, result.valid_resamples)
        self.assertAlmostEqual(1, result.spearman_low)
        self.assertAlmostEqual(1, result.spearman_high)
        self.assertEqual(3, result.teams, "A coorte do valor pontual não muda com as reamostragens")


if __name__ == "__main__":
    unittest.main()
