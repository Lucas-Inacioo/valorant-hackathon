"""Primeiro abate, localização e função do jogador que morreu."""

import pandas as pd
import streamlit as st

from valorant.analysis.agent_roles import (
    ROLE_ORDER,
    first_death_by_agent,
    first_death_by_role,
    first_death_by_role_and_trade,
    role_share,
)
from valorant.analysis.first_blood import (
    TIME_LABELS,
    plant_summary,
    summary_by_map,
    win_rate_by_time,
)
from valorant.ui.charts import (
    ATTACK_COLOR,
    DEFENSE_COLOR,
    LOST_COLOR,
    NEUTRAL_COLOR,
    SIDE_COLORS,
    WON_COLOR,
    grouped_bar_chart,
    opening_impact_chart,
    quantile_band_chart,
    rate_chart,
)
from valorant.ui.context import AppContext
from valorant.ui.controls import select_map
from valorant.ui.presentation import display_table
from valorant.ui.round_map import draw_callout_summary, draw_points
from valorant.ui.tables import display_number, openings_by_callout


def render(context: AppContext) -> None:
    st.header("Primeiro abate")
    st.caption(
        "O primeiro abate é a primeira morte causada por um adversário no round. "
        "O relógio começa depois da fase de compra."
    )
    first_abates = context.data.first_blood()
    first_abates = first_abates[first_abates["match_id"].isin(context.selected_match_ids)]
    _show_summary(first_abates)
    _show_abate_timing(first_abates)
    _show_results_by_map(first_abates, context)
    _show_attack_locations(first_abates, context)
    _show_victim_roles(context)
    _show_timing_by_round(first_abates)


def _show_summary(first_abates: pd.DataFrame) -> None:
    rounds_column, time_column, wins_column = st.columns(3)
    rounds_column.metric("Rounds com primeiro abate definido", len(first_abates))
    time_column.metric(
        "Tempo do primeiro abate",
        display_number(first_abates["segundos"].median(), suffix=" s"),
        help="Mediana do tempo. Metade dos primeiros abates aconteceu antes e metade depois.",
    )
    wins_column.metric(
        "Vitórias de quem fez o primeiro abate",
        display_number(first_abates["abriu_venceu"].mean(), ".1%"),
    )
    ambiguous_rounds = first_abates.attrs.get("rounds_abertura_ambigua", 0)
    rounds_without_abate = first_abates.attrs.get("rounds_sem_abertura_valida", 0)
    st.caption(
        f"Ficam fora desta comparação {ambiguous_rounds} rounds com primeiros abates "
        f"simultâneos das duas equipes e {rounds_without_abate} rounds sem abate válido. "
        "Quando os abates simultâneos são da mesma equipe, o round entra nas taxas, "
        "mas não recebe uma posição individual no mapa."
    )


def _show_abate_timing(first_abates: pd.DataFrame) -> None:
    st.subheader("Resultado conforme o tempo do primeiro abate")
    st.caption(
        "A taxa mostra quantos rounds foram vencidos pela equipe que fez o primeiro abate. "
        "Ataque e defesa aparecem separados."
    )
    rate_column, count_column = st.columns([3, 2])
    rate_column.altair_chart(
        rate_chart(
            win_rate_by_time(first_abates),
            "faixa",
            "abriu_venceu",
            "rounds",
            "% de rounds vencidos por quem fez o primeiro abate",
            group_column="lado_abriu",
            group_colors=SIDE_COLORS,
            order=TIME_LABELS,
        ),
        width="stretch",
    )
    count_column.markdown("**Quantidade de primeiros abates em cada faixa de tempo**")
    counts_by_time = pd.crosstab(first_abates["faixa"], first_abates["lado_abriu"]).reindex(
        TIME_LABELS
    )
    count_column.altair_chart(
        grouped_bar_chart(
            counts_by_time,
            [ATTACK_COLOR, DEFENSE_COLOR],
            "rounds",
            ",",
        ),
        width="stretch",
    )
    with st.expander("Primeiro abate antes ou depois do plant"):
        st.caption("Plant é o momento em que o ataque termina de instalar a spike.")
        display_table(
            plant_summary(first_abates).rename(
                index={True: "antes do plant", False: "depois do plant"},
                level="antes_do_plant",
            ),
            width="content",
            container=st,
        )


def _show_results_by_map(first_abates: pd.DataFrame, context: AppContext) -> None:
    st.subheader("Diferença entre o ataque e a defesa em cada mapa")
    st.caption(
        "Comparamos a taxa de vitória do ataque quando ele faz o primeiro abate com "
        "a taxa quando a defesa faz esse abate. Por exemplo, de 40% para 60% são "
        "20 pontos percentuais. A diferença também pode refletir a força das equipes."
    )
    results_by_map = summary_by_map(first_abates).rename(index=context.map_names)
    chart_column, table_column = st.columns([3, 2])
    chart_column.altair_chart(opening_impact_chart(results_by_map), width="stretch")
    display_table(
        results_by_map[
            [
                "rounds",
                "ataque_abriu",
                "ataque_vence",
                "ataque_vence_se_abre",
                "ataque_vence_se_defesa_abre",
            ]
        ],
        width="stretch",
        container=table_column,
    )


def _show_attack_locations(first_abates: pd.DataFrame, context: AppContext) -> None:
    st.subheader("Onde o ataque faz o primeiro abate")
    selected_map, map_metadata = select_map(
        context,
        "Mapa",
        summary_by_map(first_abates).index,
        "opening_map",
    )
    attack_abates = first_abates[
        (first_abates["mapa"] == selected_map)
        & (first_abates["lado_abriu"] == "ataque")
        & first_abates["antes_do_plant"]
    ].dropna(subset=["vitima_x", "vitima_y"])
    if map_metadata is None or attack_abates.empty:
        st.info("Não há imagem do mapa ou primeiros abates do ataque nesta seleção.")
        return
    results_by_region = openings_by_callout(attack_abates, map_metadata)
    map_win_rate = attack_abates["abriu_venceu"].mean()
    st.caption(
        "As marcas usam a posição do defensor que morreu antes do plant. "
        "Cada região reúne os abates mais próximos dela. Marcas maiores indicam "
        f"mais abates. Círculos indicam taxas acima da média do mapa de {map_win_rate:.0%} "
        "e quadrados indicam taxas abaixo dela. Poucos abates deixam a taxa menos precisa."
    )
    map_column, table_column = st.columns([3, 2])
    if st.checkbox("Mostrar cada abate em vez das regiões"):
        rounds_won = attack_abates[attack_abates["abriu_venceu"]]
        rounds_lost = attack_abates[~attack_abates["abriu_venceu"]]
        figure = draw_points(
            map_metadata,
            [
                (
                    "ataque venceu o round",
                    WON_COLOR,
                    "o",
                    list(zip(rounds_won["vitima_x"], rounds_won["vitima_y"])),
                ),
                (
                    "ataque perdeu o round",
                    LOST_COLOR,
                    "x",
                    list(zip(rounds_lost["vitima_x"], rounds_lost["vitima_y"])),
                ),
            ],
        )
    else:
        figure = draw_callout_summary(
            map_metadata,
            results_by_region,
            map_win_rate,
            label_min_count=10**9,
        )
    map_column.pyplot(
        figure,
        alt="Primeiros abates do ataque por região. A tabela mostra as quantidades e taxas.",
        width="stretch",
    )
    display_table(
        results_by_region[["aberturas", "ataque_venceu", "ic95"]],
        width="stretch",
        container=table_column,
    )


def _show_victim_roles(context: AppContext) -> None:
    st.subheader("Função de quem morreu primeiro")
    st.caption(
        "A função é a classe do agente no jogo, como duelista, iniciador, controlador "
        "ou sentinela. O primeiro gráfico compara a presença de cada função nas "
        "equipes com sua presença entre as primeiras mortes."
    )
    max_seconds = st.slider(
        "Considerar só primeiros abates até este segundo do round",
        10,
        150,
        150,
        step=10,
        key="role_max_seconds",
    )
    deaths = context.data.deaths()
    deaths = deaths[deaths["match_id"].isin(context.selected_match_ids)]
    first_deaths_by_role = first_death_by_role(deaths, max_seconds)
    share_column, wins_column = st.columns(2)
    share_column.markdown("**Presença nas equipes e nas primeiras mortes**")
    share_column.altair_chart(
        grouped_bar_chart(
            role_share(deaths, max_seconds),
            [NEUTRAL_COLOR, ATTACK_COLOR, DEFENSE_COLOR],
            "fração",
        ),
        width="stretch",
    )
    wins_column.markdown("**Vitórias da equipe que perdeu o primeiro jogador**")
    wins_column.altair_chart(
        rate_chart(
            first_deaths_by_role,
            "funcao",
            "vitoria_da_vitima",
            "rounds",
            "% de rounds vencidos pela equipe da vítima",
            group_column="lado",
            group_colors=SIDE_COLORS,
            order=ROLE_ORDER,
        ),
        width="stretch",
    )
    with st.expander("Números por função, troca e agente"):
        display_table(first_deaths_by_role, width="content", container=st)
        st.markdown("**Com e sem troca**")
        st.caption(
            "Uma morte conta como trocada quando um aliado mata o adversário que "
            "a causou em até 5 segundos."
        )
        display_table(
            first_death_by_role_and_trade(deaths, max_seconds), width="content", container=st
        )
        st.markdown("**Agentes com pelo menos 30 primeiras mortes**")
        st.caption("As diferenças incluem o agente, quem o escolheu e as partidas em que jogou.")
        display_table(first_death_by_agent(deaths, max_seconds), width="content", container=st)


def _show_timing_by_round(first_abates: pd.DataFrame) -> None:
    st.subheader("Tempo do primeiro abate ao longo da partida")
    timing_by_round = (
        first_abates[first_abates["round"] <= 24]
        .groupby("round")["segundos"]
        .agg(
            rounds="size",
            p10=lambda seconds: seconds.quantile(0.1),
            p25=lambda seconds: seconds.quantile(0.25),
            mediana="median",
            p75=lambda seconds: seconds.quantile(0.75),
            p90=lambda seconds: seconds.quantile(0.9),
            media="mean",
            desvio_padrao="std",
        )
        .round(1)
    )
    st.caption(
        "A linha mostra a mediana em cada round da partida. A faixa escura reúne "
        "a metade central dos tempos e a clara reúne os 80% centrais. O gráfico ao "
        "lado conta os rounds que entraram nessa comparação, sem prorrogação."
    )
    time_column, count_column = st.columns([3, 2])
    time_column.altair_chart(quantile_band_chart(timing_by_round), width="stretch")
    count_column.bar_chart(
        timing_by_round["rounds"],
        color=[NEUTRAL_COLOR],
        y_label="rounds contados",
        x_label="round da partida",
    )
    with st.expander("Números por round"):
        display_table(timing_by_round, width="content", container=st)
