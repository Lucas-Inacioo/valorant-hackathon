"""Navegação do replay sem depender dos arquivos completos da base."""

import unittest

from streamlit.testing.v1 import AppTest

REPLAY_APP = """
import pandas as pd
import streamlit as st
from valorant.ui.replay import RecordedRound, render_event_buttons, render_recorded_event

match_id = st.selectbox("Partida de teste", ["primeira", "segunda"], key="fixture_match")
round_index = st.selectbox("Round de teste", [0, 1, 2], key="fixture_round")
initial = st.number_input("Lance inicial", min_value=0, value=0, key="fixture_initial")
players = [
    dict(puuid=name, gameName=name.upper(), tagLine="teste", teamId=team)
    for name, team in [("a", "Blue"), ("b", "Red"), ("c", "Red"), ("d", "Red")]
]
locations = [dict(puuid="a", location=dict(x=1, y=2))]
kills = [
    dict(killer="a", victim=victim, timeSinceRoundStartMillis=(index + 1) * 1000,
         victimLocation=dict(x=4, y=5), playerLocations=locations)
    for index, victim in enumerate(["b", "c", "d"])
]
rounds = [
    dict(playerStats=[dict(kills=kills)]),
    dict(playerStats=[], bombPlanter="a", plantRoundTime=5000,
         plantPlayerLocations=locations, plantSite="A", plantLocation=dict(x=1, y=2)),
    dict(playerStats=[]),
]
match = dict(matchInfo=dict(matchId=match_id), players=players, roundResults=rounds)
recorded = RecordedRound(pd.Series(dict(match_id=match_id)), match, round_index, "a")
chosen = render_event_buttons(recorded, key_prefix="postmatch_event", initial_event_index=initial)
if chosen is not None:
    render_recorded_event(recorded, chosen, None)
"""


class EventNavigationTests(unittest.TestCase):
    def make_app(self):
        app = AppTest.from_string(REPLAY_APP, default_timeout=20).run()
        self.assertFalse(app.exception)
        return app

    def test_buttons_jump_to_event_and_keep_one_active_without_slider(self):
        app = self.make_app()
        self.assertEqual(3, len(app.button))
        self.assertEqual(0, len(app.slider))
        self.assertIn("Evento 1 de 3", [caption.value for caption in app.caption])
        self.assertEqual(
            ["primary", "secondary", "secondary"], [button.proto.type for button in app.button]
        )
        app.button[2].click().run()
        self.assertFalse(app.exception)
        self.assertIn("Evento 3 de 3", [caption.value for caption in app.caption])
        self.assertEqual(
            ["secondary", "secondary", "primary"], [button.proto.type for button in app.button]
        )
        self.assertIn("D#teste", app.button[2].help)
        app.run()
        self.assertIn("Evento 3 de 3", [caption.value for caption in app.caption])

    def test_event_selection_is_scoped_to_match_and_round(self):
        app = self.make_app()
        original_keys = [button.key for button in app.button]
        app.button[2].click().run()
        app.selectbox(key="fixture_match").select("segunda").run()
        self.assertIn("Evento 1 de 3", [caption.value for caption in app.caption])
        self.assertTrue(set(original_keys).isdisjoint(button.key for button in app.button))
        app.button[2].click().run()
        app.selectbox(key="fixture_round").select(1).run()
        self.assertFalse(app.exception)
        self.assertEqual(1, len(app.button))
        self.assertIn("Evento 1 de 1", [caption.value for caption in app.caption])

    def test_round_without_events_has_no_buttons_or_invalid_event(self):
        app = self.make_app()
        app.selectbox(key="fixture_round").select(2).run()
        self.assertFalse(app.exception)
        self.assertEqual(0, len(app.button))
        self.assertTrue(any("não tem eventos registrados" in message.value for message in app.info))

    def test_initial_event_can_open_a_lance_and_is_clamped_to_available_events(self):
        app = self.make_app()
        app.number_input(key="fixture_initial").set_value(1).run()
        self.assertIn("Evento 2 de 3", [caption.value for caption in app.caption])
        app.button[0].click().run()
        self.assertIn("Evento 1 de 3", [caption.value for caption in app.caption])
        app.number_input(key="fixture_initial").set_value(100).run()
        self.assertIn("Evento 3 de 3", [caption.value for caption in app.caption])


if __name__ == "__main__":
    unittest.main()
