"""Regressões de eventos táticos, empates e snapshots com ressurreição."""
import copy
import math
import unittest
from pathlib import Path

import pandas as pd

from agent_roles import SIDE_ROLE_INDEX, death_cost_by_role, first_death_by_role
from first_blood import first_blood_table, summary_by_map, wilson_interval
from match_events import (alive_before_puuids, alive_puuids, final_alive_puuids,
                          is_enemy_kill, round_events, was_traded)
from round_style import build_round_styles, collapse_of, collapse_rows, team_profiles
from solo_deaths import (DEATH_COLUMNS, allies_context, death_rows,
                         win_rate_by_situation, with_solo_flag, early_positions)

TEAMS = {"b1": "Blue", "b2": "Blue", "r1": "Red", "r2": "Red"}


def locations(*ids):
    return [{"puuid": puuid, "location": {"x": index * 100, "y": 0}} for index, puuid in enumerate(ids)]


def kill(actor, victim, time, alive, damage_type="Weapon"):
    return {"killer": actor, "victim": victim, "timeSinceRoundStartMillis": time,
            "victimLocation": {"x": 1000, "y": 0}, "playerLocations": locations(*alive),
            "assistants": [], "finishingDamage": {"damageType": damage_type}}


def round_result(kills, **overrides):
    result = {"roundNum": 0, "winningTeam": "Blue", "winningTeamRole": "Attacker",
              "roundResult": "Eliminated", "roundResultCode": "Elimination",
              "bombPlanter": None, "bombDefuser": None, "plantRoundTime": 0,
              "defuseRoundTime": 0, "plantPlayerLocations": [], "defusePlayerLocations": [],
              "playerStats": [{"puuid": "b1", "kills": kills}]}
    result.update(overrides)
    return result


def match(rr):
    return {"matchInfo": {"matchId": "m", "mapId": "/Game/map"}, "roundResults": [rr],
            "players": [{"puuid": puuid, "teamId": team, "characterId": "agent"} for puuid, team in TEAMS.items()],
            "teams": [{"teamId": "Blue", "won": True, "roundsWon": 2, "roundsPlayed": 3},
                      {"teamId": "Red", "won": False, "roundsWon": 1, "roundsPlayed": 3}]}


def deaths(rr):
    frame = pd.DataFrame(death_rows(match(rr), Path("test.json")), columns=DEATH_COLUMNS)
    frame["funcao"], frame["agente"] = "duelista", "agent"
    return frame


class EventTests(unittest.TestCase):
    def test_order_ids_are_stable_and_input_is_untouched(self):
        a = kill("b1", "r1", 1000, ["b1", "b2", "r2"])
        b = kill("r2", "b2", 1000, ["b1", "r1", "r2"])
        rr = round_result([])
        rr["playerStats"] = [{"kills": [a]}, {"kills": [b]}]
        before = copy.deepcopy(rr)
        events = round_events(rr, TEAMS)
        reverse = copy.deepcopy(rr)
        reverse["playerStats"].reverse()
        self.assertEqual(events, round_events(reverse, TEAMS))
        self.assertEqual(before, rr)
        self.assertEqual([0, 1], [event["index"] for event in events])
        self.assertEqual(2, len({event["event_id"] for event in events}))
        self.assertEqual(a["playerLocations"], next(e for e in events if e["victim"] == "r1")["locations"])

    def test_simultaneous_victims_share_a_state_without_arbitrary_order(self):
        rr = round_result([kill("b1", "r1", 1000, ["b1", "b2", "r2"]),
                           kill("r2", "b2", 1000, ["b1", "r1", "r2"])])
        events = round_events(rr, TEAMS)
        for event in events:
            self.assertEqual(set(TEAMS), alive_before_puuids(event))
            self.assertEqual({"b1", "r2"}, alive_puuids(event))
            self.assertTrue(event["simultaneous"])

    def test_snapshot_resurrection_restores_survivor(self):
        rr = round_result([kill("b1", "r1", 1000, ["b1", "b2", "r2"]),
                           kill("r2", "b2", 2000, ["b1", "r1", "r2"])])
        self.assertIn("r1", final_alive_puuids(rr, TEAMS))
        self.assertIn("r1", alive_before_puuids(round_events(rr, TEAMS)[1]))

    def test_post_defuse_events_remain_visible_but_not_tactical(self):
        rr = round_result([kill("b1", "r1", 2500, ["b1", "b2", "r2"])],
                          bombDefuser="b2", defuseRoundTime=2000,
                          defusePlayerLocations=locations(*TEAMS),
                          roundResult="Bomb defused", roundResultCode="Defuse")
        events = round_events(rr, TEAMS)
        self.assertEqual(["defuse", "kill"], [e["kind"] for e in events])
        self.assertTrue(events[1]["after_decision"])
        self.assertFalse(events[1]["tactical_valid"])

    def test_plant_validity_is_shared_without_arbitrary_timer_guess(self):
        rr = round_result([], bombPlanter="b1", plantRoundTime=100500,
                          plantPlayerLocations=locations(*TEAMS), plantLocation={"x": 100, "y": 100},
                          roundResult="Bomb detonated", roundResultCode="Detonate")
        event = round_events(rr, TEAMS)[0]
        self.assertTrue(event["plant_valid"])
        rr["roundResult"] = "Round timer expired"
        event = round_events(rr, TEAMS)[0]
        self.assertFalse(event["plant_valid"])
        self.assertIn("round encerrado por tempo", event["plant_exclusion"])
        rr["roundResult"] = "Eliminated"
        rr["plantPlayerLocations"] = locations("b1", "b2")
        event = round_events(rr, TEAMS)[0]
        self.assertFalse(event["plant_valid"])
        self.assertIn("plant sem defensor vivo", event["plant_exclusion"])

    def test_post_elimination_plant_is_flagged(self):
        rr = round_result([kill("b1", "r1", 1000, ["b1", "b2", "r2"]),
                           kill("b1", "r2", 2000, ["b1", "b2"])],
                          bombPlanter="b1", plantRoundTime=3000,
                          plantPlayerLocations=locations("b1", "b2"))
        events = round_events(rr, TEAMS)
        self.assertTrue(events[-1]["after_decision"])
        self.assertFalse(events[1]["after_decision"])

    def test_observed_bomb_damage_proves_detonation_before_later_kill(self):
        rr = round_result([kill("r1", "r1", 83000, ["b1", "b2", "r2"], "Bomb"),
                           kill("b1", "r2", 85000, ["b1", "b2"])],
                          roundResult="Bomb detonated", roundResultCode="Detonate")
        events = round_events(rr, TEAMS)
        self.assertEqual(83000, events[-1]["decision_time_ms"])
        self.assertTrue(events[-1]["after_decision"])
        self.assertFalse(events[-1]["tactical_valid"])

    def test_territory_uses_one_snapshot_with_victim_per_round(self):
        rr = round_result([kill("b1", "r1", 1000, ["b1", "b2", "r2"]),
                           kill("r2", "b2", 2000, ["b1", "r2"])])
        metadata = {"callouts": [{"superRegionName": "A", "regionName": "Site", "location": {"x": 0, "y": 0}}]}
        observed = list(early_positions(match(rr), metadata, rr))
        self.assertEqual(4, len(observed))
        self.assertEqual(2, sum(side == "defesa" for _, side in observed))
        self.assertEqual(2, sum(side == "ataque" for _, side in observed))

    def test_unknown_timer_does_not_invent_a_cutoff(self):
        rr = round_result([kill("b1", "r1", 123456, ["b1", "b2", "r2"])],
                          roundResult="Round timer expired", roundResultCode="")
        self.assertIsNone(round_events(rr, TEAMS)[0]["decision_time_ms"])

    def test_environment_and_friendly_deaths_are_not_enemy_kills(self):
        for damage in ["Bomb", "Fall", "Crush"]:
            event = round_events(round_result([kill("b1", "r1", 1000, ["b1", "b2", "r2"], damage)]), TEAMS)[0]
            self.assertFalse(is_enemy_kill(event, TEAMS))
        event = round_events(round_result([kill("r1", "r1", 1000, ["b1", "b2", "r2"], "Ability")]), TEAMS)[0]
        self.assertFalse(event["tactical_valid"])

    def test_trade_requires_enemy_actor_and_accepts_simultaneous_order(self):
        initial = kill("b1", "r1", 1000, ["b1", "b2", "r2"])
        bomb = kill("b1", "b1", 2000, ["b2", "r2"], "Bomb")
        events = round_events(round_result([initial, bomb]), TEAMS)
        self.assertFalse(was_traded(events[0], events, TEAMS))
        simultaneous = kill("r2", "b1", 1000, ["b2", "r1", "r2"])
        events = round_events(round_result([initial, simultaneous]), TEAMS)
        self.assertTrue(all(was_traded(e, events, TEAMS) for e in events if e["actor"] == "b1"))
        frame = deaths(round_result([initial, simultaneous]))
        self.assertTrue(frame.loc[frame["killer"] == "b1", "trade_simultaneous"].iloc[0])

    def test_environmental_first_death_does_not_assign_an_opponent_opening(self):
        frame = deaths(round_result([kill("r1", "r1", 500, ["b1", "b2", "r2"], "Fall"),
                                     kill("r2", "b2", 1000, ["b1", "r2"])]))
        first = first_blood_table(frame)
        self.assertEqual(1, len(first))
        self.assertEqual("Red", first.iloc[0]["time_abriu"])
        self.assertEqual(1, first.iloc[0]["segundos"])
        self.assertFalse(first.iloc[0]["venceu_partida"])

    def test_opposing_simultaneous_openings_are_counted_and_excluded(self):
        frame = deaths(round_result([kill("b1", "r1", 1000, ["b1", "b2", "r2"]),
                                     kill("r2", "b2", 1000, ["b1", "r1", "r2"])]))
        first = first_blood_table(frame)
        self.assertTrue(first.empty)
        self.assertEqual(1, first.attrs["rounds_abertura_ambigua"])
        self.assertFalse(frame["primeira_vitima_unica"].any())

    def test_same_team_simultaneous_opening_has_no_arbitrary_location(self):
        frame = deaths(round_result([kill("b1", "r1", 1000, ["b1", "b2", "r2"]),
                                     kill("b2", "r2", 1000, ["b1", "b2", "r1"])]))
        first = first_blood_table(frame)
        self.assertEqual(1, len(first))
        self.assertEqual("Blue", first.iloc[0]["time_abriu"])
        self.assertTrue(pd.isna(first.iloc[0]["vitima_x"]))

    def test_slider_recomputes_context_and_one_ally_is_not_a_group(self):
        frame = deaths(round_result([kill("r1", "b1", 1000, ["b2", "r1", "r2"])]))
        frame["aliados_mesma_regiao"] = True
        frame["aliados_vivos"] = 2
        self.assertEqual("em grupo", with_solo_flag(frame, 2000).iloc[0]["contexto"])
        self.assertEqual("flanco", with_solo_flag(frame, 500).iloc[0]["contexto"])
        self.assertEqual("isolado", allies_context({"x": 0, "y": 0}, [{"x": 2000, "y": 0}], ["A"]))

    def test_empty_filters_and_missing_roles_keep_their_schemas(self):
        frame = deaths(round_result([]))
        self.assertEqual(["lado", "situacao", "mortes", "sem", "com", "diferenca"], list(win_rate_by_situation(with_solo_flag(frame, 500), "trocada").columns))
        self.assertTrue(summary_by_map(first_blood_table(frame)).empty)
        self.assertEqual(SIDE_ROLE_INDEX.tolist(), first_death_by_role(frame).index.tolist())
        self.assertTrue(first_death_by_role(frame)["ic95_baixo"].isna().all())
        self.assertEqual(8, len(death_cost_by_role(with_solo_flag(frame, 500))))
        self.assertTrue(all(math.isnan(value) for value in wilson_interval(math.nan, math.nan)))


class StyleTests(unittest.TestCase):
    def test_collapse_requires_distinct_victims_and_marks_mixed_regions(self):
        table = pd.DataFrame({"segundos": [1, 2, 3], "vitima": ["a", "b", "a"],
                              "regiao": ["A", "B", "C"], "fase": ["pré-plant"] * 3,
                              "diagnostico_tatico": [True] * 3})
        self.assertFalse(collapse_of(table, [])["colapso"])
        table.loc[2, "vitima"] = "c"
        result = collapse_of(table, [])
        self.assertTrue(result["colapso"])
        self.assertEqual("múltiplas regiões", result["regiao_colapso"])
        table["diagnostico_tatico"] = False
        self.assertFalse(collapse_of(table, [])["colapso"])

    def test_three_with_an_enemy_kill_is_a_separate_count(self):
        table = pd.DataFrame({"segundos": [1, 2, 3], "vitima": ["a", "b", "c"],
                              "regiao": ["A"] * 3, "fase": ["pré-plant"] * 3})
        result = collapse_of(table, [2.5])
        self.assertTrue(result["tres_em_10s"])
        self.assertTrue(result["tres_com_abate"])
        self.assertFalse(result["colapso"])

    def test_invalid_raw_plant_is_not_labeled_as_a_tactical_style(self):
        table = pd.DataFrame([{"match_id": "m", "round": 1, "time": "Blue", "lado": "ataque",
                               "venceu": True, "mapa": "map", "segundos_plant": 30.0, "plant_valido": False}])
        names = pd.DataFrame([{"match_id": "m", "nome_blue": "Blue", "nome_red": "Red"}])
        result = build_round_styles(deaths(round_result([])), table, names)
        self.assertEqual("plant excluído", result.iloc[0]["estilo"])

    def test_plant_style_is_available_without_any_deaths(self):
        table = pd.DataFrame([{"match_id": "m", "round": 1, "time": "Blue", "lado": "ataque",
                               "venceu": True, "mapa": "map", "segundos_plant": 30.0}])
        names = pd.DataFrame([{"match_id": "m", "nome_blue": "Blue", "nome_red": "Red"}])
        result = build_round_styles(deaths(round_result([])), table, names)
        self.assertEqual("execução rápida", result.iloc[0]["estilo"])
        self.assertEqual("sem abate adversário", result.iloc[0]["contato"])
        self.assertFalse(result.iloc[0]["colapso"])
        self.assertTrue(team_profiles(result, min_attack_rounds=100).empty)


if __name__ == "__main__":
    unittest.main()
