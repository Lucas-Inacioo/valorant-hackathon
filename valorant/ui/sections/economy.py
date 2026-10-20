"""Equipamento inicial, resultados e economia do round seguinte."""

import pandas as pd
import streamlit as st

from valorant.analysis.economy import (
    after_previous_round,
    after_streak,
    close_match_ids,
    pistol_by_side,
    second_round_cycle,
    versus_full_buy,
    win_rate_by_loadout,
    win_rate_matrix,
)
from valorant.analysis.fights import (
    economic_first_death,
    next_loadout_by_outcome,
    post_plant_exchange,
    save_effect,
)
from valorant.ui.charts import (
    ATTACK_COLOR,
    LOST_COLOR,
    NEUTRAL_COLOR,
    TRADE_COLOR,
    WON_COLOR,
    dumbbell_chart,
    grouped_bar_chart,
    heatmap_chart,
    rate_chart,
)
from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table


def render(context: AppContext) -> None:
    st.header("Economia")
    st.caption(
        "O valor do equipamento inicial é a soma registrada para os cinco jogadores "
        "da equipe, em créditos. Parte desse equipamento pode ter vindo do round "
        "anterior. O saldo de créditos e o gasto na compra são outras medidas."
    )
    team_rounds = context.data.rounds()
    team_rounds = team_rounds[team_rounds["match_id"].isin(context.selected_match_ids)]
    fights = context.data.fights()
    fights = fights[fights["match_id"].isin(context.selected_match_ids)]
    _show_equipment_and_results(team_rounds)
    _show_following_rounds(team_rounds)
    _show_pistol_cycles(team_rounds)
    _show_first_victim_and_survivors(team_rounds, fights)
    _show_next_equipment_and_post_plant(team_rounds, fights, context)


def _show_equipment_and_results(team_rounds: pd.DataFrame) -> None:
    st.subheader("Equipamento inicial e vitórias")
    own_equipment, equipment_difference = win_rate_by_loadout(team_rounds)
    difference_column, opponent_column = st.columns(2)
    difference_column.markdown("**Diferença de equipamento entre as equipes**")
    difference_column.caption(
        "Acima de zero, o equipamento desta equipe valia mais que o do adversário. "
        "Este gráfico inclui todos os rounds."
    )
    difference_column.altair_chart(
        rate_chart(
            equipment_difference,
            "faixa_diferenca",
            "vitoria",
            "rounds",
            "% de rounds vencidos",
        ),
        width="stretch",
    )
    opponent_column.markdown("**Contra adversários com mais de 20 mil créditos em equipamento**")
    opponent_column.caption(
        "O eixo separa as equipes pelo valor do próprio equipamento. "
        "Ficam fora os rounds de pistol e os rounds 2 e 14."
    )
    opponent_column.altair_chart(
        rate_chart(
            versus_full_buy(team_rounds),
            "faixa_loadout",
            "vitoria",
            "rounds",
            "% de rounds vencidos",
        ),
        width="stretch",
    )
    with st.expander("Tabelas de equipamento e resultados"):
        st.caption(
            "A variação por mil créditos compara as taxas de faixas vizinhas, "
            "levando em conta a diferença entre seus valores médios de equipamento. "
            "Ela descreve essas faixas e não mede o efeito de gastar mais."
        )
        display_table(versus_full_buy(team_rounds), width="content", container=st)
        display_table(own_equipment, width="content", container=st)
        rates, counts = win_rate_matrix(team_rounds)
        st.altair_chart(
            heatmap_chart(
                rates,
                counts,
                "equipamento inicial do adversário",
                "equipamento inicial da equipe",
                "% de rounds vencidos",
            ),
            width="stretch",
        )


def _equipment_comparison(table: pd.DataFrame, group_column: str, rate_label: str):
    return dumbbell_chart(
        table,
        group_column,
        "esperado_pelo_dinheiro",
        "vitoria",
        "comparação por equipamento inicial",
        "vitórias observadas",
        rate_label,
        count_column="rounds",
        x_domain=[0, 1],
    )


def _show_following_rounds(team_rounds: pd.DataFrame) -> None:
    st.subheader("Resultados depois de uma vitória ou derrota")
    st.caption(
        "A comparação por equipamento usa a taxa de vitória dos rounds com uma "
        "diferença parecida no valor inicial das duas equipes. A referência deixa "
        "de fora os rounds 1, 2, 13 e 14. Cada grupo reúne essas taxas pela frequência "
        "das faixas que contém. A diferença para essa média também pode refletir "
        "a força das equipes e outros fatores da partida."
    )
    st.caption(
        "Clutch e thrifty são destaques registrados pelo jogo para certas vitórias. "
        "Eles formam um grupo separado de derrotas aqui, sem indicar que o round era fácil."
    )
    close_rounds = team_rounds[team_rounds["match_id"].isin(close_match_ids(team_rounds))]
    all_column, close_column = st.columns(2)
    result_labels = {
        "perdeu round fácil (clutch ou thrifty do adversário)": "perdeu para clutch ou thrifty",
    }
    all_column.markdown("**Todas as partidas**")
    all_column.altair_chart(
        _equipment_comparison(
            after_previous_round(team_rounds).rename(index=result_labels),
            "anterior",
            "% de rounds seguintes vencidos",
        ),
        width="stretch",
    )
    close_match_count = close_rounds["match_id"].nunique()
    close_column.markdown(f"**Partidas com placar final próximo** com {close_match_count} partidas")
    close_column.caption(
        "São partidas que terminaram com até 4 rounds de diferença. "
        "A seleção usa o resultado final e não garante equipes de força parecida."
    )
    close_column.altair_chart(
        _equipment_comparison(
            after_previous_round(close_rounds).rename(index=result_labels),
            "anterior",
            "% de rounds seguintes vencidos",
        ),
        width="stretch",
    )
    streak_column, close_streak_column = st.columns(2)
    streak_column.markdown("**Derrotas seguidas antes do round em todas as partidas**")
    streak_column.altair_chart(
        _equipment_comparison(
            after_streak(team_rounds),
            "derrotas",
            "% de rounds vencidos",
        ),
        width="stretch",
    )
    close_streak_column.markdown("**Derrotas seguidas nas partidas com placar final próximo**")
    close_streak_column.altair_chart(
        _equipment_comparison(
            after_streak(close_rounds),
            "derrotas",
            "% de rounds vencidos",
        ),
        width="stretch",
    )


def _show_pistol_cycles(team_rounds: pd.DataFrame) -> None:
    st.subheader("Os três rounds depois do pistol")
    st.caption(
        "Pistol é o primeiro round de cada metade, nos rounds 1 e 13. "
        "O gráfico acompanha quem perdeu esse round. As faixas eco, leve e force "
        "agrupam o valor do equipamento no round seguinte, até 4 mil, de 4 a 8 mil "
        "e acima de 8 mil créditos."
    )
    pistol_column, cycle_column = st.columns([1, 3])
    pistol_column.markdown("**Vitórias no pistol por lado**")
    display_table(pistol_by_side(team_rounds), width="content", container=pistol_column)
    overall_cycles, cycles_by_side = second_round_cycle(team_rounds)
    cycle_column.markdown("**Vitórias nos três rounds seguintes de quem perdeu o pistol**")
    cycle_column.caption(
        "As três taxas e a soma usam os mesmos ciclos completos. "
        "Se a partida terminou antes, o ciclo aparece na tabela como incompleto. "
        "A comparação descreve os grupos observados e não recomenda uma compra."
    )
    cycle_column.altair_chart(
        grouped_bar_chart(
            overall_cycles[["vitoria_round_2", "vitoria_round_3", "vitoria_round_4"]].rename(
                columns={
                    "vitoria_round_2": "primeiro round depois do pistol",
                    "vitoria_round_3": "segundo round depois do pistol",
                    "vitoria_round_4": "terceiro round depois do pistol",
                }
            ),
            [WON_COLOR, TRADE_COLOR, NEUTRAL_COLOR],
            "% de rounds vencidos nos ciclos completos",
        ),
        width="stretch",
    )
    with st.expander("Números dos ciclos no total e por lado"):
        st.caption(
            "A taxa anterior usa somente rounds que aconteceram antes do pistol. "
            "Ela fica vazia quando não há rounds anteriores."
        )
        display_table(overall_cycles, width="stretch", container=st)
        display_table(cycles_by_side, width="stretch", container=st)


def _show_first_victim_and_survivors(team_rounds: pd.DataFrame, fights: pd.DataFrame) -> None:
    st.subheader("Equipamento da primeira vítima e jogadores que sobreviveram")
    st.caption(
        "As primeiras mortes são comparadas com a taxa de vitória da equipe "
        "na própria partida. As armas e os valores são os do início do round."
    )
    expensive_column, operator_column = st.columns(2)
    expensive_column.markdown("**Primeira vítima com o equipamento mais caro da equipe**")
    expensive_column.caption("O grupo só inclui o maior valor quando não há empate com um aliado.")
    display_table(
        economic_first_death(fights, "mais_caro_do_time"),
        width="content",
        container=expensive_column,
    )
    operator_column.markdown("**Primeira vítima que começou com Operator**")
    display_table(
        economic_first_death(
            fights.assign(operator=fights["arma_vitima"] == "Operator"),
            "operator",
        ),
        width="content",
        container=operator_column,
    )
    surviving_players = save_effect(team_rounds, fights)
    surviving_players = surviving_players[surviving_players["rounds"] >= 20]
    st.caption(
        "Abaixo contamos os jogadores vivos ao fim dos rounds perdidos. "
        "Só aparecem grupos com pelo menos 20 rounds. Ficam fora as transições "
        "em que a economia é reiniciada, como a troca de metade."
    )
    equipment_column, wins_column = st.columns(2)
    equipment_column.markdown("**Equipamento inicial no round seguinte**")
    equipment_column.bar_chart(
        surviving_players["loadout_seguinte"],
        color=[WON_COLOR],
        y_label="valor do equipamento inicial em créditos",
        x_label="sobreviventes",
    )
    wins_column.markdown("**Vitórias no round seguinte**")
    wins_column.altair_chart(
        rate_chart(
            surviving_players,
            "sobreviventes",
            "venceu_seguinte",
            "rounds",
            "% de rounds seguintes vencidos",
            height=170,
        ),
        width="stretch",
    )


def _show_next_equipment_and_post_plant(
    team_rounds: pd.DataFrame,
    fights: pd.DataFrame,
    context: AppContext,
) -> None:
    st.subheader("Sobreviventes e mortes depois do plant")
    st.caption(
        "Plant é a instalação da spike. Estes dados mostram quem sobreviveu e "
        "quem morreu depois disso, mas não registram quem estava caçando um adversário."
    )
    equipment_column, exchange_column = st.columns(2)
    next_equipment, round_counts = next_loadout_by_outcome(team_rounds, fights)
    equipment_column.markdown("**Equipamento no round seguinte por resultado e sobreviventes**")
    equipment_column.altair_chart(
        grouped_bar_chart(
            next_equipment.rename_axis(index="sobreviventes"),
            [WON_COLOR, LOST_COLOR],
            "valor do equipamento inicial em créditos",
            ",.0f",
        ),
        width="stretch",
    )
    plants = context.data.plants()
    plants = plants[plants["match_id"].isin(context.selected_match_ids)]
    post_plant_deaths = post_plant_exchange(plants, fights)
    exchange_column.markdown("**Mortes do ataque entre as mortes depois do plant**")
    exchange_column.caption(
        "Só entram rounds que o ataque venceu. Em 3 contra 2, por exemplo, "
        "havia 3 atacantes e 2 defensores vivos no plant. Essa taxa não inclui "
        "os rounds em que o ataque perdeu."
    )
    exchange_column.altair_chart(
        rate_chart(
            post_plant_deaths,
            "situacao",
            "parte_do_ataque",
            "mortes_pos_plant",
            "% das mortes após o plant que são de atacantes",
            color=ATTACK_COLOR,
        ),
        width="stretch",
    )
    with st.expander("Números por sobreviventes e jogadores vivos no plant"):
        display_table(
            round_counts.rename(columns=lambda column: f"rounds em que {column}"),
            width="content",
            container=st,
        )
        display_table(post_plant_deaths, width="content", container=st)
