"""Revisão da partida conserva evidências, elegibilidade e rounds únicos."""

import unittest

import pandas as pd

from valorant.analysis.events import round_events
from valorant.analysis.fights import TRADE_POSSIBLE
from valorant.analysis.post_match import build_match_review

TEAMS = {
    f"{prefix}{index}": team
    for prefix, team in [("b", "Blue"), ("r", "Red")]
    for index in range(1, 4)
}


def kill(actor, victim, time, alive=None, *, positions=None):
    alive = list(TEAMS.keys() - {victim}) if alive is None else alive
    return {
        "killer": actor,
        "victim": victim,
        "timeSinceRoundStartMillis": time,
        "victimLocation": {"x": 0, "y": 0},
        "playerLocations": [
            {
                "puuid": player,
                "location": (positions or {}).get(player, {"x": 2000, "y": 0}),
                "viewRadians": 0,
            }
            for player in alive
        ],
        "assistants": [],
        "finishingDamage": {"damageType": "Weapon"},
    }


def round_result(kills=(), **overrides):
    result = {
        "roundNum": 0,
        "winningTeam": "Red",
        "winningTeamRole": "Defender",
        "roundResult": "Eliminated",
        "roundResultCode": "Elimination",
        "bombPlanter": None,
        "bombDefuser": None,
        "playerStats": [
            {"puuid": player, "kills": list(kills) if player == "b1" else []} for player in TEAMS
        ],
    }
    result.update(overrides)
    return result


def match(*results):
    return {
        "matchInfo": {"matchId": "m"},
        "players": [
            {"puuid": player, "teamId": team, "gameName": player.upper()}
            for player, team in TEAMS.items()
        ],
        "roundResults": [{**result, "roundNum": index} for index, result in enumerate(results)],
    }


def details(result, **extra):
    return pd.DataFrame(
        [
            {
                "match_id": "m",
                "round": 1,
                "event_id": event["event_id"],
                "regiao": "A",
                "aliados_mesma_regiao": True,
                "troca_possivel": TRADE_POSSIBLE,
                **extra,
            }
            for event in round_events(result, TEAMS)
            if event["kind"] == "kill"
        ]
    )


def pattern(review, team, pattern_id, player=None):
    table = review.pattern_summary(team, player)
    return table.loc[table["pattern_id"].eq(pattern_id)].iloc[0]


class PostMatchTests(unittest.TestCase):
    def test_multiple_patterns_keep_one_lost_round_and_evidence(self):
        result = round_result([kill("r1", "b1", 1000)])
        table = details(result)
        review = build_match_review(match(result), pd.concat([table, table]))
        rows = review.observations.query("player_id == 'b1'")
        self.assertEqual(4, len(rows))
        self.assertTrue((rows["event_index"] == 0).all())
        self.assertEqual(4, rows["observation_id"].nunique())
        player = review.player_summary("Blue").query("player_id == 'b1'").iloc[0]
        self.assertEqual(3, player.occurrences)
        self.assertEqual(1, player.rounds_with_observations)
        self.assertEqual(1, player.lost_round_count)
        self.assertEqual(1, pattern(review, "Blue", "isolated_death").lost_round_count)
        self.assertEqual(1, review.round_summary("Blue").won_round.eq(False).sum())

    def test_isolation_denominator_excludes_last_alive_and_missing_position(self):
        results = [
            round_result([kill("r1", "b1", 1000)]),
            round_result([kill("r1", "b1", 1000, ["r1", "r2", "r3"])]),
            round_result([kill("r1", "b1", 1000, [])]),
            round_result([kill("r1", "b1", 1000, positions={"b2": {"x": 100, "y": 0}})]),
        ]
        review = build_match_review(match(*results), pd.DataFrame())
        isolated = pattern(review, "Blue", "isolated_death", "b1")
        self.assertEqual(2, isolated.opportunities)
        self.assertEqual(1, isolated.occurrences)
        self.assertEqual(0.5, isolated.rate)

    def test_trade_is_assigned_to_actor_and_uses_kills_as_denominator(self):
        result = round_result(
            [
                kill("r1", "b1", 1000),
                kill("b2", "r1", 2000, ["b2", "b3", "r2", "r3"]),
                kill("b2", "r2", 9000, ["b2", "b3", "r3"]),
            ]
        )
        review = build_match_review(match(result), details(result))
        traded = pattern(review, "Blue", "trade_kill", "b2")
        self.assertEqual(2, traded.opportunities)
        self.assertEqual(1, traded.occurrences)
        self.assertEqual(0.5, traded.rate)
        observation = review.observations.query("pattern_id == 'trade_kill'").iloc[0]
        self.assertEqual("b2", observation.player_id)
        self.assertEqual("b1", observation.related_player_id)
        self.assertEqual(1, observation.event_index)
        self.assertEqual(0, pattern(review, "Blue", "isolated_opening_untraded").occurrences)

    def test_simultaneous_opening_has_no_individual_attribution_or_fake_advantage(self):
        result = round_result(
            [
                kill("b1", "r1", 1000),
                kill("r2", "b2", 1000),
            ]
        )
        review = build_match_review(match(result), details(result))
        self.assertFalse(review.opportunities["pattern_id"].eq("opening_kill").any())
        self.assertFalse(review.opportunities["pattern_id"].eq("numerical_advantage_lost").any())
        self.assertFalse(review.observations["pattern_id"].eq("isolated_opening_untraded").any())

    def test_resurrection_keeps_both_deaths_without_creating_three_distinct_victims(self):
        result = round_result(
            [
                kill("r1", "b1", 1000),
                kill("r2", "b2", 2000, ["b3", "r1", "r2", "r3"]),
                kill("r3", "b1", 3000, ["b3", "r1", "r2", "r3"]),
            ]
        )
        review = build_match_review(match(result), details(result))
        isolated = pattern(review, "Blue", "isolated_death", "b1")
        self.assertEqual(2, isolated.occurrences)
        self.assertEqual(2, isolated.opportunities)
        self.assertEqual(1, isolated.round_count)
        self.assertEqual(0, pattern(review, "Blue", "collapse").occurrences)
        b1_deaths = review.observations.query(
            "pattern_id == 'isolated_death' and player_id == 'b1'"
        )
        self.assertEqual([0, 2], list(b1_deaths.event_index))

    def test_after_decision_excluded_and_event_index_counts_plant(self):
        result = round_result(
            [kill("r1", "b1", 1000), kill("r2", "b2", 3000)],
            bombPlanter="b3",
            plantRoundTime=500,
            plantPlayerLocations=[
                {"puuid": player, "location": {"x": 2000, "y": 0}} for player in TEAMS
            ],
            plantLocation={"x": 0, "y": 0},
            bombDefuser="r3",
            defuseRoundTime=2000,
            defusePlayerLocations=[
                {"puuid": player, "location": {"x": 2000, "y": 0}}
                for player in TEAMS
                if player != "b1"
            ],
            roundResultCode="Defuse",
        )
        review = build_match_review(match(result), details(result))
        isolated = review.observations.query("pattern_id == 'isolated_death'")
        self.assertEqual([1], list(isolated.event_index))
        self.assertEqual(["b1"], list(isolated.player_id))
        self.assertEqual(1, review.round_summary("Blue").iloc[0].event_index)

    def test_empty_round_remains_and_zero_observation_summaries_work(self):
        result = round_result(winningTeamRole="unknown")
        review = build_match_review(match(result), pd.DataFrame())
        self.assertTrue(review.observations.empty)
        self.assertEqual(1, len(review.round_summary("Blue")))
        self.assertEqual(0, review.round_summary("Blue").iloc[0].occurrences)
        self.assertEqual("", review.round_summary("Blue").iloc[0].patterns)
        self.assertEqual(3, len(review.player_summary("Blue")))
        self.assertEqual(0, review.player_summary("Blue").lost_round_count.sum())
        self.assertEqual(0, pattern(review, "Blue", "collapse").occurrences)
        self.assertEqual(0, len(review.pattern_summary("Blue", "b1")))

    def test_equipment_and_no_plant_are_collective_context_only(self):
        result = round_result()
        rounds = pd.DataFrame(
            [
                {
                    "match_id": "m",
                    "round": 1,
                    "time": "Blue",
                    "loadout": 10000,
                    "loadout_adversario": 18000,
                }
            ]
        )
        review = build_match_review(match(result), pd.DataFrame(), rounds)
        contexts = review.observations
        self.assertEqual(
            {"lower_starting_equipment", "attack_without_plant"}, set(contexts.pattern_id)
        )
        self.assertTrue(contexts.context_only.all())
        self.assertTrue(contexts.player_id.isna().all())
        self.assertEqual(0, review.player_summary("Blue").occurrences.sum())

    def test_opening_team_rate_is_per_round_and_player_rate_uses_same_eligible_rounds(self):
        results = [
            round_result([kill("b1", "r1", 1000)]),
            round_result([kill("b2", "r1", 1000)]),
            round_result([kill("r2", "b1", 1000)]),
        ]
        review = build_match_review(match(*results), pd.DataFrame())
        team = pattern(review, "Blue", "opening_kill")
        player = pattern(review, "Blue", "opening_kill", "b1")
        self.assertEqual(3, team.opportunities)
        self.assertEqual(2, team.occurrences)
        self.assertAlmostEqual(2 / 3, team.rate)
        self.assertEqual(3, player.opportunities)
        self.assertEqual(1, player.occurrences)

    def test_collective_collapse_needs_three_different_people_and_no_answer(self):
        events = [
            kill("r1", "b1", 1000),
            kill("r2", "b2", 2000, ["b3", "r1", "r2", "r3"]),
            kill("r3", "b3", 3000, ["r1", "r2", "r3"]),
        ]
        result = round_result(events)
        review = build_match_review(match(result), details(result))
        collapsed = pattern(review, "Blue", "collapse")
        self.assertEqual(1, collapsed.occurrences)
        self.assertEqual(1, collapsed.lost_round_count)
        self.assertTrue(
            review.observations.query("pattern_id == 'collapse'").player_id.isna().all()
        )
        result = round_result([*events, kill("b3", "r2", 2500, ["b3", "r1", "r3"])])
        review = build_match_review(match(result), details(result))
        self.assertEqual(0, pattern(review, "Blue", "collapse").occurrences)

    def test_advantage_loss_and_recovery_count_once_per_round(self):
        result = round_result(
            [
                kill("b1", "r1", 1000),
                kill("r2", "b1", 2000, ["b2", "b3", "r2", "r3"]),
                kill("r2", "b2", 3000, ["b3", "r2", "r3"]),
            ],
            winningTeam="Blue",
            winningTeamRole="Attacker",
            roundResultCode="Detonate",
        )
        review = build_match_review(match(result), details(result))
        for team in ("Blue", "Red"):
            self.assertEqual(1, pattern(review, team, "numerical_advantage_lost").opportunities)
        lost = pattern(review, "Blue", "numerical_advantage_lost")
        self.assertEqual(1, lost.occurrences)
        self.assertEqual(0, lost.lost_round_count)
        evidence = review.observations.query(
            "pattern_id == 'numerical_advantage_lost' and team_id == 'Blue'"
        ).iloc[0]
        self.assertEqual(3000, evidence.time_ms, "The loss is the moment the team falls behind, not the tie")
        won = pattern(review, "Blue", "won_after_disadvantage")
        self.assertEqual(1, won.occurrences)
        self.assertTrue(won.positive)

    def test_traded_advantage_that_only_ties_is_not_a_loss(self):
        result = round_result(
            [
                kill("b1", "r1", 1000),
                kill("r2", "b1", 2000, ["b2", "b3", "r2", "r3"]),
                kill("b2", "r2", 3000, ["b2", "b3", "r3"]),
            ]
        )
        review = build_match_review(match(result), details(result))
        lost = pattern(review, "Blue", "numerical_advantage_lost")
        self.assertEqual(1, lost.opportunities)
        self.assertEqual(0, lost.occurrences)

    def test_advantage_loss_between_snapshots_keeps_first_evidence_after_revive(self):
        result = round_result(
            [
                kill("b1", "r1", 1000),
                # r1 reaparece e o estado anterior deste abate já é 3v3.
                kill("r2", "b1", 2000, ["b2", "b3", "r1", "r2", "r3"]),
                kill("b2", "r1", 3000, ["b2", "b3", "r2", "r3"]),
                kill("b2", "r2", 4000, ["b2", "b3", "r3"]),
                # A segunda perda de vantagem não cria outro round envolvido.
                kill("r3", "b2", 5000, ["b3", "r3"]),
            ]
        )
        review = build_match_review(match(result), details(result))
        lost = pattern(review, "Blue", "numerical_advantage_lost")
        self.assertEqual(1, lost.opportunities)
        self.assertEqual(1, lost.occurrences)
        self.assertEqual(1, lost.round_count)
        evidence = review.observations.query(
            "pattern_id == 'numerical_advantage_lost' and team_id == 'Blue'"
        ).iloc[0]
        self.assertEqual(1, evidence.event_index)
        self.assertEqual(2000, evidence.time_ms)
        self.assertEqual(3, evidence.allies_before)
        self.assertEqual(3, evidence.enemies_before)
        self.assertIn("ressurreição", evidence.description)

    def test_partial_ally_coordinates_do_not_prove_isolation(self):
        result = round_result(
            [kill("r1", "b1", 1000, positions={"b2": {"x": 3000, "y": 0}, "b3": {}})]
        )
        review = build_match_review(match(result), details(result))
        for pattern_id in ("isolated_death", "isolated_opening_untraded", "away_from_group"):
            self.assertFalse(review.opportunities.pattern_id.eq(pattern_id).any())
            self.assertFalse(review.observations.pattern_id.eq(pattern_id).any())

    def test_pattern_priority_uses_rate_after_unique_round_counts(self):
        results = [
            round_result(
                [
                    kill("b1", "r1", 1000),
                    kill("r2", "b1", 2000, ["b2", "b3", "r2", "r3"]),
                    kill("b2", "r2", 3000, ["b2", "b3", "r3"]),
                ]
            ),
            round_result([kill("r1", "b1", 1000)]),
            round_result([kill("r1", "b1", 1000)]),
        ]
        review = build_match_review(match(*results), pd.DataFrame())
        selected = review.pattern_summary("Blue").query(
            "pattern_id in ['trade_kill', 'opening_kill']"
        )
        self.assertEqual(["trade_kill", "opening_kill"], list(selected.pattern_id))
        self.assertEqual([1, 1], list(selected.lost_round_count))
        self.assertEqual([1, 1], list(selected.round_count))
        self.assertEqual([0.5, 1 / 3], list(selected.rate))

    def test_nearby_context_is_assigned_to_ally_and_denominator_includes_distant_cases(self):
        results = [
            round_result(
                [
                    kill(
                        "r1",
                        "b1",
                        1000,
                        positions={
                            "r1": {"x": 3000, "y": 0},
                            "b2": {"x": 2000, "y": 0},
                            "b3": {"x": 20000, "y": 0},
                        },
                    )
                ]
            ),
            round_result(
                [
                    kill(
                        "r1",
                        "b1",
                        1000,
                        positions={
                            "r1": {"x": 3000, "y": 0},
                            "b2": {"x": 10000, "y": 0},
                            "b3": {"x": 20000, "y": 0},
                        },
                    )
                ]
            ),
        ]
        review = build_match_review(match(*results), pd.DataFrame())
        context = pattern(review, "Blue", "nearby_ally_without_trade", "b2")
        self.assertEqual(2, context.opportunities)
        self.assertEqual(1, context.occurrences)
        self.assertEqual(0.5, context.rate)
        self.assertTrue(context.context_only)
        evidence = review.observations.query("pattern_id == 'nearby_ally_without_trade'").iloc[0]
        self.assertEqual("b2", evidence.player_id)
        self.assertEqual("b1", evidence.related_player_id)
        self.assertEqual(0, evidence.event_index)
        self.assertEqual(
            0, review.player_summary("Blue").query("player_id == 'b2'").iloc[0].occurrences
        )

    def test_nearby_context_requires_known_actor_position_and_ally_direction(self):
        result = round_result([kill("r1", "b1", 1000, positions={"r1": {}})])
        review = build_match_review(match(result), pd.DataFrame())
        self.assertFalse(review.opportunities.pattern_id.eq("nearby_ally_without_trade").any())
        result = round_result([kill("r1", "b1", 1000)])
        for location in result["playerStats"][0]["kills"][0]["playerLocations"]:
            location.pop("viewRadians")
        review = build_match_review(match(result), pd.DataFrame())
        self.assertFalse(review.opportunities.pattern_id.eq("nearby_ally_without_trade").any())

    def test_nearby_context_is_not_created_when_team_completes_trade(self):
        result = round_result(
            [
                kill("r1", "b1", 1000),
                kill("b2", "r1", 2000, ["b2", "b3", "r2", "r3"]),
            ]
        )
        review = build_match_review(match(result), pd.DataFrame())
        context = pattern(review, "Blue", "nearby_ally_without_trade", "b3")
        self.assertGreater(context.opportunities, 0)
        self.assertEqual(0, context.occurrences)

    def test_pattern_filter_preserves_rounds_without_matching_observation(self):
        result = round_result([kill("r1", "b1", 1000)])
        review = build_match_review(match(result, round_result()), details(result))
        rounds = review.round_summary("Blue", "b1", "isolated_death")
        self.assertEqual([1, 2], list(rounds["round"]))
        self.assertEqual([1, 0], list(rounds.occurrences))
        self.assertEqual(["Blue", "Blue"], list(rounds.team_id))


if __name__ == "__main__":
    unittest.main()
