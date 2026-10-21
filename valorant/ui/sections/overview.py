"""Dashboard da pesquisa, com achados, ranking e acesso à revisão das partidas."""

import streamlit as st

from valorant.ui.context import AppContext
from valorant.ui.presentation import display_table
from valorant.ui.research_findings import decimal, show_findings
from valorant.ui.research_evidence import show_evidence_context
from valorant.ui.research_ranking import show_ranking

ALL_TOURNAMENTS = "Todos os torneios selecionados"


def render(context: AppContext) -> None:
    st.header("Dashboard da pesquisa")
    st.write(
        "Veja os achados das partidas, quais equipes acumulam mais lances para rever e como essa frequência "
        "se relaciona com o desempenho observado. Os números acompanham os filtros do menu lateral."
    )
    options = [ALL_TOURNAMENTS, *sorted(context.selected_matches["torneio"].unique())]
    if st.session_state.get("dashboard_tournament") not in options:
        st.session_state["dashboard_tournament"] = ALL_TOURNAMENTS
    selected = st.selectbox("Recorte do dashboard", options, key="dashboard_tournament")
    tournament = None if selected == ALL_TOURNAMENTS else selected
    inventory = context.selected_matches
    if tournament is not None:
        inventory = inventory[inventory["torneio"].eq(tournament)]
    match_ids = set(inventory["match_id"])
    with st.spinner("Reunindo as observações da pesquisa. A primeira consulta pode demorar um pouco"):
        data = context.data.research()
    teams = data.team_matches[data.team_matches["match_id"].isin(match_ids)]
    games_per_team = teams.groupby("team_name")["matches"].sum()
    columns = st.columns(4)
    columns[0].metric("Partidas", len(inventory))
    columns[1].metric("Rounds", int(teams["rounds"].sum() / 2))
    columns[2].metric("Equipes", len(games_per_team))
    columns[3].metric("Lances de equipe para rever", int(teams["review_events"].sum()))
    st.caption(
        f"Cada equipe tem em média {decimal(games_per_team.mean(), 1)} partidas, com mediana de "
        f"{decimal(games_per_team.median(), 1)}. Os nomes das equipes vêm dos arquivos. Nomes diferentes "
        "permanecem separados e um mesmo nome pode ter mudanças de elenco ao longo da base."
    )
    show_findings(data, match_ids)
    show_evidence_context(context, data, match_ids)
    show_ranking(context, teams, tournament)
    st.caption(
        "As observações ajudam a escolher lances para rever. A base registra instantes, sem trajetória contínua "
        "ou linha de tiro. Uma frequência menor também pode refletir diferença na disponibilidade de posições. "
        "As associações não demonstram que um jogador causou a derrota."
    )
    st.write("A seção Previsão avalia o uso de partidas anteriores para antecipar resultados de outros jogos.")
    with st.expander("Ver a lista de partidas"):
        display_table(
            inventory.drop(
                columns=["match_id", "caminho", "mapa_interno", "mapa_do_arquivo"]
            ),
            hide_index=True,
        )
