"""Documento de resultados calculados para a base padrão."""

import re

import streamlit as st

from valorant.paths import PROJECT_ROOT
from valorant.ui.context import AppContext


def display_report_numbers(text):
    """O relatório arquivado usa ponto nos milhares e vírgula nos decimais."""
    return re.sub(
        r"(?<![\w.,])[1-9]\d{0,2}(?:\.\d{3})+(?![\w.,])",
        lambda match: match.group().replace(".", ""),
        text,
    )


def render(context: AppContext) -> None:
    st.caption(
        "Estas conclusões foram calculadas para a base padrão indicada no documento. "
        "Os filtros do menu não mudam o texto. As outras seções mostram os números da seleção atual."
    )
    st.markdown(display_report_numbers((PROJECT_ROOT / "CONCLUSOES.md").read_text(encoding="utf-8")))
