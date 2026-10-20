"""Ordem de navegação e carregamento das telas sob demanda."""

from importlib import import_module

SECTIONS = {
    "Visão geral": "overview",
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


def render_section(name, context):
    section = import_module(f"valorant.ui.sections.{SECTIONS[name]}")
    section.render(context)
