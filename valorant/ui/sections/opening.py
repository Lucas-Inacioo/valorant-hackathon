"""Primeiro abate, localização e função do jogador que morreu."""

import pandas as pd
import streamlit as st

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
    st.header("Abertura")
    st.caption("O tempo conta a partir do início do round, depois da fase de compra.")
    first_abates = context.data.first_blood()
    first_abates = first_abates[first_abates["match_id"].isin(context.selected_match_ids)]
    _show_summary(first_abates)
    _show_abate_timing(first_abates)
    _show_results_by_map(first_abates, context)
    _show_attack_locations(first_abates, context)
    _show_timing_by_round(first_abates)


def _show_summary(first_abates: pd.DataFrame) -> None:
    rounds_column, time_column, wins_column = st.columns(3)
    rounds_column.metric("Rounds com pelo menos um abate, sem empate na abertura", len(first_abates))
    time_column.metric(
        "Segundo típico do primeiro abate (mediana)",
        display_number(first_abates["segundos"].median(), suffix=" s"),
        help="Mediana do tempo. Metade dos primeiros abates aconteceu antes e metade depois.",
    )
    wins_column.metric(
        "Quem consegue o primeiro abate vence o round",
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
    st.subheader(
        "1. Quem consegue o primeiro abate vence o round? Isso muda conforme o tempo em que ele acontece?"
    )
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
            "% de rounds vencidos pela equipe que conseguiu o primeiro abate",
            group_column="lado_abriu",
            group_colors=SIDE_COLORS,
            order=TIME_LABELS,
        ),
        width="stretch",
    )
    count_column.markdown(
        "**Em que segundo o primeiro abate acontece**, separado pelo lado que fez o abate"
    )
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
    st.subheader("2. Em que mapa o primeiro abate do ataque pesa mais?")
    st.caption(
        "Diferença entre quantos rounds o ataque vence quando a equipe atacante consegue o "
        "primeiro abate e quantos vence quando a equipe defensora consegue o primeiro abate. "
        "Barra maior significa que, naquele mapa, conseguir o primeiro abate muda mais o round. "
        "Mapas em ordem de quantidade de rounds, entre parênteses."
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
    st.subheader("3. Em que lugar do mapa o ataque consegue o primeiro abate")
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
        st.info("Este mapa não tem imagem disponível ou não tem primeiros abates do ataque nos filtros escolhidos.")
        return
    results_by_region = openings_by_callout(attack_abates, map_metadata)
    map_win_rate = attack_abates["abriu_venceu"].mean()
    st.caption(
        "Cada círculo é uma região do mapa, com o nome que os jogadores usam para ela. "
        "Só foram considerados o primeiro abate de cada round do ataque, antes do plant, e "
        "agrupados na região mais próxima de onde o defensor morreu. O tamanho do círculo "
        "mostra quantos primeiros abates aconteceram ali, enquanto a cor e a forma quantos "
        f"desses rounds o ataque venceu, em relação à média do mapa ({map_win_rate:.0%}). "
        "Círculo: matar um defensor ali quase garante o round. Quadrado: mesmo matando ali, "
        "o round continua em aberto."
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


def _show_timing_by_round(first_abates: pd.DataFrame) -> None:
    st.subheader("5. O primeiro abate fica mais cedo ou mais tarde ao longo da partida?")
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
        "Para cada round da partida, o segundo em que o primeiro abate acontece. A linha "
        "apresenta o valor típico, com metade dos rounds abaixo e metade acima. A faixa escura "
        "onde ficam os 50% centrais e a faixa clara os 80% centrais. O gráfico ao lado mostra "
        "a frequência de partidas que chegaram até cada round."
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
