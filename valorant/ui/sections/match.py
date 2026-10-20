"""Consulta de eventos e números de uma partida."""

from pathlib import Path

import streamlit as st

from valorant.analysis.deaths import SOLO_DISTANCE, with_solo_flag
from valorant.data.fields import load_match
from valorant.data.metadata import load_agents_by_id
from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table
from valorant.ui.replay import RecordedRound, render_recorded_event
from valorant.ui.tables import deaths_per_round_table, first_blood_per_round_table


def render(context: AppContext) -> None:
    st.header("Acompanhar partida")
    chosen_file = st.selectbox("Partida", context.selected_matches["arquivo"].tolist())
    match_info = context.selected_matches[context.selected_matches["arquivo"] == chosen_file].iloc[
        0
    ]
    match = load_match(Path(match_info["caminho"]))
    st.write(
        f'{match_info["torneio"]} no mapa {match_info["mapa"]}. Blue fez {match_info["rounds_blue"]} rounds e Red fez {match_info["rounds_red"]}.'
    )
    st.subheader("Posições registradas no round")
    st.caption(
        "Escolha um evento de abate, plant ou desarme para ver as posições disponíveis naquele instante."
    )
    participants = {p["puuid"]: p for p in match["players"] if not p["isObserver"]}
    player_column, round_column = st.columns(2)
    selected_player = player_column.selectbox(
        "Jogador",
        list(participants),
        format_func=lambda player: f'{participants[player]["gameName"]}#{participants[player]["tagLine"]} ({participants[player]["teamId"]})',
    )
    round_index = round_column.selectbox(
        "Round", range(len(match["roundResults"])), format_func=lambda index: f"Round {index + 1}"
    )
    recorded = RecordedRound(match_info, match, round_index, selected_player)
    map_metadata = context.data.maps().get(match["matchInfo"]["mapId"])
    if not recorded.events:
        st.info("Este round não tem eventos com posições registradas.")
    else:
        if map_metadata is None:
            st.info("Este mapa não tem imagem disponível. As posições aparecem na tabela.")
        event_index = (
            st.slider("Momento", 0, len(recorded.events) - 1, 0, format="evento %d")
            if len(recorded.events) > 1
            else 0
        )
        render_recorded_event(recorded, event_index, map_metadata)

    st.subheader("Primeiro abate de cada round")
    st.caption(
        "A abertura é o primeiro abate entre adversários. Rounds com abates das duas equipes no mesmo instante não têm abertura definida."
    )
    openings = context.data.first_blood()
    display_table(
        first_blood_per_round_table(openings[openings["match_id"] == match_info["match_id"]]),
        hide_index=True,
    )

    st.subheader("Mortes, isolamento e trocas por round")
    st.caption(
        "Uma morte é isolada quando o aliado vivo mais próximo está a mais de 1.000 unidades do jogo, cerca de 10 metros. "
        "Essa conversão é aproximada. A troca conta quando um aliado abate quem fez a morte em até cinco segundos, incluindo o mesmo instante."
    )
    deaths = context.data.deaths()
    match_deaths = with_solo_flag(
        deaths[deaths["match_id"] == match_info["match_id"]], SOLO_DISTANCE
    )
    display_table(deaths_per_round_table(match_deaths, match["roundResults"]), hide_index=True)

    with st.expander("Ver jogadores, rounds e dados do arquivo"):
        match_players = (
            context.players[context.players["match_id"] == match_info["match_id"]]
            .drop(columns=["match_id", "puuid"])
            .copy()
        )
        agent_names = {key: agent["agente"] for key, agent in load_agents_by_id().items()}
        match_players["agente"] = match_players["agente"].map(
            lambda agent: agent_names.get(agent, agent)
        )
        display_table(
            match_players.sort_values(["time", "score"], ascending=[True, False]), hide_index=True
        )
        display_table(
            context.rounds[context.rounds["match_id"] == match_info["match_id"]].drop(
                columns=["match_id"]
            ),
            hide_index=True,
        )
        st.json(match["matchInfo"])
