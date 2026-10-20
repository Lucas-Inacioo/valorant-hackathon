"""Comparação histórica complementar para os lances de uma partida."""

import altair as alt
import streamlit as st

from valorant.analysis.state_reference import describe_state, match_win_added
from valorant.ui.charts import ATTACK_COLOR
from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table, display_value, field_label
from valorant.ui.replay import RecordedRound
from valorant.ui.round_map import describe_event
from valorant.ui.tables import attacking_team


def round_references(context: AppContext, recorded: RecordedRound):
    state_table, _ = context.data.states(recorded.match_info["match_id"])
    attacking_by_round = {
        result["roundNum"] + 1: attacking_team(result) for result in recorded.match["roundResults"]
    }
    rounds = context.data.rounds()
    attack_rounds = rounds[
        (rounds["match_id"] == recorded.match_info["match_id"]) & (rounds["lado"] == "ataque")
    ]
    starting_equipment = {
        row.round: {"faixa_diferenca": str(row.faixa_diferenca)}
        for row in attack_rounds.itertuples()
    }
    selected_match = dict(recorded.match, roundResults=[recorded.result])
    references = match_win_added(
        selected_match, attacking_by_round, state_table, starting_equipment
    )
    if not references.empty:
        references["descricao"] = [
            (
                describe_event(
                    recorded.events[int(row.evento)], recorded.player_names, recorded.result
                )
                if 0 <= row.evento < len(recorded.events)
                else "Resultado final registrado"
            )
            for row in references.itertuples()
        ]
        references["estado"] = references["estado"].map(describe_state)
        references["passo"] = range(1, len(references) + 1)
    return references


def render_references(context: AppContext, recorded: RecordedRound):
    st.subheader("Como terminaram rounds em situações parecidas")
    st.write(
        "Uma situação reúne a quantidade de jogadores vivos, o momento antes ou depois do plant, "
        "a diferença de equipamento inicial e a faixa de tempo. Antes do plant, o tempo conta desde o fim da compra. Depois, conta desde o plant. A comparação procura essa mesma combinação em outras partidas selecionadas, sem exigir o mesmo mapa ou as mesmas equipes. Ela pode incluir jogos posteriores, por isso descreve a base já observada."
    )
    st.caption(
        "A taxa mostra quantos desses rounds o ataque venceu. Ela só aparece com pelo menos 20 rounds de 5 outras partidas. "
        "O intervalo de 95% vem de sortear partidas inteiras e repetir a conta. Essa taxa não avalia o mérito de quem fez o lance."
    )
    references = round_references(context, recorded)
    if references.empty:
        st.info("Este round não tem registros suficientes para consultar a comparação.")
        return
    supported = references["depois_ataque"].notna()
    st.metric("Eventos com comparação disponível", f"{int(supported.sum())} / {len(references)}")
    if supported.any():
        base = alt.Chart(references).encode(x=alt.X("passo:O", title="Evento do round"))
        tooltip_fields = [
            "descricao",
            "estado",
            "n_depois",
            "partidas_depois",
            "faixa_diferenca",
            "faixa_tempo",
        ]
        points = base.mark_point(size=100, filled=True, color=ATTACK_COLOR).encode(
            y=alt.Y(
                "depois_ataque:Q",
                title="Rounds vencidos pelo ataque",
                axis=alt.Axis(format=".0%"),
                scale=alt.Scale(domain=[0, 1]),
            ),
            tooltip=[alt.Tooltip(field, title=field_label(field)) for field in tooltip_fields]
            + [alt.Tooltip("depois_ataque:Q", title="Vitórias do ataque", format=".1%")],
        )
        intervals = base.mark_rule(color="#444444").encode(y="ic_baixo:Q", y2="ic_alto:Q")
        st.altair_chart((intervals + points).properties(height=300), width="stretch")
        st.caption(
            "Os pontos mostram as taxas e os traços mostram os intervalos. Um evento sem comparação fica sem ponto."
        )
    else:
        st.info(
            "Não há rounds suficientes em situações parecidas nas outras partidas da seleção. Tente incluir mais torneios ou versões do jogo."
        )
    columns = [
        "descricao",
        "tipo",
        "estado",
        "fase",
        "faixa_diferenca",
        "faixa_tempo",
        "antes_ataque",
        "depois_ataque",
        "n_depois",
        "partidas_depois",
        "ic_baixo",
        "ic_alto",
        "observacao",
    ]
    display_table(
        references[[column for column in columns if column in references]], hide_index=True
    )
    st.caption(
        f'{recorded.result["winningTeam"]} venceu o round por {display_value(recorded.result["roundResult"])}.'
    )
