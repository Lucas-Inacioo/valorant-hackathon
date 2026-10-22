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
    st.markdown(
        "Loadout é o valor das armas e escudos dos cinco jogadores. Rounds normais são todos menos o pistol "
        "(rounds 1 e 13) e o segundo round de cada metade (2 e 14). Vitória esperada pelo dinheiro é a taxa "
        "de vitória normal para a diferença de loadout vista entre as equipes."
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
    st.subheader("1. Quanto o dinheiro gasto em armas compra de rounds?")
    own_equipment, equipment_difference = win_rate_by_loadout(team_rounds)
    difference_column, opponent_column = st.columns(2)
    difference_column.markdown(
        "**Diferença de loadout entre a equipe e o adversário.** Acima de zero, a equipe gastou mais. (todos os rounds)"
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
    opponent_column.markdown(
        "**Pelo loadout da equipe quando o adversário comprou tudo** (20 mil ou mais, rounds normais)"
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
    with st.expander(
        "Números: ganho de vitória por 1.000 créditos a mais, loadout da equipe sem olhar o adversário, "
        "e o cruzamento loadout da equipe x loadout do adversário"
    ):
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
                "loadout do adversário",
                "loadout da equipe",
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
        "esperado pelo dinheiro",
        "venceu de fato",
        rate_label,
        count_column="rounds",
        x_domain=[0, 1],
    )


def _show_following_rounds(team_rounds: pd.DataFrame) -> None:
    st.subheader("2. Perder um round abala a equipe no round seguinte?")
    st.caption(
        "A comparação por equipamento usa a taxa de vitória dos rounds com uma "
        "diferença parecida no valor inicial das duas equipes. A referência deixa "
        "de fora os rounds 1, 2, 13 e 14. Cada grupo reúne essas taxas pela frequência "
        "das faixas que contém. A diferença para essa média também pode refletir "
        "a força das equipes e outros fatores da partida."
    )
    st.caption(
        "Round fácil perdido é quando a equipe perdeu um round em que o adversário venceu em desvantagem "
        "(clutch ou thrifty). Quadrado mostra quantos rounds seguintes a equipe deveria vencer só pelo "
        "dinheiro que tinha. Círculo mostra quantos venceu de fato."
    )
    close_rounds = team_rounds[team_rounds["match_id"].isin(close_match_ids(team_rounds))]
    all_column, close_column = st.columns(2)
    result_labels = {
        "perdeu round fácil (clutch ou thrifty do adversário)": "perdeu round fácil",
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
    close_column.markdown(
        f"**Só partidas equilibradas** (até 4 rounds de diferença no placar final, {close_match_count} partidas)"
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
    streak_column.markdown(
        "**Quantos rounds seguidos, na mesma metade, a equipe tinha perdido antes deste**, todas as partidas"
    )
    streak_column.altair_chart(
        _equipment_comparison(
            after_streak(team_rounds),
            "derrotas",
            "% de rounds vencidos",
        ),
        width="stretch",
    )
    close_streak_column.markdown(
        "**Quantos rounds seguidos, na mesma metade, a equipe tinha perdido antes deste**, só partidas equilibradas"
    )
    close_streak_column.altair_chart(
        _equipment_comparison(
            after_streak(close_rounds),
            "derrotas",
            "% de rounds vencidos",
        ),
        width="stretch",
    )


def _show_pistol_cycles(team_rounds: pd.DataFrame) -> None:
    st.subheader("3. Quem perde o pistol deve economizar ou comprar no round 2?")
    st.caption(
        "Pistol é o primeiro round de cada metade, nos rounds 1 e 13. "
        "O gráfico acompanha quem perdeu esse round. As faixas eco, leve e force "
        "agrupam o valor do equipamento no round seguinte, até 4 mil, de 4 a 8 mil "
        "e acima de 8 mil créditos."
    )
    pistol_column, cycle_column = st.columns([1, 3])
    pistol_column.markdown("**Round pistol**, quantos cada lado vence")
    display_table(pistol_by_side(team_rounds), width="content", container=pistol_column)
    overall_cycles, cycles_by_side = second_round_cycle(team_rounds)
    cycle_column.markdown(
        "**Equipe que perdeu o pistol, o que ela gastou no round 2 e quantos dos rounds 2, 3 e 4 venceu.** "
        "Nas tabelas, taxa prévia é a taxa de vitória da equipe nos rounds anteriores ao pistol, que só existe "
        "na segunda metade, para ver se quem força é uma equipe melhor ou pior."
    )
    cycle_column.caption(
        "As três taxas e a soma usam os mesmos ciclos completos. "
        "Se a partida terminou antes, o ciclo aparece na tabela como incompleto. "
        "A comparação descreve os grupos observados e não recomenda uma compra."
    )
    cycle_column.altair_chart(
        grouped_bar_chart(
            overall_cycles[["vitoria_round_2", "vitoria_round_3", "vitoria_round_4"]].rename(
                columns={
                    "vitoria_round_2": "round 2",
                    "vitoria_round_3": "round 3",
                    "vitoria_round_4": "round 4",
                }
            ),
            [WON_COLOR, TRADE_COLOR, NEUTRAL_COLOR],
            "% de rounds vencidos",
        ),
        width="stretch",
    )
    with st.expander("Números dos rounds 2 a 4, no total e por lado"):
        st.caption(
            "A taxa anterior usa somente rounds que aconteceram antes do pistol. "
            "Ela fica vazia quando não há rounds anteriores."
        )
        display_table(overall_cycles, width="stretch", container=st)
        display_table(cycles_by_side, width="stretch", container=st)


def _show_first_victim_and_survivors(team_rounds: pd.DataFrame, fights: pd.DataFrame) -> None:
    st.subheader("4. Perder o jogador mais caro custa mais? E sobreviver a um round perdido vale quanto?")
    st.caption(
        "As primeiras mortes são comparadas com a taxa de vitória da equipe "
        "na própria partida. Os valores são os do início do round."
    )
    expensive_column, _ = st.columns(2)
    expensive_column.markdown(
        "**Comparação quando o primeiro a morrer é o jogador com maior loadout da equipe**, "
        "em relação à média da equipe na partida."
    )
    expensive_column.caption("O grupo só inclui o maior valor quando não há empate com um aliado.")
    display_table(
        economic_first_death(fights, "mais_caro_do_time"),
        width="content",
        container=expensive_column,
    )
    surviving_players = save_effect(team_rounds, fights)
    surviving_players = surviving_players[surviving_players["rounds"] >= 20]
    equipment_column, wins_column = st.columns(2)
    equipment_column.markdown(
        "**Quanto a equipe tem para gastar no round seguinte**, conforme quantos jogadores sobreviveram "
        "ao round perdido (sem os rounds 12 e 24 nem a prorrogação, em que o dinheiro zera)"
    )
    equipment_column.bar_chart(
        surviving_players["loadout_seguinte"],
        color=[WON_COLOR],
        y_label="loadout do round seguinte",
        x_label="sobreviventes",
    )
    wins_column.markdown("**Chance de vencer o round seguinte**, conforme quantos sobreviveram")
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
    st.subheader("5. Vale a pena caçar quem está guardando para o próximo round?")
    st.caption(
        "Os arquivos não dizem quem foi atrás de quem, então considera-se quanto cada sobrevivente vale para "
        "quem venceu e para quem perdeu o round, e como terminam as lutas depois do plant quando o ataque já "
        "está em vantagem."
    )
    equipment_column, exchange_column = st.columns(2)
    next_equipment, round_counts = next_loadout_by_outcome(team_rounds, fights)
    equipment_column.markdown(
        "**Quanto a equipe tem para gastar no round seguinte**, conforme quantos sobreviveram, "
        "para quem venceu e para quem perdeu o round"
    )
    equipment_column.altair_chart(
        grouped_bar_chart(
            next_equipment.rename_axis(index="sobreviventes"),
            [WON_COLOR, LOST_COLOR],
            "loadout do round seguinte",
            ".0f",
        ),
        width="stretch",
    )
    plants = context.data.plants()
    plants = plants[plants["match_id"].isin(context.selected_match_ids)]
    post_plant_deaths = post_plant_exchange(plants, fights)
    exchange_column.markdown(
        "**Parte das mortes depois do plant que são de atacantes**, por situação no plant "
        "(atacantes x defensores vivos), em rounds que o ataque venceu"
    )
    exchange_column.altair_chart(
        rate_chart(
            post_plant_deaths,
            "situacao",
            "parte_do_ataque",
            "mortes_pos_plant",
            "% das mortes depois do plant que são de atacantes",
            color=ATTACK_COLOR,
        ),
        width="stretch",
    )
    with st.expander("Números por sobreviventes e por situação no plant"):
        display_table(
            round_counts.rename(columns=lambda column: f"rounds, {column}"),
            width="content",
            container=st,
        )
        display_table(post_plant_deaths, width="content", container=st)
