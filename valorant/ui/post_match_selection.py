"""Seleção de partida e navegação entre resumos e lances do pós-jogo."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from valorant.analysis.post_match import MatchReview
from valorant.analysis.prediction import parse_match_name, team_names_by_color
from valorant.data.fields import load_match
from valorant.ui.context import AppContext

ALL_PLAYERS = "Todos"
ALL_PATTERNS = "all"


@dataclass(frozen=True)
class PostMatchSelection:
    app: AppContext
    match_info: pd.Series
    match: dict
    team_id: str
    team_names: dict
    review: MatchReview

    @property
    def player_names(self):
        return {p["puuid"]: f'{p["gameName"]}#{p["tagLine"]}' for p in self.match["players"]}

    @property
    def team_players(self):
        return [
            p["puuid"]
            for p in self.match["players"]
            if not p.get("isObserver") and p["teamId"] == self.team_id
        ]

    @property
    def match_id(self):
        return self.match["matchInfo"]["matchId"]


def select_match_and_team(context: AppContext) -> PostMatchSelection:
    files = context.selected_matches["arquivo"].tolist()
    if st.session_state.get("pos_match") not in files:
        st.session_state["pos_match"] = files[0]
    chosen_file = st.selectbox("Partida", files, key="pos_match")
    match_info = context.selected_matches[context.selected_matches["arquivo"] == chosen_file].iloc[
        0
    ]
    match = load_match(Path(match_info["caminho"]))
    try:
        names = team_names_by_color(match, parse_match_name(Path(chosen_file)))
    except (ValueError, KeyError):
        names = {team["teamId"]: team["teamId"] for team in match["teams"]}
    teams = list(names)
    match_id = match["matchInfo"]["matchId"]
    previous_scope = st.session_state.get("review_scope")
    match_changed = previous_scope is None or previous_scope[0] != match_id
    current_team = st.session_state.get("review_team")
    if match_changed or current_team not in teams:
        # Reenviar o valor também atualiza o nome exibido para a mesma cor.
        # Remover a chave não sincroniza o seletor já montado no navegador.
        st.session_state["review_team"] = current_team if current_team in teams else teams[0]
    team_id = st.selectbox(
        "Equipe", teams, format_func=lambda team: f"{names[team]} ({team})", key="review_team"
    )
    scope = (match_id, team_id)
    if previous_scope != scope:
        player_ids = [
            p["puuid"]
            for p in match["players"]
            if not p.get("isObserver") and p["teamId"] == team_id
        ]
        st.session_state["pos_round"] = 0
        st.session_state["pos_player"] = (
            player_ids[0] if st.session_state.get("review_view") == "Jogadores" else ALL_PLAYERS
        )
        st.session_state["review_pattern"] = ALL_PATTERNS
        st.session_state["overview_round"] = 1
        st.session_state.pop("review_event_focus", None)
        st.session_state["review_scope"] = scope
    with st.spinner("Reunindo os lances da partida"):
        review = context.data.match_review(match)
    return PostMatchSelection(context, match_info, match, team_id, names, review)


def jump_to_evidence(
    selection: PostMatchSelection, pattern_id=ALL_PATTERNS, player_id=ALL_PLAYERS, round_number=None
):
    """Callback executado antes dos seletores para abrir o primeiro lance correspondente."""
    observations = selection.review.observations
    chosen = observations[observations["team_id"] == selection.team_id]
    if pattern_id != ALL_PATTERNS:
        chosen = chosen[chosen["pattern_id"] == pattern_id]
    if player_id != ALL_PLAYERS:
        chosen = chosen[chosen["player_id"] == player_id]
    if round_number is not None:
        chosen = chosen[chosen["round"] == round_number]
    if not chosen.empty:
        chosen = chosen.sort_values(["won_round", "round", "time_ms"])
        first = chosen.iloc[0]
        round_number = int(first["round"])
        event_index = int(first["event_index"]) if pd.notna(first["event_index"]) else 0
    else:
        round_number = round_number or 1
        event_index = 0
    st.session_state["review_view"] = "Lances"
    st.session_state["review_pattern"] = pattern_id
    st.session_state["pos_player"] = player_id
    st.session_state["pos_round"] = round_number - 1
    serial = st.session_state.get("review_jump_serial", 0) + 1
    st.session_state["review_jump_serial"] = serial
    st.session_state["review_event_focus"] = {
        "match_id": selection.match_id,
        "round": round_number,
        "event_index": event_index,
    }
