"""Ordem de navegação e carregamento das telas sob demanda."""

from importlib import import_module

import streamlit as st

DASHBOARD = "Dashboard da pesquisa"
POST_MATCH = "Análise pós-jogo"
EXPLORATORY_AREA = "Dados exploratórios e análises"
MAIN_AREAS = ("Dashboard", POST_MATCH, EXPLORATORY_AREA)

SECTIONS = {
    "Dashboard da pesquisa": "overview",
    "Análise pós-jogo": "post_match",
    "Primeiro abate": "opening",
    "Trocas e isolamento": "trades",
    "Ritmo dos rounds": "round_patterns",
    "Economia": "economy",
    "Plant e desarme": "spike",
    "Previsão": "prediction",
    "Conclusões": "conclusions",
    "Explorar dados": "exploration",
    "Qualidade dos dados": "quality",
}
EXPLORATORY_SECTIONS = {name: module for name, module in SECTIONS.items() if name not in {DASHBOARD, POST_MATCH}}


def section_area(section):
    if section in EXPLORATORY_SECTIONS:
        return EXPLORATORY_AREA
    return POST_MATCH if section == POST_MATCH else "Dashboard"


def navigate(section):
    """Mantém uma rota única para o menu e os atalhos que abrem lances."""
    if section not in SECTIONS:
        section = DASHBOARD
    st.session_state["section"] = section
    if section in EXPLORATORY_SECTIONS:
        st.session_state["last_exploratory_section"] = section


def select_main_area():
    area = st.session_state["navigation_area"]
    if area == EXPLORATORY_AREA:
        select_exploratory_area()
    else:
        navigate(POST_MATCH if area == POST_MATCH else DASHBOARD)


def select_exploratory_tab():
    navigate(st.session_state["exploratory_tabs"])


def render_navigation():
    section = st.session_state.get("section", DASHBOARD)
    if section not in SECTIONS:
        section = DASHBOARD
    navigate(section)
    # Sincroniza também os saltos feitos pelos botões do dashboard e do replay.
    st.session_state["navigation_area"] = section_area(section)
    st.sidebar.radio(
        "Navegação", MAIN_AREAS, key="navigation_area", on_change=select_main_area,
        captions=["Resumo dos achados", "Ferramenta para revisar partidas", "De onde vieram os resultados"],
    )
    return section


def render_dashboard_paths():
    tool, research = st.columns(2)
    with tool.container(border=True):
        st.markdown("**Ferramenta de análise pós-jogo**")
        st.write("Esse é o meu entregável para a Hackaton, lances decisivos para a partida são selecionados e podem ser revisados em um mapa.")
        st.button("Abrir ferramenta de análise pós-jogo", key="dashboard_go_post_match", type="primary",
                  on_click=navigate, args=(POST_MATCH,))
    with research.container(border=True):
        st.markdown(f"**{EXPLORATORY_AREA}**")
        st.write("Aqui estão as análises que fiz para chegar ao meu entregável, são apenas para consulta e curiosidade. Cada seção está explicada, com conclusões específicas dela e também com dados inconclusivos, mas que foram avaliados como parte do projeto.")
        st.button("Explorar dados e análises", key="dashboard_go_exploratory", on_click=select_exploratory_area)


def select_exploratory_area():
    previous = st.session_state.get("last_exploratory_section")
    navigate(previous if previous in EXPLORATORY_SECTIONS else next(iter(EXPLORATORY_SECTIONS)))


def render_content(section, context):
    if section not in EXPLORATORY_SECTIONS:
        render_section(section, context)
        return
    st.header(EXPLORATORY_AREA)
    st.write("Estas são as análises que deram origem aos achados do dashboard. Escolha uma aba para consultar os dados, os critérios e os resultados em detalhe.")
    st.session_state["exploratory_tabs"] = section
    tabs = st.tabs(list(EXPLORATORY_SECTIONS), key="exploratory_tabs", on_change=select_exploratory_tab)
    for name, tab in zip(EXPLORATORY_SECTIONS, tabs):
        if tab.open:
            with tab:
                render_section(name, context)


def render_section(name, context):
    section = import_module(f"valorant.ui.sections.{SECTIONS[name]}")
    section.render(context)
