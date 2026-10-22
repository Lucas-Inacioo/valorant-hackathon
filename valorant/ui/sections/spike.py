"""Plant, desarme e posições dos jogadores nesses momentos."""

import pandas as pd
import streamlit as st

from valorant.analysis.plants import (
    cells_for_map,
    situation_matrix,
    summary_by_plant_time,
    summary_by_site,
)
from valorant.analysis.setups import defuse_by, retake_summary, watching_bands
from valorant.ui.charts import dumbbell_chart, heatmap_chart
from valorant.ui.context import AppContext
from valorant.ui.controls import select_map
from valorant.ui.presentation import display_table
from valorant.ui.round_map import draw_rate_markers
from valorant.ui.tables import display_number


def render(context: AppContext) -> None:
    st.header("Plant e defuse")
    st.markdown("Esperado pelos vivos é a taxa de desarme normal para a mesma quantidade de vivos em cada um dos lados, considerando todos os mapas e sites.")
    st.caption(
        "Plant é a instalação da spike pelo ataque. Desarme é quando a defesa a "
        "desativa. Estas comparações usam plants feitos com o round ainda em disputa."
    )
    plants = context.data.plants()
    plants = plants[plants["match_id"].isin(context.selected_match_ids)]
    plants_column, defuse_column, time_column = st.columns(3)
    plants_column.metric("Rounds com spike plantada", len(plants))
    defuse_column.metric("Desarmados pela defesa", display_number(plants["defusada"].mean(), ".1%"))
    time_column.metric(
        "Segundo típico do plant (mediana)",
        display_number(plants["segundos_plant"].median(), ".0f", " s"),
        help="Mediana contada desde o fim da fase de compra. Metade dos plants ocorreu antes e metade depois.",
    )
    _show_players_alive(plants)
    _show_defuses_by_time_and_site(plants, context)
    _show_plant_locations(plants, context)
    _show_player_positions(context)


def _show_players_alive(plants: pd.DataFrame) -> None:
    st.subheader("1. Quantos estão vivos no momento do plant é o que mais decide")
    st.caption(
        "Cada quadrado combina a quantidade de atacantes e defensores vivos quando "
        "a spike foi plantada. A taxa é a parte desses rounds em que houve desarme."
    )
    rates, counts = situation_matrix(plants)
    st.altair_chart(
        heatmap_chart(
            rates,
            counts,
            "defensores vivos no momento do plant",
            "atacantes vivos no momento do plant",
            "% de spikes desarmadas",
        ),
        width="stretch",
    )


def _defuse_comparison(table: pd.DataFrame, group_column: str):
    """Compara a taxa do grupo com a média das situações numéricas que ele reuniu."""
    return dumbbell_chart(
        table,
        group_column,
        "esperado_pelos_vivos",
        "defuse",
        "esperado pelos vivos",
        "desarmado de fato",
        "% de spikes desarmadas",
        count_column="plants",
        x_domain=[0, 0.6],
    )


def _show_defuses_by_time_and_site(plants: pd.DataFrame, context: AppContext) -> None:
    st.subheader("2. O segundo do plant e o site mudam a chance de desarme?")
    st.caption(
        "A comparação por jogadores vivos usa a taxa de desarme dos plants com "
        "a mesma quantidade de jogadores de cada lado. Um plant com 3 atacantes "
        "e 2 defensores usa a taxa dos casos de 3 contra 2 nesta seleção. "
        "Em cada grupo, fazemos a média dessas taxas, com mais peso para as "
        "situações mais frequentes. É uma comparação dos dados, sem prever o "
        "resultado nem medir o efeito do local ou do tempo."
    )
    time_column, site_column = st.columns(2)
    time_column.markdown("**Pelo segundo em que a spike foi plantada**")
    rates_by_time = summary_by_plant_time(plants)
    time_column.altair_chart(
        _defuse_comparison(
            rates_by_time[rates_by_time["plants"] >= 20],
            "faixa_tempo",
        ),
        width="stretch",
    )
    time_column.caption("São mostradas faixas com pelo menos 20 plants.")
    rates_by_site = summary_by_site(plants).rename(index=context.map_names, level="mapa")
    named_sites = rates_by_site[rates_by_site["plants"] >= 100].reset_index()
    named_sites["mapa_site"] = named_sites["mapa"] + " " + named_sites["site"]
    site_column.markdown("**Por mapa e site**, sites com 100 ou mais plants")
    site_column.caption(
        "Site é a área do mapa em que a spike pode ser plantada. São mostrados sites com pelo menos 100 plants."
    )
    site_column.altair_chart(
        _defuse_comparison(
            named_sites.set_index("mapa_site"),
            "mapa_site",
        ),
        width="stretch",
    )
    with st.expander("Números por mapa e site"):
        display_table(rates_by_site, width="content", container=st)


def _show_plant_locations(plants: pd.DataFrame, context: AppContext) -> None:
    st.subheader("3. Onde a spike é plantada, e quais posições a defesa desarma mais")
    selected_map, map_metadata = select_map(
        context,
        "Mapa",
        plants["mapa"].value_counts().index,
        "plant_map",
    )
    if map_metadata is None:
        st.info("Este mapa não tem imagem disponível.")
        return
    plant_cells = cells_for_map(plants, selected_map)
    map_defuse_rate = plants.loc[plants["mapa"] == selected_map, "defusada"].mean()
    st.caption("Cada marca junta os plants feitos num quadrado de cerca de 4 metros, só quadrados com 5 ou mais plants, com uma imagem por site. Tamanho da bola é maior de acordo com a quantidade de plants. Cor e forma mostram quantos foram desarmados, em relação à média do mapa")
    sites = sorted(plant_cells["site"].unique())
    if not sites:
        st.info("Nenhum quadrado reúne pelo menos 5 plants nesta seleção.")
        return
    for site_column, site in zip(st.columns(len(sites)), sites):
        site_cells = plant_cells[plant_cells["site"] == site]
        shown_plants = int(site_cells["plants"].sum())
        site_column.markdown(f"**Site {site}** ({shown_plants} plants nos quadrados mostrados)")
        site_column.pyplot(
            draw_rate_markers(
                map_metadata,
                site_cells,
                "plants",
                "defuse",
                map_defuse_rate,
                "taxa de defuse",
                label_min_count=10**9,
                size_per_unit=3,
                zoom_padding=90,
            ),
            alt=f"Plants no site {site}. Quantidades e taxas de desarme estão na tabela.",
            width="stretch",
        )
    with st.expander("Números de cada quadrado"):
        display_table(
            plant_cells[
                [
                    "site",
                    "plants",
                    "defuse",
                    "esperado_pelos_vivos",
                    "acima_do_esperado",
                ]
            ],
            width="content",
            container=st,
        )


def _show_player_positions(context: AppContext) -> None:
    st.subheader("4. O posicionamento no momento do plant muda o desarme? E como a defesa retoma o site?")
    st.caption("No instante do plant, comparado com o esperado pelos vivos. Atacantes no site mostra quantos estavam a menos de 15 metros da spike. Olhando para fora a parte dos aliados de quem plantou que estava de costas para a spike, ou seja, vigiando as entradas. Distância da defesa é a mediana da distância dos defensores até a spike.")
    setups = context.data.setups()
    setups = setups[setups["match_id"].isin(context.selected_match_ids)]
    attackers_column, watching_column, defense_column = st.columns(3)
    attackers_column.markdown("**Atacantes a menos de 15 m da spike**")
    attackers_column.caption(
        "Quantidade a até 1500 unidades da spike. Estar perto não garante estar dentro do site."
    )
    attackers_column.altair_chart(
        _defuse_comparison(
            defuse_by(setups, "atacantes_no_site"),
            "atacantes_no_site",
        ),
        width="stretch",
    )
    watching_column.markdown("**Parte dos aliados de quem plantou olhando para fora do site**")
    watching_column.caption(
        "Fração dos aliados de quem plantou. Isso não mostra se vigiavam uma entrada ou conseguiam atirar."
    )
    watching_column.altair_chart(
        _defuse_comparison(
            defuse_by(setups, watching_bands(setups)),
            "fracao_olhar_oposto_spike",
        ),
        width="stretch",
    )
    defense_column.markdown("**Distância da defesa até a spike no momento do plant**")
    defense_column.caption(
        "Mediana das distâncias dos defensores vivos no plant, em unidades do jogo."
    )
    defense_distances = defuse_by(setups, "faixa_defesa")
    defense_column.altair_chart(
        _defuse_comparison(
            defense_distances,
            "faixa_defesa",
        ),
        width="stretch",
    )
    st.markdown("**Quando a defesa desarmou, quantos atacantes ainda estavam vivos e a que distância da spike estava o mais próximo**")
    st.caption(
        "A tabela conta os atacantes vivos no instante do desarme e a distância "
        "do mais próximo. A distância central é a mediana, em unidades do jogo. "
        "Também mostramos a frequência de casos sem atacante a até 1500 unidades."
    )
    display_table(retake_summary(setups), width="content", container=st)
