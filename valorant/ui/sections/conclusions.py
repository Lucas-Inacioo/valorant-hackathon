"""Documento de resultados calculados para a base padrão."""

import streamlit as st

from valorant.paths import PROJECT_ROOT
from valorant.ui.context import AppContext


def render(context: AppContext) -> None:
    st.caption(
        "Estas conclusões foram calculadas para a base padrão indicada no documento. "
        "Os filtros do menu não mudam o texto. As outras seções mostram os números da seleção atual."
    )
    st.markdown((PROJECT_ROOT / "CONCLUSOES.md").read_text(encoding="utf-8"))
