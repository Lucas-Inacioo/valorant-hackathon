"""Dados e exibição compartilhados pelas duas telas de consulta de rounds."""

from dataclasses import dataclass
from functools import cached_property
import hashlib
import json

import pandas as pd
import streamlit as st

from valorant.analysis.events import is_enemy_kill, round_events
from valorant.ui.presentation import display_table
from valorant.ui.round_map import describe_event, draw_round_map
from valorant.ui.tables import event_position_table


@dataclass(frozen=True)
class RecordedRound:
    match_info: pd.Series
    match: dict
    round_index: int
    player_id: str
    highlight_selected: bool = True

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


def _navigation_scope(recorded_round: RecordedRound, key_prefix: str) -> str:
    """Identifica a partida e o round sem depender da posição de uma seleção."""
    match_id = recorded_round.match.get("matchInfo", {}).get("matchId")
    if not match_id:
        match_id = recorded_round.match_info.get("match_id")
    if not match_id:
        match_id = json.dumps(recorded_round.match, sort_keys=True, ensure_ascii=False)
    identity = json.dumps([str(match_id), recorded_round.round_index])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{key_prefix}_{digest}"


def _select_event(state_key: str, event_index: int) -> None:
    st.session_state[state_key] = event_index


def event_button_label(event: dict, event_index: int, teams: dict) -> str:
    """Rótulo curto. Os nomes e a descrição completa ficam no texto de ajuda."""
    seconds = f"{event.get('time_ms', 0) / 1000:.1f}".replace(".", ",")
    kind = {"plant": "Plant", "defuse": "Desarme"}.get(event["kind"])
    if kind is None:
        kind = "Abate" if is_enemy_kill(event, teams) else "Morte"
    return f"{event_index + 1} · {seconds} s · {kind}"


def render_event_buttons(
    recorded_round: RecordedRound, *, key_prefix: str = "round_events", initial_event_index: int = 0
) -> int | None:
    """Um botão por evento com seleção preservada apenas na partida e round.

    O índice inicial também permite abrir um lance vindo do resumo. Se ele
    mudar, a seleção acompanha o novo lance. Clicar nos botões mantém a escolha
    entre as demais atualizações da tela.
    """
    events = recorded_round.events
    if not events:
        st.info("Este round não tem eventos registrados.")
        return None
    scope = _navigation_scope(recorded_round, key_prefix)
    state_key = f"{scope}_selected"
    initial_key = f"{scope}_initial"
    initial = min(max(int(initial_event_index), 0), len(events) - 1)
    if st.session_state.get(initial_key) != initial:
        st.session_state[state_key] = initial
        st.session_state[initial_key] = initial
    selected = st.session_state.get(state_key, initial)
    if not isinstance(selected, int) or not 0 <= selected < len(events):
        selected = initial
        st.session_state[state_key] = selected
    st.caption("Escolha um evento para ver as posições registradas naquele instante.")
    with st.container(horizontal=True, wrap=True, gap="small"):
        for index, event in enumerate(events):
            event_id = event.get("event_id", f"{index}:{event.get('time_ms')}:{event['kind']}")
            event_digest = hashlib.sha256(str(event_id).encode("utf-8")).hexdigest()[:12]
            st.button(
                event_button_label(event, index, recorded_round.player_teams),
                key=f"{scope}_event_{event_digest}_{index}",
                help=describe_event(event, recorded_round.player_names, recorded_round.result),
                type="primary" if selected == index else "secondary",
                on_click=_select_event,
                args=(state_key, index),
            )
    return selected


def render_recorded_event(recorded_round: RecordedRound, event_index: int, map_metadata):
    if not recorded_round.events:
        st.info("Este round não tem eventos registrados.")
        return
    if not 0 <= event_index < len(recorded_round.events):
        st.info("Este evento não está disponível no round escolhido.")
        return
    event = recorded_round.events[event_index]
    description = describe_event(event, recorded_round.player_names, recorded_round.result)
    st.caption(f"Evento {event_index + 1} de {len(recorded_round.events)}")
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
                highlight_selected=recorded_round.highlight_selected,
            ),
            alt=description,
            width="stretch",
        )
    else:
        map_column.info("A imagem deste mapa não está disponível. Consulte as posições na tabela.")
    if recorded_round.highlight_selected:
        position_column.caption(
            f"Jogador escolhido {recorded_round.player_names.get(recorded_round.player_id, 'sem identificação')}."
        )
    display_table(
        event_position_table(event, recorded_round.player_names, recorded_round.player_teams),
        hide_index=True,
        container=position_column,
    )
