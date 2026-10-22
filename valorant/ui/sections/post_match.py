"""Análise da partida inteira e dos lances que sustentam cada observação."""

import streamlit as st

from valorant.ui.context import AppContext
from valorant.ui.post_match_selection import select_match_and_team
from valorant.ui.post_match_views import show_evidence, show_players, show_team


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
