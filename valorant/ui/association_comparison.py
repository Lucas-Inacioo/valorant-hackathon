"""Comparação histórica complementar das ocorrências do pós-jogo."""

import pandas as pd
import streamlit as st

from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table


def render_associations(context: AppContext):
    panel = st.expander(
        "Comparar ocorrências em todas as partidas selecionadas",
        on_change="rerun",
        key="association_panel",
    )
    if not panel.open:
        return
    with panel:
        st.write(
            "A diferença compara a taxa de vitória com e sem cada ocorrência. "
            "Por exemplo, 60% contra 50% são 10 pontos percentuais de diferença. "
            "Ela descreve os grupos e não mede o efeito de uma decisão."
        )
        st.caption(
            "O intervalo de 95% vem de repetir a comparação sorteando partidas inteiras. "
            "Nas linhas de mortes, um round com mais mortes entra mais vezes na conta."
        )
        negative, positive = context.data.associations()
        combined = pd.concat([negative, positive], ignore_index=True).drop_duplicates("fator")
        for unit, table in combined.groupby("unidade", sort=False):
            st.markdown(f"**{unit}**")
            table = table.sort_values("diferenca").copy()
            for column in ["diferenca", "ic_baixo", "ic_alto"]:
                table[column] = table[column] * 100
            display_table(
                table,
                hide_index=True,
                column_config={
                    "diferenca": st.column_config.NumberColumn(
                        "Diferença em pontos percentuais", format="%+.1f"
                    ),
                    "ic_baixo": st.column_config.NumberColumn(
                        "Limite inferior em pontos percentuais", format="%+.1f"
                    ),
                    "ic_alto": st.column_config.NumberColumn(
                        "Limite superior em pontos percentuais", format="%+.1f"
                    ),
                },
            )
