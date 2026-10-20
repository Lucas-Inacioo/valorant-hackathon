"""Resumo da base selecionada e caminhos para as análises."""

import streamlit as st

from valorant.ui.charts import NEUTRAL_COLOR
from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table, display_value


def render(context: AppContext) -> None:
    st.header("Visão geral")
    st.write(
        "Este projeto reúne partidas de VALORANT para estudar o que acontece nos rounds. "
        "Escolha uma análise no menu e use os filtros para comparar os torneios."
    )
    match_column, round_column, player_column = st.columns(3)
    match_column.metric("Partidas", len(context.selected_matches))
    round_column.metric("Rounds", len(context.selected_rounds))
    player_column.metric("Jogadores", context.selected_players["puuid"].nunique())

    map_column, result_column = st.columns(2)
    map_column.subheader("Partidas por mapa")
    map_column.bar_chart(
        context.selected_matches["mapa"].value_counts(),
        horizontal=True,
        color=[NEUTRAL_COLOR],
        x_label="partidas",
        y_label="",
    )
    result_column.subheader("Como os rounds terminam")
    results = context.selected_rounds["resultado"].map(display_value).value_counts()
    result_column.bar_chart(
        results,
        horizontal=True,
        color=[NEUTRAL_COLOR],
        x_label="rounds",
        y_label="",
    )
    st.caption(
        "Os gráficos descrevem as partidas disponíveis. Diferenças entre grupos podem "
        "misturar equipe, mapa e momento do jogo, por isso não demonstram o efeito de uma decisão."
    )
    with st.expander("Ver a lista de partidas"):
        display_table(
            context.selected_matches.drop(
                columns=["match_id", "caminho", "mapa_interno", "mapa_do_arquivo"]
            ),
            hide_index=True,
        )
