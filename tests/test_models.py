"""Regressões sintéticas de método, censura, identidade e estados empíricos."""

import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from valorant.analysis.economy import DIFF_BINS, DIFF_LABELS, second_round_cycle
from valorant.analysis.factors import (
    cluster_contrast,
    player_decisions,
    match_team_summary,
    ROUND_FACTORS,
    GOOD_ROUND_FACTORS,
)
from valorant.analysis.prediction import FEATURE_SIGNS, combined_score, forecast_accuracy
from valorant.analysis.state_reference import (
    build_state_table,
    match_win_added,
    round_win_added,
    state_probability,
    state_reference,
    _round_states,
)


class ModelTests(unittest.TestCase):
    def test_opposite_reference_is_complement_not_same_rate(self):
        table = {("defesa", 2, 3, "pré-plant"): 0.7}
        self.assertAlmostEqual(state_probability(table, "ataque", 3, 2, False), 0.3)
        self.assertTrue(math.isnan(state_probability({}, "ataque", 0, 1, True)))

    def test_no_cross_economy_or_time_fallback(self):
        table = {
            ("ataque", 3, 2, "pré-plant", "econ A", "pré: [0, 20) s"): {
                "probabilidade": 0.8,
                "rounds": 30,
                "partidas": 10,
                "ic_baixo": 0.6,
                "ic_alto": 0.9,
            }
        }
        self.assertTrue(
            math.isnan(
                state_reference(table, "ataque", 3, 2, False, "econ B", "pré: [0, 20) s")[
                    "probabilidade"
                ]
            )
        )
        self.assertTrue(
            math.isnan(
                state_reference(table, "ataque", 3, 2, False, "econ A", "pré: [20, 40) s")[
                    "probabilidade"
                ]
            )
        )

    def test_no_rounds_is_typed_empty_not_concat_failure(self):
        result = match_win_added({"players": [], "roundResults": []}, {}, {}, {})
        self.assertTrue(result.empty)
        self.assertIn("round", result)
        self.assertNotIn("ganho_do_autor", result)

    def test_snapshots_allow_resurrection_and_never_negative_alive(self):
        def kill(t, victim, alive):
            return {
                "timeSinceRoundStartMillis": t,
                "killer": "r",
                "victim": victim,
                "victimLocation": {"x": 0, "y": 0},
                "playerLocations": [{"puuid": p, "location": {"x": 0, "y": 0}} for p in alive],
                "assistants": [],
                "finishingDamage": {},
            }

        rr = {
            "winningTeam": "Red",
            "roundNum": 0,
            "playerStats": [
                {
                    "kills": [
                        kill(1000, "b", ["r", "b2"]),
                        kill(2000, "b2", ["r", "b"]),
                        kill(3000, "b", ["r"]),
                    ]
                }
            ],
            "bombPlanter": None,
            "bombDefuser": None,
        }
        result = round_win_added(rr, {"b": "Blue", "b2": "Blue", "r": "Red"}, "Blue", {}, "econ")
        self.assertEqual(result["estado"].tolist(), ["1v1", "1v1", "0v1"])
        self.assertNotIn("ganho_do_autor", result)

    def test_reference_excludes_selected_match(self):
        matches = {}
        for mid in ["selected", "other"]:
            players = [
                {"puuid": f"{color}{i}", "teamId": color, "isObserver": False}
                for color in ["Blue", "Red"]
                for i in range(5)
            ]
            matches[mid] = {
                "matchInfo": {"matchId": mid},
                "players": players,
                "roundResults": [
                    {
                        "roundNum": 0,
                        "winningTeam": "Blue",
                        "playerStats": [],
                        "bombPlanter": None,
                        "bombDefuser": None,
                    }
                ],
            }
        rounds = pd.DataFrame(
            [
                {"match_id": mid, "round": 1, "lado": "ataque", "faixa_diferenca": "econ"}
                for mid in matches
            ]
        )
        with patch(
            "valorant.analysis.state_reference.find_match_files", return_value=["selected", "other"]
        ), patch(
            "valorant.analysis.state_reference.load_match", side_effect=lambda p: matches[p]
        ), patch(
            "valorant.analysis.prediction.attacking_team_by_round", return_value={1: "Blue"}
        ):
            refs, _ = build_state_table(None, None, rounds, exclude_match_id="selected")
        self.assertEqual(len(refs), 1)
        self.assertEqual(next(iter(refs.values()))["rounds"], 1)
        self.assertTrue(math.isnan(next(iter(refs.values()))["probabilidade"]))

    def test_simultaneous_plant_and_kill_share_postplant_state(self):
        locations = [{"puuid": p, "location": {"x": 1, "y": 1}} for p in ["b1", "r1"]]
        rr = {
            "winningTeam": "Blue",
            "roundResult": "Bomb detonated",
            "roundNum": 0,
            "plantLocation": {"x": 1, "y": 1},
            "plantRoundTime": 20000,
            "plantPlayerLocations": locations,
            "bombPlanter": "b1",
            "bombDefuser": None,
            "playerStats": [
                {
                    "kills": [
                        {
                            "timeSinceRoundStartMillis": 20000,
                            "killer": "b1",
                            "victim": "r2",
                            "victimLocation": {"x": 0, "y": 0},
                            "playerLocations": locations,
                            "assistants": [],
                            "finishingDamage": {},
                        }
                    ]
                }
            ],
        }
        teams = {"b1": "Blue", "r1": "Red", "r2": "Red"}
        states = list(_round_states(rr, teams, "Blue", "econ"))
        self.assertEqual(states[-1][3], "pós-plant")
        self.assertEqual(states[-1][5], "pós: [0, 10) s")
        events = round_win_added(rr, teams, "Blue", {}, "econ")
        self.assertEqual(events["fase"].tolist(), ["pós-plant", "pós-plant"])
        self.assertEqual(events["estado"].nunique(), 1)

    def test_force_cycle_uses_complete_cohort_and_exposes_censoring(self):
        rows = []
        for mid, results in [
            ("complete", [False, True, True, False]),
            ("censored", [False, False]),
        ]:
            for number, won in enumerate(results, 13):
                rows.append(
                    {
                        "match_id": mid,
                        "time": "Blue",
                        "round": number,
                        "tipo": (
                            "pistol" if number == 13 else ("segundo" if number == 14 else "outro")
                        ),
                        "venceu_anterior": False,
                        "venceu": won,
                        "loadout": 9000,
                        "lado": "ataque",
                    }
                )
        table, _ = second_round_cycle(pd.DataFrame(rows))
        row = table.iloc[0]
        self.assertEqual(row["rounds"], 2)
        self.assertEqual(row["ciclos_completos"], 1)
        self.assertEqual(row["ciclos_censurados"], 1)
        self.assertEqual(row["rounds_ganhos_2_a_4"], 2)
        self.assertEqual(row["disponiveis_round_4"], 1)

    def test_exact_band_boundaries_are_explicit(self):
        labels = pd.cut(pd.Series([-10000, 10000, 10**7]), DIFF_BINS, labels=DIFF_LABELS)
        self.assertEqual(str(labels.iloc[0]), "≤ -10k")
        self.assertEqual(str(labels.iloc[1]), "(5k, 10k]")
        self.assertEqual(str(labels.iloc[2]), "> 10k")

    def test_victim_identity_prevents_simultaneous_flag_overwrite(self):
        flags = pd.DataFrame(
            [
                {
                    "segundos": 1.0,
                    "vitima": "b1",
                    "ordem_da_morte": 1,
                    "trocada": False,
                    "mais_caro_do_time": True,
                    "sem_reacao": True,
                },
                {
                    "segundos": 1.0,
                    "vitima": "b2",
                    "ordem_da_morte": 2,
                    "trocada": False,
                    "mais_caro_do_time": False,
                    "sem_reacao": False,
                },
            ]
        )
        events = [
            {"kind": "kill", "time_ms": 1000, "actor": "r", "victim": b, "locations": []}
            for b in ["b1", "b2"]
        ]
        teams = {"b1": "Blue", "b2": "Blue", "r": "Red"}
        first = player_decisions(events, teams, "b1", flags, {})
        second = player_decisions(events, teams, "b2", flags, {})
        self.assertIn("sem dano no autor registrado no round", [r["fator"] for r in first])
        self.assertNotIn("sem dano no autor registrado no round", [r["fator"] for r in second])
        self.assertTrue(all("custo" not in row for row in first))

    def test_team_summary_has_counts_without_summed_scores(self):
        row = {
            "match_id": "m",
            "time": "Blue",
            "venceu": True,
            **{column: True for _, _, column in GOOD_ROUND_FACTORS + ROUND_FACTORS},
        }
        table = match_team_summary(pd.DataFrame([row]), "m", {})
        self.assertNotIn("saldo", table)
        self.assertNotIn("pontos ganhos", table)
        self.assertEqual(table.iloc[0]["colapso"], 1)

    def test_cluster_bootstrap_preserves_match_units(self):
        frame = pd.DataFrame(
            {
                "match_id": ["a", "a", "b", "b"],
                "flag": [True, False, True, False],
                "won": [True, False, False, True],
            }
        )
        difference, low, high = cluster_contrast(frame, "flag", "won")
        self.assertEqual(difference, 0)
        self.assertLessEqual(low, difference)
        self.assertGreaterEqual(high, difference)

    def test_temporal_scale_has_no_future_and_baseline_uses_same_games(self):
        matches = pd.DataFrame(
            [{"match_id": str(i), "inicio": i * 1000, "venceu_blue": i % 2 == 0} for i in range(8)]
        )
        profiles = []
        for i in range(8):
            for team, sign in [("Blue", 1), ("Red", -1)]:
                profiles.append(
                    {
                        "match_id": str(i),
                        "time": team,
                        "outras": 3,
                        "taxa_vitoria_outras": 0.7 if team == "Blue" else (0.7 if i == 7 else 0.3),
                        **{
                            f: sign * (i + 1) * (0.01 if j % 2 else 0.02)
                            for j, f in enumerate(FEATURE_SIGNS)
                        },
                    }
                )
        with patch(
            "valorant.analysis.prediction.team_profiles_out_of_match",
            return_value=pd.DataFrame(profiles),
        ):
            result = forecast_accuracy(matches, pd.DataFrame(), True)
        combined = result[result["metrica"] == "combinada (abertura + troca)"].iloc[0]
        self.assertEqual(combined["partidas"], 4)  # first 3 lack scale; final baseline tie abstains
        self.assertTrue(pd.notna(combined["base_mesmos_jogos"]))
        self.assertEqual(combined["abstencoes_ou_sem_referencia"], 4)
        future = pd.DataFrame(profiles)
        future.loc[future["match_id"] == "7", list(FEATURE_SIGNS)] = 99999
        with patch("valorant.analysis.prediction.team_profiles_out_of_match", return_value=future):
            changed = forecast_accuracy(matches, pd.DataFrame(), True)
        self.assertEqual(
            combined["acerto"], changed[changed["metrica"] == combined["metrica"]].iloc[0]["acerto"]
        )

    def test_combined_headline_does_not_require_unused_features(self):
        data = pd.DataFrame({"abertura": [0.1, 0.2], "troca": [0.3, 0.4]})
        result = combined_score(data, ["abertura", "troca"])
        self.assertTrue(result.notna().all())


if __name__ == "__main__":
    unittest.main()
