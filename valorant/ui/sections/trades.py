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
        "Distância a partir da qual a morte conta como isolada (unidades do jogo, cerca de 100 por metro)",
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
        help="Depois do plant os papéis se invertem: a defesa precisa entrar no site para desarmar.",
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
    deaths_column.metric("Mortes", len(deaths))
    trades_column.metric("Mortes trocadas", display_number(deaths["trocada"].mean(), ".0%"))
    isolated_column.metric(
        "Mortes isoladas (entre as que tinham aliado vivo)",
        display_number(deaths_with_allies["isolada"].mean(), ".0%"),
        help="Calculada somente entre mortes com pelo menos um aliado vivo.",
    )
    missed_column.metric(
        "Trocas possíveis que não aconteceram",
        display_number(1 - nearby_and_facing["trocada"].mean(), ".0%"),
        help="Casos com um aliado a até 2000 unidades do adversário e com o olhar voltado para ele.",
    )
    st.caption(
        "Entram mortes causadas por adversários com o round ainda em disputa. "
        "A distância dos aliados só é comparada quando havia pelo menos um deles vivo. "
        "Uma troca no mesmo instante entra na contagem, mas não comprova reação."
    )


def _show_win_differences(deaths_with_allies: pd.DataFrame) -> None:
    st.subheader("1. Quanto vale trocar abates, e quanto vale ter um aliado perto?")
    st.caption(
        "O eixo mostra quantos aliados da vítima continuaram vivos no instante em que ela morreu. "
        "Por exemplo, a barra 1 reúne mortes em que a equipe tinha 2 vivos e ficou com 1. "
        "Cada barra compara a taxa de vitória do round entre mortes trocadas e não trocadas "
        "ou entre mortes com aliado perto e sem. A comparação só junta mortes com o mesmo número "
        "de aliados e de inimigos vivos nesse instante, para não refletir o fato de a equipe já "
        "estar em vantagem numérica. Valores acima de zero ajudam a vencer o round. Exemplo de "
        "leitura da barra 1 em morte trocada: a situação era 2x2, um jogador morreu e virou 1x2. "
        "Se o aliado que sobrou trocou o abate, virou 1x1. A barra diz que, com a troca, a equipe "
        "vence cerca de 16 pontos a mais do que ficando no 1x2 sem trocar. A barra é a média de "
        "todas as quantidades de inimigos (1x1, 1x2, 1x3 e assim por diante), por isso o exemplo "
        "é uma ilustração."
    )
    for condition, label in [
        ("trocada", "Morte trocada"),
        ("aliado_perto", "Aliado a menos do limite de isolamento"),
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
                    index="aliados da vítima vivos no instante da morte"
                ),
                [ATTACK_COLOR, DEFENSE_COLOR],
                "diferença na vitória",
                "+.0%",
                height=260,
            ),
            width="stretch",
        )
        with st.expander(f"Números de cada situação (aliados x inimigos vivos): {label.lower()}"):
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
    st.subheader("2. Quando a troca era possível, ela aconteceu?")
    st.caption(
        "Um aliado está perto quando fica a até 2000 unidades do adversário que "
        "fez o abate. O olhar está voltado para ele quando a diferença de direção "
        "é de até 45 graus. Distância e direção não mostram se havia uma parede, "
        "fumaça ou outra barreira ao tiro."
    )
    trade_groups = trade_possibility_summary(fights, ["lado"]).rename(
        index={
            TRADE_POSSIBLE: "aliado perto, olhando para o inimigo",
            "aliado em alcance olhando para outro lado": "aliado perto, olhando para outro lado",
            "sem aliado em alcance": "nenhum aliado perto",
        },
        level="troca_possivel",
    )
    trades_column, wins_column = st.columns(2)
    trades_column.markdown("**Quantas mortes foram trocadas**, considerando se algum aliado da vítima estava a menos de 20 m do inimigo que a matou e olhando para ele")
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
    wins_column.markdown("**Quantos rounds a equipe da vítima venceu**, nas mesmas três situações")
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
    st.subheader("3. A que distância do aliado mais próximo o jogador morreu?")
    st.caption(
        "Mortes agrupadas pela distância até o aliado vivo mais próximo, em unidades do jogo "
        "(100 unidades são cerca de 1 metro). Morte trocada: quantas foram trocadas. "
        "Equipe venceu o round: quantos desses rounds a equipe da vítima ainda venceu."
    )
    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_deaths = deaths_with_allies[deaths_with_allies["lado"] == side]
        side_column.markdown(f"**Jogador que morreu estava {SIDE_PHRASES[side]}**")
        distance_rates = summary_by_distance_band(side_deaths)[["fracao_trocadas", "venceu_round"]]
        distance_rates = distance_rates.rename(
            columns={
                "fracao_trocadas": "morte trocada",
                "venceu_round": "equipe venceu o round",
            }
        ).rename_axis(index="distância até o aliado mais próximo (unidades do jogo)")
        side_column.altair_chart(
            grouped_bar_chart(
                distance_rates,
                [TRADE_COLOR, WON_COLOR],
                "% das mortes",
            ),
            width="stretch",
        )
    with st.expander("Números por lado e resultado do round, e o primeiro abate separado em isolado ou trocado"):
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
            side_column.markdown(f"**Primeira morte do round, jogador que morreu estava {SIDE_PHRASES[side]}**")
            display_table(first_deaths, hide_index=True, width="content", container=side_column)


def _show_ally_and_region_comparison(deaths_with_allies: pd.DataFrame) -> None:
    st.subheader("4. Onde estavam os aliados, e a morte foi em área própria ou do adversário?")
    allies_column, region_column = st.columns(2)
    allies_column.markdown("**Quantos rounds a equipe venceu**, conforme onde estavam os aliados")
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
    region_column.markdown("**Quantos rounds a equipe venceu**, conforme de quem é a região")
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
    with st.expander("Números de posição dos aliados e de região, e o isolamento separado por função do agente"):
        display_table(allies_summary, width="content", container=st)
        display_table(
            territory_summary(deaths_with_allies, ["lado"]), width="content", container=st
        )
        st.markdown(
            "**Por função do agente.** Acima do esperado: taxa de vitória do round menos o esperado "
            "para a mesma quantidade de vivos. Custo do isolamento: essa mesma conta para mortes "
            "isoladas menos para mortes acompanhadas."
        )
        display_table(death_cost_by_role(deaths_with_allies), width="content", container=st)


def _show_team_trades(fights: pd.DataFrame, context: AppContext) -> None:
    st.subheader("5. Quantas trocas possíveis viraram troca? Por equipe")
    st.caption(
        "Só equipes com 150 ou mais mortes. Uma troca é possível quando um aliado estava a menos "
        "de 20 m de quem matou, olhando para ele, e é considerada uma troca convertida quando ela "
        "de fato ocorreu. O dano no autor do abate é o total registrado durante o round, por isso "
        "não mostra uma reação a essa morte."
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
