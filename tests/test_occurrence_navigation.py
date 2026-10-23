"""Percurso de ocorrências entre rounds e retorno à visão de origem."""

import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from valorant.ui.post_match_occurrences import occurrence_neighbors


OCCURRENCE_APP = '''
from types import SimpleNamespace
import pandas as pd
import streamlit as st
from valorant.ui.post_match_selection import PostMatchSelection, jump_to_evidence
from valorant.ui.post_match_views import show_evidence

players = [
    dict(puuid=player, gameName=player.upper(), tagLine="teste", teamId=team)
    for player, team in [("a", "Blue"), ("b", "Blue"), ("x", "Red"), ("y", "Red")]
]
rounds = [
    dict(winningTeam=winner, playerStats=[dict(kills=[
        dict(killer="a", victim=victim, timeSinceRoundStartMillis=(index + 1) * 1000,
             victimLocation=dict(x=4, y=5), playerLocations=[])
        for index, victim in enumerate(["x", "y"])
    ])])
    for winner in ["Red", "Red", "Blue"]
]
rows = [
    dict(observation_id=identifier, team_id="Blue", player_id=player, player_name=player.upper(),
         pattern_id=pattern, pattern=pattern, round=round_number, event_index=event,
         time_ms=(event + 1) * 1000, won_round=round_number == 3, review_question="O que rever?")
    for identifier, player, pattern, round_number, event in [
        ("a1", "a", "opening_untraded", 1, 1),
        ("a2", "a", "opening_untraded", 2, 0),
        ("a3", "a", "opening_untraded", 3, 1),
        ("a4", "a", "other_pattern", 1, 1),
        ("b1", "b", "opening_untraded", 1, 0),
    ]
]
class Review:
    observations = pd.DataFrame(rows)
    def pattern_summary(self, team_id, player_id=None):
        observations = self.observations
        if player_id:
            observations = observations[observations.player_id == player_id]
        return observations.groupby(["pattern_id", "pattern"]).size().reset_index(name="occurrences")

class Data:
    def maps(self):
        return {}
    def match_table(self, *args):
        return pd.DataFrame(columns=["round", "event_id"])

match_id = st.selectbox("Partida de teste", ["first", "second"], key="fixture_match")
selection = PostMatchSelection(
    SimpleNamespace(data=Data()), pd.Series(dict(match_id=match_id)),
    dict(matchInfo=dict(matchId=match_id, mapId="fixture"), players=players, roundResults=rounds),
    "Blue", {"Blue": "Equipe azul"}, Review(),
)
if match_id == "second":
    selection.review.observations = selection.review.observations.iloc[:0]
if "review_view" not in st.session_state:
    st.session_state["review_view"] = "Jogadores"
view = st.radio("Visão pós-jogo", ["Equipe", "Jogadores", "Lances"], key="review_view")
if view == "Lances":
    show_evidence(selection)
else:
    player = st.selectbox("Jogador", ["a", "b"], key="pos_player") if view == "Jogadores" else "Todos"
    st.selectbox("Round para consultar", [1, 2, 3], key="overview_round")
    st.button("Rever os lances", key="fixture_review", on_click=jump_to_evidence,
              args=(selection, "opening_untraded", player))
    st.button("Rever como equipe", key="fixture_shared", on_click=jump_to_evidence,
              args=(selection, "all", "Todos"))
'''


class OccurrenceNavigationTests(unittest.TestCase):
    def make_app(self):
        app = AppTest.from_string(OCCURRENCE_APP, default_timeout=20).run()
        self.assertFalse(app.exception)
        return app

    def assert_occurrence(self, app, number, count, round_number, event_number):
        self.assertFalse(app.exception)
        self.assertEqual("a", app.selectbox(key="pos_player").value)
        self.assertEqual("opening_untraded", app.selectbox(key="review_pattern").value)
        self.assertEqual(round_number - 1, app.selectbox(key="pos_round").value)
        captions = [caption.value for caption in app.caption]
        self.assertIn(f"Ocorrência {number} de {count}", captions)
        self.assertIn(f"Evento {event_number} de 2", captions)

    def test_next_and_previous_change_round_and_event_without_losing_filters(self):
        app = self.make_app()
        app.button(key="fixture_review").click().run()
        self.assert_occurrence(app, 1, 3, 1, 2)
        self.assertTrue(app.button(key="review_previous_occurrence").disabled)
        app.button(key="review_next_occurrence").click().run()
        self.assert_occurrence(app, 2, 3, 2, 1)
        app.button(key="review_next_occurrence").click().run()
        self.assert_occurrence(app, 3, 3, 3, 2)
        self.assertTrue(app.button(key="review_next_occurrence").disabled)
        app.button(key="review_previous_occurrence").click().run()
        self.assert_occurrence(app, 2, 3, 2, 1)
        app.button(key="review_previous_occurrence").click().run()
        self.assert_occurrence(app, 1, 3, 1, 2)

    def test_back_restores_source_player_and_round_after_reviewing_as_team(self):
        app = self.make_app()
        app.selectbox(key="pos_player").select("b").run()
        app.selectbox(key="overview_round").select(3).run()
        app.button(key="fixture_shared").click().run()
        self.assertEqual("Todos", app.selectbox(key="pos_player").value)
        app.button(key="review_next_occurrence").click().run()
        app.selectbox(key="pos_player").select("a").run()
        app.button(key="review_return").click().run()
        self.assertFalse(app.exception)
        self.assertEqual("Jogadores", app.radio(key="review_view").value)
        self.assertEqual("b", app.selectbox(key="pos_player").value)
        self.assertEqual(3, app.selectbox(key="overview_round").value)
        self.assertTrue(app.selectbox(key="pos_player").proto.set_value)

    def test_back_restores_team_view_and_new_origin_replaces_old_one(self):
        app = self.make_app()
        app.button(key="fixture_review").click().run()
        app.button(key="review_return").click().run()
        app.radio(key="review_view").set_value("Equipe").run()
        app.selectbox(key="overview_round").select(2).run()
        app.button(key="fixture_review").click().run()
        self.assertIn("equipe", app.button(key="review_return").label)
        app.button(key="review_return").click().run()
        self.assertFalse(app.exception)
        self.assertEqual("Equipe", app.radio(key="review_view").value)
        self.assertEqual(2, app.selectbox(key="overview_round").value)

    def test_return_button_does_not_use_origin_from_another_match(self):
        app = self.make_app()
        app.button(key="fixture_review").click().run()
        app.selectbox(key="fixture_match").select("second").run()
        self.assertFalse(app.exception)
        self.assertNotIn("review_return", [button.key for button in app.button])
        self.assertTrue(app.button(key="review_previous_occurrence").disabled)
        self.assertTrue(app.button(key="review_next_occurrence").disabled)

    def test_single_occurrence_disables_both_directions(self):
        app = self.make_app()
        app.selectbox(key="pos_player").select("b").run()
        app.button(key="fixture_review").click().run()
        self.assertFalse(app.exception)
        self.assertIn("Ocorrência 1 de 1", [caption.value for caption in app.caption])
        self.assertTrue(app.button(key="review_previous_occurrence").disabled)
        self.assertTrue(app.button(key="review_next_occurrence").disabled)

    def test_manual_event_can_rejoin_occurrences_and_filter_change_updates_count(self):
        app = self.make_app()
        app.button(key="fixture_review").click().run()
        events = [button for button in app.button if button.key.startswith("postmatch_event_")]
        events[0].click().run()
        self.assertTrue(any("fora da sequência" in caption.value for caption in app.caption))
        app.button(key="review_next_occurrence").click().run()
        self.assert_occurrence(app, 1, 3, 1, 2)
        app.selectbox(key="review_pattern").select("all").run()
        self.assertIn("Ocorrência 1 de 4", [caption.value for caption in app.caption])
        app.button(key="review_next_occurrence").click().run()
        self.assertIn("Ocorrência 2 de 4", [caption.value for caption in app.caption])
        self.assertEqual(0, app.selectbox(key="pos_round").value)

    def test_neighbors_handle_empty_selection_and_events_between_occurrences(self):
        occurrences = pd.DataFrame([
            dict(observation_id="a", round=1, event_index=0, time_ms=1000, won_round=False),
            dict(observation_id="b", round=1, event_index=2, time_ms=3000, won_round=False),
        ])
        self.assertEqual((None, 0, 1), occurrence_neighbors(occurrences, 1, 1, 2000, False))
        self.assertEqual((None, None, None), occurrence_neighbors(occurrences.iloc[:0], 1, 0, 0, False))


if __name__ == "__main__":
    unittest.main()
