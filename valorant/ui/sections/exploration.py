"""Tela de explorar dados."""

import streamlit as st
from valorant.analysis.fights import (
    distance_matrix,
    distance_summary,
    fight_class_summary,
    player_range_discipline,
)
from valorant.ui.context import AppContext
from valorant.ui.tables import players_summary
from valorant.ui.presentation import display_table


def render(context: AppContext) -> None:
    st.header("Explorar dados")
    st.markdown(
        "Aqui ficam outras consultas sobre armas iniciais, distância e dano ao longo do round. Você também pode ver os números dos jogadores e os campos presentes nos arquivos."
    )
    fights = context.data.fights()[
        context.data.fights()["match_id"].isin(context.selected_match_ids)
    ]
    st.subheader("Arma da vítima e distância de quem matou")
    summary_column, matrix_column = st.columns(2)
    display_table(distance_summary(fights), width="content", container=summary_column)
    distance_shares = distance_matrix(fights)
    display_table(
        distance_shares,
        percentage_columns=distance_shares.columns,
        width="content",
        container=matrix_column,
    )
    name_by_puuid = context.players.drop_duplicates("puuid").set_index("puuid")["jogador"]
    short_table, sniper_table = player_range_discipline(fights, name_by_puuid)
    short_column, sniper_column = st.columns(2)
    short_column.markdown(
        "**Mortes com submetralhadora ou escopeta inicial a longa distância**. Entram jogadores com pelo menos 10 mortes com essas armas."
    )
    display_table(short_table, hide_index=True, width="content", container=short_column)
    sniper_column.markdown(
        "**Mortes com fuzil de precisão inicial a curta distância**. Entram jogadores com pelo menos 10 mortes com essas armas."
    )
    display_table(sniper_table, hide_index=True, width="content", container=sniper_column)
    st.caption(
        "As distâncias vêm em unidades do jogo. Consideramos longa distância a partir de 2.500 unidades e curta até 1.000. A aproximação de 100 unidades por metro não foi validada."
    )
    st.subheader("Dano recebido e causado ao longo do round")
    st.caption(
        "Categorias pelo dano recebido de adversários ao longo do round, independentemente de assistência. Não identificam foco simultâneo ou reação naquela luta. A arma atribuída à vítima é o equipamento inicial."
    )
    display_table(fight_class_summary(fights, ["lado"]), width="content", container=st)
    st.subheader("Abates, mortes e pontuação dos jogadores")
    st.caption(
        "Abates por morte divide os abates pelas mortes. A pontuação média por round usa o score registrado pelo jogo, sem criar uma nota para o jogador."
    )
    display_table(players_summary(context.selected_players), hide_index=True, container=st)
    st.subheader("Campos dos arquivos de partida")
    relevant_fields, irrelevant_fields = context.data.fields()
    field_filter = st.text_input("Filtrar campo")
    display_table(
        relevant_fields[relevant_fields["campo"].str.contains(field_filter, regex=False)],
        hide_index=True,
        container=st,
    )
    with st.container(border=True):
        st.markdown(
            "**Campos com um único valor.** Eles não ajudam a diferenciar os registros nesta seleção."
        )
        display_table(
            irrelevant_fields.drop(columns=["distintos"]).rename(
                columns={"mais_frequentes": "valor"}
            ),
            hide_index=True,
            container=st,
        )
