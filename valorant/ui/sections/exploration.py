"""Tela de explorar dados."""

import streamlit as st
from valorant.analysis.fights import fight_class_summary
from valorant.ui.context import AppContext
from valorant.ui.tables import players_summary
from valorant.ui.presentation import display_table


def render(context: AppContext) -> None:
    st.header("Explorar dados")
    st.markdown(
        "Aqui ficam outras consultas sobre dano ao longo do round e metadados"
    )
    fights = context.data.fights()[
        context.data.fights()["match_id"].isin(context.selected_match_ids)
    ]
    st.subheader("Dano recebido e causado ao longo do round")
    display_table(fight_class_summary(fights, ["lado"]), width="content", container=st)
    st.subheader("Abates, mortes e pontuação dos jogadores")
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
