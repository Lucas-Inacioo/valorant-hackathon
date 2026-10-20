"""Consulta de ocorrências e comparações para um round escolhido."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from valorant.analysis.factors import (
    match_player_summary,
    match_team_summary,
    match_timeline,
    player_decisions,
)
from valorant.analysis.state_reference import describe_state, match_win_added
from valorant.data.fields import load_match
from valorant.ui.charts import ATTACK_COLOR
from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table, display_value, field_label
from valorant.ui.replay import RecordedRound, render_recorded_event
from valorant.ui.round_map import describe_event
from valorant.ui.tables import attacking_team


def select_recorded_round(context: AppContext) -> RecordedRound:
    if st.button("Sortear partida, round e jogador"):
        random_info = context.selected_matches.sample(1).iloc[0]
        random_match = load_match(Path(random_info["caminho"]))
        st.session_state["pos_match"] = random_info["arquivo"]
        st.session_state["pos_round"] = int(
            pd.Series(range(len(random_match["roundResults"]))).sample(1).iloc[0]
        )
        st.session_state["pos_player"] = (
            pd.Series([p["puuid"] for p in random_match["players"] if not p["isObserver"]])
            .sample(1)
            .iloc[0]
        )
    match_files = context.selected_matches["arquivo"].tolist()
    if st.session_state.get("pos_match") not in match_files:
        st.session_state.pop("pos_match", None)
    match_column, round_column, player_column = st.columns(3)
    chosen_file = match_column.selectbox("Partida", match_files, key="pos_match")
    match_info = context.selected_matches[context.selected_matches["arquivo"] == chosen_file].iloc[
        0
    ]
    match = load_match(Path(match_info["caminho"]))
    participants = {p["puuid"]: p for p in match["players"] if not p["isObserver"]}
    if st.session_state.get("pos_round") not in range(len(match["roundResults"])):
        st.session_state.pop("pos_round", None)
    if st.session_state.get("pos_player") not in participants:
        st.session_state.pop("pos_player", None)
    round_index = round_column.selectbox(
        "Round",
        range(len(match["roundResults"])),
        format_func=lambda index: f"Round {index + 1}",
        key="pos_round",
    )
    player_id = player_column.selectbox(
        "Jogador",
        list(participants),
        format_func=lambda player: f'{participants[player]["gameName"]}#{participants[player]["tagLine"]} ({participants[player]["teamId"]})',
        key="pos_player",
    )
    return RecordedRound(match_info, match, round_index, player_id)


def render_occurrences(context: AppContext, recorded: RecordedRound, map_metadata):
    flagged_deaths, flagged_rounds = context.data.factors()
    st.subheader("O que aconteceu na partida")
    st.caption(
        "Cada coluna conta um tipo de ocorrência. O mesmo round pode aparecer em mais de uma coluna. "
        "Essas contagens ajudam a localizar lances para rever."
    )
    display_table(match_team_summary(flagged_rounds, recorded.match_info["match_id"], {}).T)
    display_table(match_player_summary(recorded.match, flagged_deaths, {}))
    with st.expander("Ver as ocorrências por round"):
        display_table(match_timeline(flagged_rounds, recorded.match_info["match_id"], {}))
    st.subheader("Lances do jogador no round")
    round_deaths = flagged_deaths[
        (flagged_deaths["match_id"] == recorded.match_info["match_id"])
        & (flagged_deaths["round"] == recorded.round_index + 1)
    ]
    decisions = player_decisions(
        recorded.events,
        recorded.player_teams,
        recorded.player_id,
        round_deaths,
        {},
        name_of=recorded.player_names.get,
    )
    if not decisions:
        st.info("Nenhuma das ocorrências da lista foi registrada para este jogador neste round.")
    else:
        chosen = st.selectbox(
            "Lance para ver no mapa",
            range(len(decisions)),
            format_func=lambda index: decisions[index]["fator"],
        )
        decision = decisions[chosen]
        st.write(decision["detalhe"].rstrip(".") + ".")
        render_recorded_event(recorded, decision["evento"], map_metadata)
    render_associations(context)


def render_associations(context: AppContext):
    panel = st.expander(
        "Comparar ocorrências em todas as partidas selecionadas",
        on_change="rerun",
        key="association_panel",
    )
    if not panel.open:
        return
    with panel:
        st.write(
            "A diferença compara a taxa de vitória com e sem cada ocorrência. "
            "Por exemplo, 60% contra 50% são 10 pontos percentuais de diferença. "
            "Ela descreve os grupos e não mede o efeito de uma decisão."
        )
        st.caption(
            "O intervalo de 95% vem de repetir a comparação sorteando partidas inteiras. "
            "Nas linhas de mortes, um round com mais mortes entra mais vezes na conta."
        )
        negative, positive = context.data.associations()
        combined = pd.concat([negative, positive], ignore_index=True).drop_duplicates("fator")
        for unit, table in combined.groupby("unidade", sort=False):
            st.markdown(f"**{unit}**")
            table = table.sort_values("diferenca").copy()
            for column in ["diferenca", "ic_baixo", "ic_alto"]:
                table[column] = table[column] * 100
            display_table(
                table,
                hide_index=True,
                column_config={
                    "diferenca": st.column_config.NumberColumn(
                        "Diferença em pontos percentuais", format="%+.1f"
                    ),
                    "ic_baixo": st.column_config.NumberColumn(
                        "Limite inferior em pontos percentuais", format="%+.1f"
                    ),
                    "ic_alto": st.column_config.NumberColumn(
                        "Limite superior em pontos percentuais", format="%+.1f"
                    ),
                },
            )


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


def render(context: AppContext) -> None:
    st.header("Revisar um round")
    st.write(
        "Escolha uma partida, um round e um jogador para encontrar lances e consultar situações parecidas em outros jogos."
    )
    recorded = select_recorded_round(context)
    info = recorded.match_info
    st.caption(
        f'{info["torneio"]} no mapa {info["mapa"]}. Blue fez {info["rounds_blue"]} rounds e Red fez {info["rounds_red"]}.'
    )
    view = st.radio(
        "Visualização", ["Ocorrências da partida", "Situações parecidas"], horizontal=True
    )
    if view == "Ocorrências da partida":
        map_metadata = context.data.maps().get(recorded.match["matchInfo"]["mapId"])
        render_occurrences(context, recorded, map_metadata)
    else:
        render_references(context, recorded)
