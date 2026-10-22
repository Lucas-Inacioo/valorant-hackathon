"""Cobertura da base completa e dos eventos usados na seleção."""

import pandas as pd
import streamlit as st

from valorant.analysis.fights import fight_coverage
from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table

COVERAGE_LABELS = {
    "mortes_brutas": "Mortes registradas",
    "mortes_diagnostico": "Mortes usadas nas análises de posição e troca",
    "mortes_excluidas": "Mortes fora dessas análises",
    "com_posicao_autor": "Mortes com posição de quem fez o abate",
    "com_proxy_geometrica": "Mortes com classificação de proximidade calculável",
}


def render(context: AppContext) -> None:
    st.header("Qualidade dos dados")
    st.write(
        "Cobertura é a quantidade de registros com a informação necessária para uma análise. "
        "Quando falta posição ou uma comparação suficiente, o painel mantém essa lacuna."
    )
    st.subheader("Arquivos disponíveis")
    st.caption("Estes totais incluem toda a base local, mesmo as partidas fora dos filtros.")
    totals = context.quality["totals"]
    columns = st.columns(4)
    for column, label, key in zip(
        columns,
        ["Partidas", "Rounds", "Mortes", "Jogadores"],
        ["matches", "rounds", "deaths", "participants"],
    ):
        column.metric(label, totals[key])

    st.subheader("Partidas com dados atípicos")
    st.write(
        "Uma partida começa com muitos rounds encerrados pelo tempo, sem abates nem plant. "
        "Ela fica fora das análises por padrão e pode ser incluída nos filtros. Os arquivos não explicam a causa."
    )
    anomalies = context.quality["anomalies"]
    anomaly_rows = [
        {
            "Arquivo": row["source"],
            "Rounds": row["rounds"],
            "Rounds iniciais sem abates nem plant": row["initial_empty_timer_rounds"],
        }
        for row in anomalies
    ]
    display_table(pd.DataFrame(anomaly_rows), hide_index=True)

    st.subheader("Informação disponível na seleção atual")
    coverage = fight_coverage(context.data.fights())
    coverage_rows = [
        {"Informação": COVERAGE_LABELS[key], "Registros": value} for key, value in coverage.items()
    ]
    display_table(pd.DataFrame(coverage_rows), hide_index=True)
    st.caption(
        "As análises de posição e troca usam abates entre adversários enquanto o round ainda está em disputa. "
        "O painel mantém os demais eventos para consulta na partida."
    )
    st.subheader("Como tratamos os eventos")
    st.write(
        "Quando as duas equipes fazem o primeiro abate no mesmo instante, não escolhemos uma delas como abertura. "
        "Plants feitos depois da eliminação da defesa ou em rounds encerrados pelo tempo ficam fora das taxas de desarme. "
        "Os registros de posição mostram instantes do jogo e não permitem reconstruir todo o caminho ou a linha de tiro."
    )
    with st.expander("Ver os detalhes da conferência"):
        st.json(context.quality)
        st.caption(
            "A assinatura abaixo identifica a versão dos dados e metadados usada nesta execução."
        )
        st.code(context.data.data_version, language=None)
