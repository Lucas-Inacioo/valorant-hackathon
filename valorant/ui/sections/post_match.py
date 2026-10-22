"""Análise da partida inteira e dos lances que sustentam cada observação."""

import streamlit as st

from valorant.analysis.deaths import SOLO_DISTANCE, with_solo_flag
from valorant.analysis.first_blood import first_blood_table
from valorant.data.metadata import load_agents_by_id
from valorant.ui.context import AppContext
from valorant.ui.association_comparison import render_associations
from valorant.ui.post_match_selection import PostMatchSelection, select_match_and_team
from valorant.ui.post_match_views import show_evidence, show_players, show_team
from valorant.ui.presentation import display_table
from valorant.ui.tables import deaths_per_round_table, first_blood_per_round_table


def show_match_details(selection: PostMatchSelection):
    panel = st.expander(
        "Consultar os números e os dados da partida", on_change="rerun", key="review_raw_details"
    )
    if not panel.open:
        return
    with panel:
        app = selection.app
        match_id = selection.match_id
        st.markdown("**Primeiro abate de cada round**")
        openings = first_blood_table(app.data.match_table(match_id, "deaths"))
        display_table(
            first_blood_per_round_table(openings[openings["match_id"] == match_id]), hide_index=True
        )
        st.markdown("**Mortes, isolamento e trocas por round**")
        st.caption(
            "O isolamento usa o limite de 1000 unidades do jogo, cerca de 10 metros. Essa conversão é aproximada. Trocas contam abates do autor da morte em até cinco segundos, incluindo o mesmo instante."
        )
        deaths = app.data.match_table(match_id, "deaths")
        scoped = with_solo_flag(deaths[deaths["match_id"] == match_id], SOLO_DISTANCE)
        display_table(
            deaths_per_round_table(scoped, selection.match["roundResults"]), hide_index=True
        )
        st.markdown("**Jogadores e resultados registrados**")
        players = (
            app.players[app.players["match_id"] == match_id]
            .drop(columns=["match_id", "puuid"])
            .copy()
        )
        agents = load_agents_by_id()
        players["agente"] = players["agente"].map(
            lambda agent: agents.get(agent, {}).get("agente", agent)
        )
        display_table(
            players.sort_values(["time", "score"], ascending=[True, False]), hide_index=True
        )
        display_table(
            app.rounds[app.rounds["match_id"] == match_id].drop(columns=["match_id"]),
            hide_index=True,
        )
        st.json(selection.match["matchInfo"])


def render(context: AppContext) -> None:
    st.header("Análise pós-jogo")
    selection = select_match_and_team(context)
    info = selection.match_info
    st.caption(
        f'{info["torneio"]} no mapa {info["mapa"]}. Blue fez {info["rounds_blue"]} rounds e Red fez {info["rounds_red"]}.'
    )
    st.markdown(f"**Equipe em análise {selection.team_names[selection.team_id]}**")
    view = st.radio(
        "Visão pós-jogo", ["Equipe", "Jogadores", "Lances"], horizontal=True, key="review_view"
    )
    {"Equipe": show_team, "Jogadores": show_players, "Lances": show_evidence}[view](selection)
    show_match_details(selection)
    render_associations(context)
