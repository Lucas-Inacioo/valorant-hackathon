"""Inicialização, filtros comuns e encaminhamento para a tela escolhida."""

import streamlit as st

from valorant.data.quality import data_signature
from valorant.ui.context import AppContext
from valorant.ui.data import AnalysisData, load_inventory, load_quality
from valorant.ui.navigation import render_content, render_navigation


def build_context() -> AppContext | None:
    data_version = data_signature()
    matches, players, rounds = load_inventory(data_version)
    if matches.empty:
        st.info("Ainda não há partidas. Veja no README como baixar os arquivos.")
        return None

    tournaments = sorted(matches["torneio"].unique())
    versions = sorted(matches["versao"].unique())
    st.sidebar.subheader("Filtros")
    chosen_tournaments = st.sidebar.multiselect("Torneios", tournaments, default=tournaments)
    chosen_versions = st.sidebar.multiselect("Versões do jogo", versions, default=versions)
    include_anomalous = st.sidebar.checkbox(
        "Incluir partidas com dados atípicos",
        value=False,
        help="Uma partida tem muitos rounds sem abates nem plant. Ela fica fora das análises por padrão.",
    )
    quality, eligible_ids = load_quality(data_version, include_anomalous)
    selected_matches = matches[
        matches["torneio"].isin(chosen_tournaments)
        & matches["versao"].isin(chosen_versions)
        & matches["match_id"].isin(eligible_ids)
    ]
    match_ids = tuple(sorted(selected_matches["match_id"]))
    st.sidebar.caption(
        "Os filtros valem para todas as análises. O documento de conclusões usa a base padrão."
    )
    return AppContext(
        data=AnalysisData(data_version, match_ids),
        matches=matches,
        players=players,
        rounds=rounds,
        selected_matches=selected_matches,
        selected_players=players[players["match_id"].isin(match_ids)],
        selected_rounds=rounds[rounds["match_id"].isin(match_ids)],
        quality=quality,
    )


def run() -> None:
    st.set_page_config(page_title="VALORANT Hackathon", layout="wide")
    st.sidebar.title("VALORANT")
    st.sidebar.caption("Protótipo de análise de partidas")
    active_section = render_navigation()
    context = build_context()
    if context is None:
        return
    if not context.selected_match_ids:
        st.info("Selecione ao menos um torneio e uma versão com partidas disponíveis.")
        return
    if active_section != "Dashboard da pesquisa":
        st.caption(
            f"A seleção contém {len(context.selected_matches)} partidas e "
            f"{len(context.selected_rounds)} rounds."
        )
    render_content(active_section, context)
