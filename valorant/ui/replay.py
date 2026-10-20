"""Dados e exibição compartilhados pelas duas telas de consulta de rounds."""

from dataclasses import dataclass
from functools import cached_property

import pandas as pd
import streamlit as st

from valorant.analysis.events import round_events
from valorant.ui.presentation import display_table
from valorant.ui.round_map import describe_event, draw_round_map
from valorant.ui.tables import event_position_table


@dataclass(frozen=True)
class RecordedRound:
    match_info: pd.Series
    match: dict
    round_index: int
    player_id: str

    @property
    def result(self):
        return self.match["roundResults"][self.round_index]

    @cached_property
    def player_names(self):
        return {
            player["puuid"]: f'{player["gameName"]}#{player["tagLine"]}'
            for player in self.match["players"]
        }

    @cached_property
    def player_teams(self):
        return {player["puuid"]: player["teamId"] for player in self.match["players"]}

    @cached_property
    def events(self):
        return round_events(self.result, self.player_teams)


def render_recorded_event(recorded_round: RecordedRound, event_index: int, map_metadata):
    event = recorded_round.events[event_index]
    description = describe_event(event, recorded_round.player_names, recorded_round.result)
    st.caption(description)
    map_column, position_column = st.columns([3, 2])
    if map_metadata is not None:
        map_column.pyplot(
            draw_round_map(
                map_metadata,
                recorded_round.events,
                event_index,
                recorded_round.player_id,
                recorded_round.player_teams,
                recorded_round.player_names,
            ),
            alt=description,
            width="stretch",
        )
    display_table(
        event_position_table(event, recorded_round.player_names, recorded_round.player_teams),
        hide_index=True,
        container=position_column,
    )
    st.caption(
        "As posições foram registradas nos eventos. As linhas ligam esses registros e não mostram todo o caminho percorrido. "
        "O mapa também não informa se havia parede ou smoke entre os jogadores."
    )
