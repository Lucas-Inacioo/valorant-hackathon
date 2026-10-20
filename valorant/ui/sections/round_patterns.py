"""Perdas em sequência e tempo do plant ao longo das partidas."""

import pandas as pd
import streamlit as st

from valorant.analysis.round_style import (
    STYLE_ORDER,
    collapse_regions,
    collapse_summary,
    style_by_score,
    style_summary,
    team_profiles,
)
from valorant.data.metadata import callout_name
from valorant.ui.charts import (
    LOST_COLOR,
    SIDE_COLORS,
    STYLE_COLORS,
    dumbbell_chart,
    rate_chart,
    share_chart,
    team_scatter,
)
from valorant.ui.context import AppContext
from valorant.ui.controls import select_map
from valorant.ui.presentation import display_table
from valorant.ui.round_map import draw_rate_markers
from valorant.ui.tables import display_number


def render(context: AppContext) -> None:
    st.header("Ritmo dos rounds")
    st.caption(
        "Aqui olhamos para as perdas de jogadores e o tempo dos eventos. "
        "Cada round aparece uma vez para cada equipe."
    )
    team_rounds = context.data.styles()
    team_rounds = team_rounds[
        team_rounds["match_id"].isin(context.selected_match_ids) & (team_rounds["lado"] != "?")
    ]
    rounds_column, losses_column, plants_column = st.columns(3)
    rounds_column.metric("Rounds contados por equipe", len(team_rounds))
    losses_column.metric(
        "Rounds com três perdas em sequência",
        display_number(team_rounds["colapso"].mean(), ".0%"),
        help="Três jogadores diferentes morrem em até 10 segundos sem a equipe fazer um abate nesse intervalo.",
    )
    fast_plant_rate = (
        team_rounds.loc[team_rounds["lado"] == "ataque", "estilo"] == "execução rápida"
    ).mean()
    plants_column.metric(
        "Rounds de ataque com plant até 40 s", display_number(fast_plant_rate, ".0%")
    )
    _show_losses_by_side_and_map(team_rounds, context)
    _show_loss_locations(team_rounds, context)
    _show_plant_and_abate_timing(team_rounds)
    _show_timing_by_score(team_rounds)
    _show_team_profiles(team_rounds)


def _show_losses_by_side_and_map(team_rounds: pd.DataFrame, context: AppContext) -> None:
    st.subheader("Três perdas em sequência")
    st.caption(
        "Contamos os rounds em que três jogadores diferentes da equipe morreram "
        "em até 10 segundos, sem que ela fizesse um abate nesse intervalo. "
        "A comparação mostra os resultados que acompanharam essas perdas."
    )
    results_by_side = collapse_summary(team_rounds, ["lado"])
    side_column, map_column = st.columns([2, 3])
    side_column.markdown("**Frequência em cada lado**")
    side_column.altair_chart(
        rate_chart(
            results_by_side,
            "lado",
            "colapsos",
            "rounds",
            "% de rounds com três perdas",
            group_column="lado",
            group_colors=SIDE_COLORS,
            height=140,
        ),
        width="stretch",
    )
    side_column.markdown("**Vitórias com e sem essas perdas**")
    side_column.altair_chart(
        dumbbell_chart(
            results_by_side,
            "lado",
            "venceu_com_colapso",
            "venceu_sem_colapso",
            "com três perdas",
            "sem três perdas",
            "% de rounds vencidos",
            count_column="rounds",
            left_color=LOST_COLOR,
        ),
        width="stretch",
    )
    map_column.markdown("**Frequência por mapa e lado**")
    results_by_map = (
        collapse_summary(team_rounds, ["mapa", "lado"])
        .rename(index=context.map_names, level="mapa")
        .sort_values("rounds", ascending=False)
    )
    map_column.altair_chart(
        rate_chart(
            results_by_map,
            "mapa",
            "colapsos",
            "rounds",
            "% de rounds com três perdas",
            group_column="lado",
            group_colors=SIDE_COLORS,
        ),
        width="stretch",
    )


def _show_loss_locations(team_rounds: pd.DataFrame, context: AppContext) -> None:
    selected_map, map_metadata = select_map(
        context,
        "Mapa das perdas em sequência",
        team_rounds["mapa"].value_counts().index,
        "collapse_map",
    )
    losses_by_region = collapse_regions(team_rounds, selected_map)
    if map_metadata is None or losses_by_region.empty:
        st.info("Não há imagem do mapa ou regiões com pelo menos 5 sequências de perdas.")
        return
    location_by_region = {
        callout_name(region): (region["location"]["x"], region["location"]["y"])
        for region in map_metadata["callouts"]
    }
    losses_by_region = losses_by_region.reset_index()
    losses_by_region["x"] = losses_by_region["regiao_colapso"].map(
        lambda name: location_by_region.get(name, (None, None))[0]
    )
    losses_by_region["y"] = losses_by_region["regiao_colapso"].map(
        lambda name: location_by_region.get(name, (None, None))[1]
    )
    losses_by_region = losses_by_region.dropna(subset=["x", "y"])
    map_losses = team_rounds[(team_rounds["mapa"] == selected_map) & team_rounds["colapso"]]
    before_plant_rate = map_losses["fase_colapso"].eq("pré-plant").mean()
    mixed_regions_count = int(map_losses["regiao_colapso"].eq("múltiplas regiões").sum())
    st.caption(
        "Cada marca reúne as perdas de uma região e seu tamanho indica a quantidade. "
        "A cor mostra a parte que começou antes do plant. Círculos ficam acima da "
        f"média do mapa de {before_plant_rate:.0%} e quadrados ficam abaixo. "
        f"Ficam sem marca {mixed_regions_count} sequências que passaram por várias regiões."
    )
    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_regions = losses_by_region[losses_by_region["lado"] == side].set_index(
            "regiao_colapso"
        )
        shown_count = int(side_regions["colapsos"].sum())
        side_column.markdown(
            f"**{side.capitalize()}** com {shown_count} sequências nas regiões mostradas"
        )
        if side_regions.empty:
            side_column.info("Nenhuma região deste lado reúne pelo menos 5 sequências.")
            continue
        side_column.pyplot(
            draw_rate_markers(
                map_metadata,
                side_regions,
                "colapsos",
                "pre_plant",
                before_plant_rate,
                "parte das sequências antes do plant",
                label_min_count=10**9,
                size_per_unit=6,
            ),
            alt=f"Perdas em sequência no lado de {side}. A tabela mostra quantidades por região.",
            width="stretch",
        )
    with st.expander("Números por região"):
        display_table(
            losses_by_region.drop(columns=["x", "y"]),
            hide_index=True,
            width="content",
            container=st,
        )


def _show_plant_and_abate_timing(team_rounds: pd.DataFrame) -> None:
    st.subheader("Tempo do plant e do primeiro abate")
    st.caption(
        "Plant é a instalação da spike. Separamos os rounds por plant até "
        "40 segundos, depois de 40 segundos ou sem plant. Essa divisão usa o tempo "
        "observado e não identifica a estratégia planejada. O primeiro abate "
        "é considerado cedo quando acontece em até 20 segundos após a compra."
    )
    results_by_plant_time, results_by_abate_time = style_summary(team_rounds)
    plant_column, abate_column = st.columns(2)
    plant_column.markdown("**Vitórias do ataque conforme o tempo do plant**")
    plant_column.altair_chart(
        rate_chart(
            results_by_plant_time,
            "estilo",
            "venceu",
            "rounds",
            "% de rounds vencidos pelo ataque",
            order=STYLE_ORDER,
            height=140,
        ),
        width="stretch",
    )
    abate_column.markdown("**Vitórias conforme o tempo do primeiro abate**")
    abate_column.altair_chart(
        rate_chart(
            results_by_abate_time,
            "contato",
            "venceu",
            "rounds",
            "% de rounds vencidos",
            group_column="lado",
            group_colors=SIDE_COLORS,
            height=140,
        ),
        width="stretch",
    )


def _show_timing_by_score(team_rounds: pd.DataFrame) -> None:
    st.subheader("Tempo do plant conforme o placar")
    st.caption(
        "O placar é o que a equipe tinha antes do round começar. "
        "Comparamos os rounds em que estava na frente, atrás ou empatada."
    )
    shares, win_rates, counts = style_by_score(team_rounds)
    shares_column, wins_column = st.columns(2)
    shares_column.markdown("**Distribuição dos rounds de ataque por tempo do plant**")
    shares_column.altair_chart(
        share_chart(
            shares,
            counts,
            STYLE_COLORS,
            "% dos rounds de ataque",
        ),
        width="stretch",
    )
    wins_column.markdown("**Vitórias em cada grupo**")
    display_table(win_rates, width="content", container=wins_column)


def _show_team_profiles(team_rounds: pd.DataFrame) -> None:
    st.subheader("Tempo do plant por equipe")
    st.caption(
        "Cada ponto é uma equipe com pelo menos 40 rounds de ataque. "
        "O tamanho mostra quantos rounds entraram na comparação."
    )
    team_results = team_profiles(team_rounds)
    st.altair_chart(
        team_scatter(
            team_results,
            "execução rápida",
            "vitoria_ataque",
            "rounds_ataque",
            "% de rounds de ataque com plant até 40 s",
            "% de rounds de ataque vencidos",
        ),
        width="stretch",
    )
    with st.expander("Todos os números por equipe"):
        display_table(team_results, width="stretch", container=st)
