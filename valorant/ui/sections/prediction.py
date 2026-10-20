"""Comparações com o resultado conhecido e avaliação com histórico anterior."""

import streamlit as st

from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table
from valorant.ui.tables import display_number


def render(context: AppContext) -> None:
    st.header("Previsão")
    st.write(
        "Aqui comparamos regras simples para escolher a equipe vencedora. "
        "O acerto é a parte dos palpites que bate com o resultado. Quando as medidas empatam ou falta histórico, a regra fica sem palpite."
    )
    prediction = context.data.predictions()
    chance_median, chance_95 = prediction["acaso"]
    st.subheader("Comparação dentro da partida")
    st.caption(
        "Esta tabela usa números da própria partida depois que ela terminou. "
        "Ela mostra se a equipe com a medida melhor também venceu."
    )
    st.caption(
        f"Ao embaralhar os vencedores, o acerto mediano é {display_number(chance_median, '.1%')}. "
        f"Em 5% desses sorteios, o acerto chega a {display_number(chance_95, '.1%')} ou mais."
    )
    display_table(prediction["dentro"], hide_index=True, width="content")

    st.subheader("Comparação com outras partidas do campeonato")
    st.caption(
        "O perfil de cada equipe usa outras partidas, incluindo jogos posteriores. "
        "Esta avaliação ajuda a comparar medidas, mas não reproduz um palpite feito antes do jogo."
    )
    display_table(prediction["outras"], hide_index=True, width="content")

    st.subheader("Palpite usando apenas partidas anteriores")
    st.caption(
        "Esta avaliação respeita a ordem dos jogos. O histórico de comparação escolhe a equipe "
        "com maior taxa de vitória nas partidas anteriores e usa os mesmos jogos de cada regra. "
        "A diferença de acerto compara esses palpites jogo a jogo."
    )
    display_table(prediction["anteriores"], hide_index=True, width="content")
    st.caption(
        "O intervalo de 95% mostra a incerteza do acerto pelo método de Wilson. "
        "Para a diferença entre regras, a faixa vem de repetir a comparação sorteando partidas. "
        "Poucos jogos avaliados limitam a leitura do resultado. Jogos das mesmas equipes compartilham condições, por isso os intervalos não resumem toda a incerteza."
    )

    st.subheader("Perfil das equipes por campeonato")
    st.caption(
        "O perfil combinado soma seis medidas colocadas na mesma escala. "
        "Primeiros abates, trocas e plants sem abate entre adversários antes aumentam o perfil. "
        "Mortes isoladas e mortes da defesa separadas do grupo o reduzem. Entram equipes com pelo menos três partidas."
    )
    st.caption(
        "A correlação de Spearman compara a ordem das equipes pelo perfil com a ordem pelas vitórias. "
        "O valor 1 indica a mesma ordem, 0 indica falta de relação na ordenação e −1 indica a ordem inversa. "
        "Este ranking descreve o campeonato já jogado."
    )
    rankings = list(prediction["rankings"].items())
    for start in range(0, len(rankings), 2):
        for column, (tournament, table) in zip(st.columns(2), rankings[start : start + 2]):
            column.markdown(f"**{tournament}**")
            column.caption(
                f"Correlação de Spearman de {display_number(table['spearman'].iloc[0], '.2f')}"
            )
            display_table(table.drop(columns=["spearman"]), container=column, width="stretch")
