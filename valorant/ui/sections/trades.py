"""Trocas de abates e posição dos aliados no momento de uma morte."""

import pandas as pd
import streamlit as st

from valorant.analysis.agent_roles import death_cost_by_role
from valorant.analysis.deaths import (
    SOLO_DISTANCE,
    context_summary,
    first_death_summary,
    summary_by_distance_band,
    summary_by_round_outcome,
    territory_summary,
    win_rate_by_situation,
    with_solo_flag,
)
from valorant.analysis.fights import TRADE_POSSIBLE, team_summary, trade_possibility_summary
from valorant.ui.charts import (
    ATTACK_COLOR,
    DEFENSE_COLOR,
    ROUND_OUTCOME_LABELS,
    SIDE_COLORS,
    SIDE_PHRASES,
    TRADE_COLOR,
    WON_COLOR,
    grouped_bar_chart,
    rate_chart,
)
from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table
from valorant.ui.tables import display_number


def render(context: AppContext) -> None:
    st.header("Trocas e isolamento")
    st.caption(
        "Uma morte conta como trocada quando um aliado mata o adversário que a "
        "causou em até 5 segundos. Uma morte é isolada quando todos os aliados "
        "vivos estão além da distância escolhida abaixo."
    )
    distance_column, phase_column = st.columns(2)
    isolation_distance = distance_column.slider(
        "Distância para considerar uma morte isolada",
        500,
        3000,
        SOLO_DISTANCE,
        step=250,
        help="Distância em unidades do jogo. Uma conversão para metros seria apenas aproximada.",
    )
    phase = phase_column.radio(
        "Momento do round",
        ["todas", "pré-plant", "pós-plant"],
        horizontal=True,
        format_func={
            "todas": "Todos",
            "pré-plant": "Antes do plant",
            "pós-plant": "Depois do plant",
        }.get,
        help="Plant é a instalação da spike. Depois dele, a defesa precisa desarmá-la.",
    )
    deaths = context.data.deaths()
    deaths = deaths[deaths["diagnostico_tatico"]].copy()
    fights = context.data.fights()
    fights = fights[fights["diagnostico_tatico"]].copy()
    if phase != "todas":
        deaths = deaths[deaths["fase"] == phase]
        fights = fights[fights["fase"] == phase]
    deaths_with_allies = with_solo_flag(deaths, isolation_distance)
    deaths_with_allies["aliado_perto"] = ~deaths_with_allies["isolada"]
    _show_summary(deaths, deaths_with_allies, fights)
    _show_win_differences(deaths_with_allies)
    _show_nearby_ally_comparison(fights)
    _show_distance_bands(deaths_with_allies)
    _show_ally_and_region_comparison(deaths_with_allies)
    _show_team_trades(fights, context)


def _show_summary(
    deaths: pd.DataFrame, deaths_with_allies: pd.DataFrame, fights: pd.DataFrame
) -> None:
    nearby_and_facing = fights[fights["troca_possivel"] == TRADE_POSSIBLE]
    deaths_column, trades_column, isolated_column, missed_column = st.columns(4)
    deaths_column.metric("Mortes analisadas", len(deaths))
    trades_column.metric("Mortes trocadas", display_number(deaths["trocada"].mean(), ".0%"))
    isolated_column.metric(
        "Mortes isoladas",
        display_number(deaths_with_allies["isolada"].mean(), ".0%"),
        help="Calculada somente entre mortes com pelo menos um aliado vivo.",
    )
    missed_column.metric(
        "Sem troca com aliado perto e olhando",
        display_number(1 - nearby_and_facing["trocada"].mean(), ".0%"),
        help="Casos com um aliado a até 2000 unidades do adversário e com o olhar voltado para ele.",
    )
    st.caption(
        "Entram mortes causadas por adversários com o round ainda em disputa. "
        "A distância dos aliados só é comparada quando havia pelo menos um deles vivo. "
        "Uma troca no mesmo instante entra na contagem, mas não comprova reação."
    )


def _show_win_differences(deaths_with_allies: pd.DataFrame) -> None:
    st.subheader("Diferença nas vitórias com troca ou aliado perto")
    st.caption(
        "Comparamos mortes com e sem cada condição, mantendo iguais as quantidades "
        "de aliados e adversários vivos. Cada barra reúne essas diferenças por "
        "quantidade de aliados, com mais peso para as situações com mais mortes. "
        "O mesmo round pode entrar várias vezes. Essa comparação não mede o "
        "efeito da troca ou a qualidade da decisão."
    )
    for condition, label in [
        ("trocada", "Morte trocada em até 5 segundos"),
        ("aliado_perto", "Pelo menos um aliado dentro do limite de isolamento"),
    ]:
        situations = win_rate_by_situation(deaths_with_allies, condition)
        if situations.empty:
            st.info(f"Não há casos suficientes para comparar {label.lower()} nesta seleção.")
            continue
        situations["aliados_apos_morte"] = situations["situacao"].str.split("v").str[0].astype(int)
        weighted_differences = (situations["diferenca"] * situations["mortes"]).groupby(
            [situations["aliados_apos_morte"], situations["lado"]]
        ).sum() / situations.groupby(["aliados_apos_morte", "lado"])["mortes"].sum()
        st.markdown(f"**{label}**")
        st.altair_chart(
            grouped_bar_chart(
                weighted_differences.unstack("lado").rename_axis(
                    index="aliados vivos após a morte"
                ),
                [ATTACK_COLOR, DEFENSE_COLOR],
                "diferença na taxa de vitória",
                "+.0%",
                height=260,
            ),
            width="stretch",
        )
        with st.expander(f"Números por jogadores vivos para {label.lower()}"):
            st.caption(
                "Em 3 contra 2, por exemplo, restavam 3 aliados da vítima e "
                "2 adversários. Cada situação precisa ter pelo menos 60 mortes, "
                "com 15 ou mais em cada grupo, para entrar na comparação."
            )
            display_table(
                situations.drop(columns=["aliados_apos_morte"]),
                hide_index=True,
                width="content",
                container=st,
            )


def _show_nearby_ally_comparison(fights: pd.DataFrame) -> None:
    st.subheader("Aliado perto do adversário e troca observada")
    st.caption(
        "Um aliado está perto quando fica a até 2000 unidades do adversário que "
        "fez o abate. O olhar está voltado para ele quando a diferença de direção "
        "é de até 45 graus. Distância e direção não mostram se havia uma parede, "
        "fumaça ou outra barreira ao tiro."
    )
    trade_groups = trade_possibility_summary(fights, ["lado"]).rename(
        index={
            TRADE_POSSIBLE: "aliado perto e olhando para o adversário",
            "aliado em alcance olhando para outro lado": "aliado perto e olhando para outro lado",
            "sem aliado em alcance": "nenhum aliado perto",
        },
        level="troca_possivel",
    )
    trades_column, wins_column = st.columns(2)
    trades_column.markdown("**Mortes trocadas em cada grupo**")
    trades_column.altair_chart(
        rate_chart(
            trade_groups,
            "troca_possivel",
            "trocada",
            "mortes",
            "% de mortes trocadas",
            group_column="lado",
            group_colors=SIDE_COLORS,
        ),
        width="stretch",
    )
    wins_column.markdown("**Vitórias da equipe da vítima nos mesmos grupos**")
    wins_column.altair_chart(
        rate_chart(
            trade_groups,
            "troca_possivel",
            "venceu_round",
            "mortes",
            "% de rounds vencidos pela equipe da vítima",
            group_column="lado",
            group_colors=SIDE_COLORS,
        ),
        width="stretch",
    )


def _show_distance_bands(deaths_with_allies: pd.DataFrame) -> None:
    st.subheader("Distância até o aliado mais próximo")
    st.caption(
        "As distâncias são medidas em unidades do jogo no momento da morte. "
        "Cada faixa mostra a parte das mortes que foi trocada e a parte em que "
        "a equipe da vítima venceu o round."
    )
    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_deaths = deaths_with_allies[deaths_with_allies["lado"] == side]
        side_column.markdown(f"**Vítima {SIDE_PHRASES[side]}**")
        distance_rates = summary_by_distance_band(side_deaths)[["fracao_trocadas", "venceu_round"]]
        distance_rates = distance_rates.rename(
            columns={
                "fracao_trocadas": "morte trocada",
                "venceu_round": "equipe venceu o round",
            }
        ).rename_axis(index="distância até o aliado mais próximo em unidades do jogo")
        side_column.altair_chart(
            grouped_bar_chart(
                distance_rates,
                [TRADE_COLOR, WON_COLOR],
                "% das mortes",
            ),
            width="stretch",
        )
    with st.expander("Números por lado e resultado, com as primeiras mortes separadas"):
        display_table(
            summary_by_round_outcome(deaths_with_allies, ["lado"]).rename(
                index=ROUND_OUTCOME_LABELS,
                level="venceu_round",
            ),
            width="content",
            container=st,
        )
        for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
            first_deaths = first_death_summary(
                deaths_with_allies[deaths_with_allies["lado"] == side]
            ).reset_index()
            first_deaths["isolada"] = first_deaths["isolada"].map(
                {False: "acompanhada", True: "isolada"}
            )
            first_deaths["trocada"] = first_deaths["trocada"].map(
                {False: "não trocada", True: "trocada"}
            )
            side_column.markdown(f"**Primeira vítima {SIDE_PHRASES[side]}**")
            display_table(first_deaths, hide_index=True, width="content", container=side_column)


def _show_ally_and_region_comparison(deaths_with_allies: pd.DataFrame) -> None:
    st.subheader("Posição dos aliados e ocupação da região")
    allies_column, region_column = st.columns(2)
    allies_column.markdown("**Vitórias conforme a posição dos aliados**")
    allies_column.caption(
        "Em grupo significa ter um aliado dentro do limite escolhido. "
        "Separado do grupo significa estar longe dos aliados, com pelo menos "
        "dois deles na mesma grande região. Os demais casos contam como isolados."
    )
    allies_summary = context_summary(deaths_with_allies, ["lado"]).rename(
        index={"flanco": "separado do grupo"},
        level="contexto",
    )
    allies_column.altair_chart(
        rate_chart(
            allies_summary,
            "contexto",
            "venceu_round",
            "mortes",
            "% de rounds vencidos pela equipe da vítima",
            group_column="lado",
            group_colors=SIDE_COLORS,
            order=["em grupo", "separado do grupo", "isolado", "último vivo"],
        ),
        width="stretch",
    )
    region_column.markdown("**Vitórias conforme a ocupação da região**")
    region_column.caption(
        "A ocupação usa posições dos primeiros confrontos até 20 segundos, "
        "com um registro por round. A região é própria quando pelo menos 65% "
        "das posições são do lado da vítima e do adversário quando são até 35%. "
        "Entre esses valores, ela é disputada."
    )
    known_regions = deaths_with_allies[deaths_with_allies["territorio"] != "?"]
    region_column.altair_chart(
        rate_chart(
            territory_summary(known_regions, ["lado"]),
            "territorio",
            "venceu_round",
            "mortes",
            "% de rounds vencidos pela equipe da vítima",
            group_column="lado",
            group_colors=SIDE_COLORS,
            order=["próprio", "disputado", "do adversário"],
        ),
        width="stretch",
    )
    with st.expander("Números de posição, região e função do agente"):
        display_table(allies_summary, width="content", container=st)
        display_table(
            territory_summary(deaths_with_allies, ["lado"]), width="content", container=st
        )
        st.markdown("**Isolamento por função do agente**")
        st.caption(
            "A comparação por jogadores vivos usa a taxa de vitória com a mesma "
            "quantidade de aliados e adversários. A diferença para essa taxa é "
            "calculada primeiro em cada grupo. Depois comparamos as mortes "
            "isoladas com as acompanhadas."
        )
        display_table(death_cost_by_role(deaths_with_allies), width="content", container=st)


def _show_team_trades(fights: pd.DataFrame, context: AppContext) -> None:
    st.subheader("Trocas por equipe")
    st.caption(
        "Só entram equipes com pelo menos 150 mortes analisadas. A tabela mostra "
        "quantas mortes foram trocadas quando havia aliado perto e olhando para "
        "o adversário. O dano no autor do abate é o total registrado durante "
        "o round, por isso não mostra uma reação a essa morte."
    )
    named_fights = fights.assign(
        time_killer=fights["time_vitima"].map({"Blue": "Red", "Red": "Blue"})
    )
    named_fights = context.data.with_team_names(
        context.data.with_team_names(named_fights, "time_vitima"),
        "time_killer",
        "nome_killer",
    )
    display_table(team_summary(named_fights), width="stretch", container=st)
