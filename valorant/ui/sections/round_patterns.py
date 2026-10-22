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
    st.header("Colapso e estilo")
    st.markdown(
        "Colapso foi definido como três jogadores da equipe morrendo em até 10 segundos sem que a equipe mate ninguém nesse intervalo. "
        "Execução rápida é quando a spike é plantada em até 40 s, default quando é plantada depois disso, sem plant quando o round acabou antes de plantar. "
        "Contato cedo é quando o primeiro abate do round aconteceu em até 20 s. Por fim, placar é quem estava na frente antes do round começar. "
        "Plant fora da análise é quando a spike foi plantada sem defensor vivo, depois de o round já estar decidido, em round encerrado por tempo ou sem posição registrada."
    )
    team_rounds = context.data.styles()
    team_rounds = team_rounds[
        team_rounds["match_id"].isin(context.selected_match_ids) & (team_rounds["lado"] != "?")
    ]
    rounds_column, losses_column, plants_column = st.columns(3)
    rounds_column.metric("Rounds contados (um por equipe)", len(team_rounds))
    losses_column.metric(
        "Rounds com colapso",
        display_number(team_rounds["colapso"].mean(), ".0%"),
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
    st.subheader("1. Colapso: com que frequência acontece e quanto custa?")
    results_by_side = collapse_summary(team_rounds, ["lado"])
    side_column, map_column = st.columns([2, 3])
    side_column.markdown("**Parte dos rounds com colapso**, em cada lado")
    side_column.altair_chart(
        rate_chart(
            results_by_side,
            "lado",
            "colapsos",
            "rounds",
            "% dos rounds com colapso",
            group_column="lado",
            group_colors=SIDE_COLORS,
            height=140,
        ),
        width="stretch",
    )
    side_column.markdown("**Quantos rounds a equipe vence** quando colapsa (quadrado) e quando não colapsa (círculo)")
    side_column.altair_chart(
        dumbbell_chart(
            results_by_side,
            "lado",
            "venceu_com_colapso",
            "venceu_sem_colapso",
            "com colapso",
            "sem colapso",
            "% de rounds vencidos",
            count_column="rounds",
            left_color=LOST_COLOR,
        ),
        width="stretch",
    )
    map_column.markdown("**Parte dos rounds com colapso em cada mapa**, por lado")
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
            "% dos rounds com colapso",
            group_column="lado",
            group_colors=SIDE_COLORS,
        ),
        width="stretch",
    )


def _show_loss_locations(team_rounds: pd.DataFrame, context: AppContext) -> None:
    selected_map, map_metadata = select_map(
        context,
        "Em que regiões do mapa os colapsos acontecem",
        team_rounds["mapa"].value_counts().index,
        "collapse_map",
    )
    losses_by_region = collapse_regions(team_rounds, selected_map)
    if map_metadata is None or losses_by_region.empty:
        st.info("Este mapa não tem imagem disponível ou não tem colapsos suficientes.")
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
        "Cada círculo é uma região do mapa, só regiões com 5 ou mais colapsos. O tamanho mostra quantos colapsos aconteceram ali, "
        "enquanto a cor e a forma mostram quando, com círculo sendo antes do plant e quadrado depois do plant, "
        f"em relação à média do mapa ({before_plant_rate:.0%} antes do plant). "
        f"Ficam sem marca {mixed_regions_count} colapsos que passaram por várias regiões."
    )
    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_regions = losses_by_region[losses_by_region["lado"] == side].set_index(
            "regiao_colapso"
        )
        shown_count = int(side_regions["colapsos"].sum())
        side_column.markdown(
            f"**Colapsos da equipe de {side}** ({shown_count} colapsos nas regiões mostradas)"
        )
        if side_regions.empty:
            side_column.info("Sem colapsos com volume neste lado.")
            continue
        side_column.pyplot(
            draw_rate_markers(
                map_metadata,
                side_regions,
                "colapsos",
                "pre_plant",
                before_plant_rate,
                "parte dos colapsos antes do plant",
                label_min_count=10**9,
                size_per_unit=6,
            ),
            alt=f"Colapsos no lado de {side}. A tabela mostra quantidades por região.",
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
    st.subheader("2. Ritmo do ataque: plantar rápido rende mais? E fazer contato cedo?")
    results_by_plant_time, results_by_abate_time = style_summary(team_rounds)
    plant_column, abate_column = st.columns(2)
    plant_column.markdown("**Quantos rounds o ataque vence** conforme o ritmo")
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
    abate_column.markdown("**Quantos rounds cada lado vence** quando o primeiro abate sai até 20 s (contato cedo) ou depois (contato tarde)")
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
    st.subheader("3. A equipe muda o ritmo quando está perdendo?")
    shares, win_rates, counts = style_by_score(team_rounds)
    shares_column, wins_column = st.columns(2)
    shares_column.markdown("**Como os rounds de ataque se dividem entre os ritmos**, conforme o placar antes do round")
    shares_column.altair_chart(
        share_chart(
            shares,
            counts,
            STYLE_COLORS,
            "% dos rounds de ataque",
        ),
        width="stretch",
    )
    wins_column.markdown("**Parte dos rounds vencidos** em cada combinação de placar e ritmo")
    display_table(win_rates, width="content", container=wins_column)


def _show_team_profiles(team_rounds: pd.DataFrame) -> None:
    st.subheader("4. Perfil de cada equipe (equipes com 40 ou mais rounds de ataque)")
    team_results = team_profiles(team_rounds)
    st.altair_chart(
        team_scatter(
            team_results,
            "execução rápida",
            "vitoria_ataque",
            "rounds_ataque",
            "% dos rounds de ataque com plant até 40 s",
            "% de rounds de ataque vencidos",
        ),
        width="stretch",
    )
    with st.expander("Todos os números por equipe"):
        display_table(team_results, width="stretch", container=st)
