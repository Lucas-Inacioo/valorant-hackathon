"""Resumos da partida, revisão individual e consulta dos lances."""

import pandas as pd
import streamlit as st

from valorant.analysis.post_match import PATTERNS
from valorant.ui.post_match_selection import (
    ALL_PATTERNS,
    ALL_PLAYERS,
    PostMatchSelection,
    evidence_origin,
    jump_to_evidence,
    return_from_evidence,
)
from valorant.ui.post_match_occurrences import render_occurrence_navigation
from valorant.ui.presentation import display_table
from valorant.ui.replay import RecordedRound, render_event_buttons, render_recorded_event
from valorant.ui.state_comparison import render_references


def _round_numbers(values):
    return ", ".join(str(int(value)) for value in values)


def _scope_observations(selection, player_id=ALL_PLAYERS, pattern_id=ALL_PATTERNS):
    observations = selection.review.observations
    observations = observations[observations["team_id"] == selection.team_id]
    if player_id != ALL_PLAYERS:
        observations = observations[observations["player_id"] == player_id]
    if pattern_id != ALL_PATTERNS:
        observations = observations[observations["pattern_id"] == pattern_id]
    return observations


def _pattern_table(summary):
    return pd.DataFrame(
        [
            {
                "Observação": row.pattern,
                "Ocorrências": row.occurrences,
                "Casos avaliáveis": row.opportunities,
                "Frequência": row.rate,
                "Rounds diferentes": row.round_count,
                "Rounds perdidos": row.lost_round_count,
                "Rounds para consultar": _round_numbers(row.round_numbers),
            }
            for row in summary.itertuples()
        ]
    )


def _show_pattern_table(summary):
    if not summary.empty:
        display_table(
            _pattern_table(summary),
            hide_index=True,
            percentage_columns=["Frequência"],
        )


def show_training_points(selection: PostMatchSelection, player_id=ALL_PLAYERS):
    summary = selection.review.pattern_summary(
        selection.team_id, None if player_id == ALL_PLAYERS else player_id
    )
    observed = summary[summary["occurrences"] > 0]
    points = observed[~observed["positive"] & ~observed["context_only"]]
    st.subheader("Pontos para rever")
    st.caption("Vários sinais do mesmo lance contam como um único round.")
    if points.empty:
        st.info("Não há ocorrências desses padrões com informação suficiente nesta seleção.")
    for row in points.itertuples():
        st.markdown(f"**{row.pattern}**")
        st.write(PATTERNS[row.pattern_id].summary.format(occurrences=row.occurrences, opportunities=row.opportunities))
        st.write(f"Ocorreu em {row.round_count} rounds diferentes, dos quais {row.lost_round_count} foram perdidos.")
        st.write(f"Pergunta a ser feita: {row.review_question}")
        st.button(
            "Rever os lances",
            key=f"review_pattern_{row.pattern_id}",
            on_click=jump_to_evidence,
            args=(selection, row.pattern_id, player_id),
        )
    if not points.empty:
        with st.expander("Ver todos os padrões e os rounds envolvidos"):
            _show_pattern_table(points)
            st.caption("Cada linha tem sua própria base de comparação.")

    positive = observed[observed["positive"] & ~observed["context_only"]]
    with st.expander("Acertos para manter"):
        if positive.empty:
            st.write(
                "Nenhuma das ações positivas desta lista foi identificada com os dados disponíveis."
            )
        _show_pattern_table(positive)
        for row in positive.itertuples():
            st.caption(row.description)
            st.button(
                f"Rever {row.pattern.lower()}",
                key=f"review_pattern_{row.pattern_id}",
                on_click=jump_to_evidence,
                args=(selection, row.pattern_id, player_id),
            )
    contexts = observed[observed["context_only"]]
    with st.expander("Contexto dos rounds"):
        _show_pattern_table(contexts)
        st.caption(
            "Esses registros descrevem condições do round ou a posição dos colegas. "
            "Eles precisam ser lidos junto da sequência de lances."
        )
        for row in contexts.itertuples():
            st.caption(row.description)
            st.button(
                f"Consultar {row.pattern.lower()}",
                key=f"review_pattern_{row.pattern_id}",
                on_click=jump_to_evidence,
                args=(selection, row.pattern_id, player_id),
            )


def show_team(selection: PostMatchSelection):
    rounds = selection.review.rounds
    rounds = rounds[rounds["team_id"] == selection.team_id]
    observations = _scope_observations(selection)
    review_points = observations[~observations["positive"] & ~observations["context_only"]]
    wins = int(rounds["won_round"].sum())
    columns = st.columns(3)
    columns[0].metric("Rounds vencidos", wins)
    columns[1].metric("Rounds perdidos", len(rounds) - wins)
    columns[2].metric(
        "Rounds perdidos com pontos para rever",
        review_points.loc[~review_points["won_round"], "round"].nunique(),
    )
    by_side = rounds.groupby("side")["won_round"].agg(rounds="size", wins="sum").reset_index()
    by_side["losses"] = by_side["rounds"] - by_side["wins"]
    display_table(
        by_side.rename(
            columns={"side": "Lado", "rounds": "Rounds", "wins": "Vitórias", "losses": "Derrotas"}
        ),
        hide_index=True,
    )
    show_training_points(selection)
    st.subheader("A partida round a round")
    show_round_table(selection)


def show_round_table(selection: PostMatchSelection, player_id=None):
    timeline = selection.review.round_summary(selection.team_id, player_id=player_id)
    table = pd.DataFrame(
        {
            "Round": timeline["round"],
            "Lado": timeline["side"],
            "Resultado": timeline["won_round"].map({True: "vitória", False: "derrota"}),
            "Observações": timeline["patterns"],
            "Ocorrências": timeline["occurrences"],
        }
    )
    display_table(table, hide_index=True)
    selected = st.selectbox(
        "Round para consultar",
        range(1, len(selection.match["roundResults"]) + 1),
        key="overview_round",
    )
    st.button(
        "Abrir os eventos deste round",
        key="review_open_round",
        on_click=jump_to_evidence,
        args=(selection, ALL_PATTERNS, player_id or ALL_PLAYERS, selected),
    )


def show_players(selection: PostMatchSelection):
    st.subheader("Jogadores da equipe")
    summary = selection.review.player_summary(selection.team_id)
    display_table(
        summary.rename(
            columns={
                "player_id": "Identificador",
                "player_name": "Jogador",
                "round_count": "Rounds jogados",
                "occurrences": "Observações para rever",
                "rounds_with_observations": "Rounds com observações",
                "lost_round_count": "Rounds perdidos com observações",
                "positive_occurrences": "Ações positivas",
            }
        ).drop(columns=["Identificador"], errors="ignore"),
        hide_index=True,
    )
    options = selection.team_players
    if st.session_state.get("pos_player") not in options:
        st.session_state["pos_player"] = options[0]
    player_id = st.selectbox(
        "Jogador", options, format_func=selection.player_names.get, key="pos_player"
    )
    show_training_points(selection, player_id)
    with st.expander("Consultar os rounds deste jogador"):
        show_round_table(selection, player_id)


def show_fight_context(selection: PostMatchSelection, recorded: RecordedRound, event_index):
    """Mantém informações do confronto fora dos sinais usados para priorizar treino."""
    event = recorded.events[event_index]
    if event["kind"] != "kill":
        return
    with st.expander("Outras informações deste confronto"):
        fights = selection.app.data.match_table(selection.match_id, "fights")
        fight = fights[
            (fights["round"] == recorded.round_index + 1)
            & (fights["event_id"] == event["event_id"])
        ]
        columns = {
            "dist_killer": "Distância de quem fez o abate em unidades",
            "dist_aliado_mais_proximo": "Aliado mais próximo em unidades",
            "dano_no_killer": "Dano no autor durante o round",
            "classe_luta": "Dano recebido durante o round",
            "regiao": "Região da morte",
            "territorio": "Ocupação nos primeiros confrontos da partida",
        }
        display_table(
            fight[[column for column in columns if column in fight]].rename(columns=columns),
            hide_index=True,
        )
        st.caption(
            "O dano é o total registrado no round inteiro "
            "e não mostra quando houve reação. A ocupação da região vem dos primeiros confrontos desta partida. "
            "As distâncias estão em unidades do jogo e o mapa não permite verificar a linha de tiro."
        )


def show_evidence(selection: PostMatchSelection):
    origin = evidence_origin(selection)
    if origin:
        label = "Voltar para o dashboard" if origin["state"].get("section") == "Dashboard da pesquisa" else (
            "Voltar para a análise do jogador"
            if origin["state"]["review_view"] == "Jogadores"
            else "Voltar para a análise da equipe"
        )
        st.button(
            label,
            key="review_return",
            on_click=return_from_evidence,
            args=(selection,),
        )
    player_options = [ALL_PLAYERS, *selection.team_players]
    if st.session_state.get("pos_player") not in player_options:
        st.session_state["pos_player"] = ALL_PLAYERS
    player_id = st.selectbox(
        "Jogador",
        player_options,
        format_func=lambda player: (
            "Toda a equipe" if player == ALL_PLAYERS else selection.player_names[player]
        ),
        key="pos_player",
    )
    summary = selection.review.pattern_summary(
        selection.team_id, None if player_id == ALL_PLAYERS else player_id
    )
    patterns = summary[summary["occurrences"] > 0]
    pattern_names = dict(zip(patterns["pattern_id"], patterns["pattern"]))
    pattern_options = [ALL_PATTERNS, *pattern_names]
    if st.session_state.get("review_pattern") not in pattern_options:
        st.session_state["review_pattern"] = ALL_PATTERNS
    pattern_id = st.selectbox(
        "Observação para consultar",
        pattern_options,
        format_func=lambda pattern: (
            "Todas as observações" if pattern == ALL_PATTERNS else pattern_names[pattern]
        ),
        key="review_pattern",
    )
    matching = _scope_observations(selection, player_id, pattern_id)
    if pattern_id != ALL_PATTERNS:
        st.caption(
            f"Esse padrão aparece nos rounds {_round_numbers(sorted(matching['round'].unique()))}."
        )
        st.button(
            "Ir para o primeiro lance desse padrão",
            key="review_filter_jump",
            on_click=jump_to_evidence,
            args=(selection, pattern_id, player_id),
        )
    round_options = list(range(len(selection.match["roundResults"])))
    if st.session_state.get("pos_round") not in round_options:
        st.session_state["pos_round"] = 0
    round_index = st.selectbox(
        "Round", round_options, format_func=lambda index: f"Round {index + 1}", key="pos_round"
    )
    raw_result = selection.match["roundResults"][round_index]
    team_won = raw_result["winningTeam"] == selection.team_id
    st.write(f"A equipe {'venceu' if team_won else 'perdeu'} este round.")
    round_observations = matching[matching["round"] == round_index + 1].sort_values("time_ms")
    if not round_observations.empty:
        display_table(
            round_observations[["player_name", "pattern", "time_ms"]]
            .assign(time_ms=lambda table: (table["time_ms"] / 1000).round(1))
            .rename(
                columns={
                    "player_name": "Jogador envolvido",
                    "pattern": "Observação",
                    "time_ms": "Segundo do round",
                }
            ),
            hide_index=True,
        )
        for question in round_observations["review_question"].drop_duplicates():
            st.caption(question)
    else:
        st.info(
            "Nenhuma observação desta seleção foi registrada neste round. Todos os eventos continuam disponíveis abaixo."
        )
    anchor_player = selection.team_players[0] if player_id == ALL_PLAYERS else player_id
    recorded = RecordedRound(
        selection.match_info,
        selection.match,
        round_index,
        anchor_player,
        highlight_selected=player_id != ALL_PLAYERS,
    )
    focus = st.session_state.get("review_event_focus", {})
    initial_event = (
        focus.get("event_index", 0)
        if focus.get("match_id") == selection.match_id and focus.get("round") == round_index + 1
        else 0
    )
    serial = st.session_state.get("review_jump_serial", 0)
    st.subheader("Eventos do round")
    event_index = render_event_buttons(
        recorded, key_prefix=f"postmatch_event_{serial}", initial_event_index=initial_event
    )
    render_occurrence_navigation(selection, recorded, event_index, pattern_id, player_id)
    if event_index is not None:
        map_metadata = selection.app.data.maps().get(selection.match["matchInfo"]["mapId"])
        if map_metadata is None:
            st.info("Este mapa não tem imagem disponível. As posições aparecem na tabela.")
        render_recorded_event(recorded, event_index, map_metadata)
        show_fight_context(selection, recorded, event_index)
    if st.checkbox("Comparar situações parecidas", key="review_references"):
        render_references(selection.app, recorded)
